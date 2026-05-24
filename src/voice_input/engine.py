from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from collections.abc import Callable
from enum import Enum, auto

from voice_input.asr import create_asr_backend
from voice_input.asr.base import ASRBase
from voice_input.audio.recorder import AudioRecorder
from voice_input.audio.vad import VoiceActivityDetector
from voice_input.config import AppConfig
from voice_input.hotkey.listener import HotkeyListener
from voice_input.output.clipboard import ClipboardOutput
from voice_input.output.typer import KeyboardTyper
from voice_input.text.polisher import AIPolisher
from voice_input.text.processor import TextProcessor

logger = logging.getLogger(__name__)

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


class EngineState(Enum):
    IDLE = auto()
    RECORDING = auto()
    PROCESSING = auto()


class VoiceEngine:
    def __init__(self, config: AppConfig | None = None):
        self._config = config or AppConfig()
        self._state = EngineState.IDLE

        self._recorder = AudioRecorder(self._config.audio)
        self._asr: ASRBase | None = None
        self._vad = VoiceActivityDetector(self._config.audio)
        self._text_processor = TextProcessor(self._config.text)
        self._polisher = AIPolisher(self._config.polish)
        self._hotkey_listener = HotkeyListener(self._config.hotkey)

        self._clipboard_output = ClipboardOutput(self._config.output)
        self._keyboard_typer = KeyboardTyper(self._config.output)

        self._on_status_change: Callable[[EngineState], None] | None = None
        self._on_partial: Callable[[str], None] | None = None
        self._on_result: Callable[[str], None] | None = None
        self._on_polished: Callable[[str], None] | None = None
        self._on_error: Callable[[str], None] | None = None

        self._streaming_enabled = self._config.streaming.enabled
        self._stream_interval = self._config.streaming.interval
        self._stream_timer: threading.Timer | None = None
        self._stream_lock = threading.Lock()
        self._model_lock = threading.Lock()
        self._last_partial_text = ""
        self._last_pcm_bytes = 0
        self._min_stream_audio_ms = 800
        self._stream_future = None

        self._recorder.set_on_silence(self._on_silence_detected)

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def is_recording(self) -> bool:
        return self._state == EngineState.RECORDING

    def set_on_status_change(self, callback: Callable[[EngineState], None]) -> None:
        self._on_status_change = callback

    def set_on_partial(self, callback: Callable[[str], None]) -> None:
        self._on_partial = callback

    def set_on_result(self, callback: Callable[[str], None]) -> None:
        self._on_result = callback

    def set_on_polished(self, callback: Callable[[str], None]) -> None:
        self._on_polished = callback

    def set_on_error(self, callback: Callable[[str], None]) -> None:
        self._on_error = callback

    @property
    def polisher(self) -> AIPolisher:
        return self._polisher

    def initialize(self) -> None:
        logger.info(f"Initializing voice engine with backend: {self._config.asr.backend}")
        import sys
        import os
        _real_stdout = sys.stdout
        _real_stderr = sys.stderr
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")
        try:
            self._asr = create_asr_backend(self._config.asr.backend, self._config.asr)
            self._asr.load_model()
        finally:
            sys.stdout.close()
            sys.stderr.close()
            sys.stdout = _real_stdout
            sys.stderr = _real_stderr
        logger.info("Voice engine initialized")

    def start_recording(self) -> None:
        if self._state != EngineState.IDLE:
            logger.warning(f"Cannot start recording in state: {self._state}")
            return

        self._last_partial_text = ""
        self._last_pcm_bytes = 0
        self._set_state(EngineState.RECORDING)
        self._recorder.start_recording()

        if self._streaming_enabled:
            self._schedule_partial_transcribe()

        logger.info("Recording started")

    def stop_and_recognize(self) -> None:
        if self._state != EngineState.RECORDING:
            return

        self._cancel_stream_timer()
        self._set_state(EngineState.PROCESSING)

        if self._stream_future and not self._stream_future.done():
            try:
                self._stream_future.result(timeout=5)
            except Exception:
                pass

        audio_data = self._recorder.stop_recording()

        if not audio_data:
            logger.warning("No audio data recorded")
            self._set_state(EngineState.IDLE)
            return

        self._process_audio(audio_data)

    def recognize_file(self, file_path: str) -> str:
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        audio_data = path.read_bytes()
        return asyncio.run(self._async_recognize(audio_data))

    def start_hotkey(self) -> None:
        self._hotkey_listener.start(
            on_ptt_press=self.start_recording,
            on_ptt_release=self.stop_and_recognize,
            on_toggle=self._toggle_recording,
        )

    def stop_hotkey(self) -> None:
        self._hotkey_listener.stop()

    def _toggle_recording(self) -> None:
        if self._state == EngineState.IDLE:
            self.start_recording()
        elif self._state == EngineState.RECORDING:
            self.stop_and_recognize()

    def _on_silence_detected(self) -> None:
        logger.info("Silence detected, auto-stopping")
        self.stop_and_recognize()

    def _set_state(self, state: EngineState) -> None:
        self._state = state
        if self._on_status_change:
            self._on_status_change(state)

    def _schedule_partial_transcribe(self) -> None:
        if self._state != EngineState.RECORDING:
            return
        self._stream_timer = threading.Timer(
            self._stream_interval, self._do_partial_transcribe
        )
        self._stream_timer.daemon = True
        self._stream_timer.start()

    def _cancel_stream_timer(self) -> None:
        if self._stream_timer:
            self._stream_timer.cancel()
            self._stream_timer = None

    def _do_partial_transcribe(self) -> None:
        if not self._stream_lock.acquire(blocking=False):
            self._schedule_partial_transcribe()
            return

        try:
            if self._state != EngineState.RECORDING:
                return

            full_wav = self._recorder.get_audio_data()
            pcm_size = self._recorder.get_audio_size()

            if not full_wav or pcm_size <= self._last_pcm_bytes:
                return

            new_pcm_bytes = pcm_size - self._last_pcm_bytes
            min_bytes = int(self._min_stream_audio_ms * self._config.audio.sample_rate * 2 / 1000)

            if new_pcm_bytes < min_bytes:
                return

            wav_header_size = 44
            new_pcm = full_wav[wav_header_size + self._last_pcm_bytes : wav_header_size + pcm_size]

            import struct

            header = bytearray(full_wav[:wav_header_size])
            struct.pack_into("<I", header, 4, len(new_pcm) + 36)
            struct.pack_into("<I", header, 40, len(new_pcm))
            chunk_wav = bytes(header) + new_pcm

            self._last_pcm_bytes = pcm_size

            self._stream_future = _executor.submit(self._sync_recognize, chunk_wav)
            try:
                partial_text = self._stream_future.result(timeout=8)
            except concurrent.futures.TimeoutError:
                return

            if partial_text and partial_text != self._last_partial_text:
                self._last_partial_text = partial_text
                processed = self._text_processor.process(partial_text)
                if processed and self._on_partial:
                    self._on_partial(processed)
        except Exception as e:
            logger.debug(f"Partial transcribe error: {e}")
        finally:
            self._stream_lock.release()
            if self._state == EngineState.RECORDING:
                self._schedule_partial_transcribe()

    def _sync_recognize(self, audio_data: bytes) -> str:
        if not self._asr:
            return ""
        with self._model_lock:
            try:
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(
                        self._asr.transcribe(audio_data, self._config.audio.sample_rate)
                    )
                finally:
                    loop.close()
            except Exception as e:
                logger.debug(f"Sync recognize error: {e}")
                return ""

    def _process_audio(self, audio_data: bytes) -> None:
        try:
            future = _executor.submit(self._sync_recognize, audio_data)
            result_text = future.result(timeout=30)
            processed = self._text_processor.process(result_text)

            if not processed:
                logger.info("No speech detected")
                self._set_state(EngineState.IDLE)
                return

            final_text = processed

            if self._polisher.enabled:
                loop = asyncio.new_event_loop()
                try:
                    polished = loop.run_until_complete(self._polisher.polish(processed))
                finally:
                    loop.close()
                if polished and polished != processed:
                    final_text = polished
                    if self._on_polished:
                        self._on_polished(polished)

            self._output_text(final_text)
            if self._on_result:
                self._on_result(final_text)
            logger.info(f"Recognition result: {final_text}")

        except Exception as e:
            error_msg = f"Recognition failed: {e}"
            logger.error(error_msg)
            if self._on_error:
                self._on_error(error_msg)
        finally:
            self._set_state(EngineState.IDLE)

    async def _async_recognize(self, audio_data: bytes) -> str:
        if not self._asr:
            raise RuntimeError("ASR backend not initialized")

        return await self._asr.transcribe(audio_data, self._config.audio.sample_rate)

    def _output_text(self, text: str) -> None:
        mode = self._config.output.mode
        if mode == "clipboard":
            self._clipboard_output.output(text)
        elif mode == "typing":
            self._keyboard_typer.output(text)
        elif mode == "both":
            self._clipboard_output.output(text)
