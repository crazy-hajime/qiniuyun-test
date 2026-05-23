from __future__ import annotations

import asyncio
import logging
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
from voice_input.text.processor import TextProcessor

logger = logging.getLogger(__name__)


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
        self._hotkey_listener = HotkeyListener(self._config.hotkey)

        self._clipboard_output = ClipboardOutput(self._config.output)
        self._keyboard_typer = KeyboardTyper(self._config.output)

        self._on_status_change: Callable[[EngineState], None] | None = None
        self._on_result: Callable[[str], None] | None = None
        self._on_error: Callable[[str], None] | None = None

        self._recorder.set_on_silence(self._on_silence_detected)

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def is_recording(self) -> bool:
        return self._state == EngineState.RECORDING

    def set_on_status_change(self, callback: Callable[[EngineState], None]) -> None:
        self._on_status_change = callback

    def set_on_result(self, callback: Callable[[str], None]) -> None:
        self._on_result = callback

    def set_on_error(self, callback: Callable[[str], None]) -> None:
        self._on_error = callback

    def initialize(self) -> None:
        logger.info(f"Initializing voice engine with backend: {self._config.asr.backend}")
        self._asr = create_asr_backend(self._config.asr.backend, self._config.asr)
        self._asr.load_model()
        logger.info("Voice engine initialized")

    def start_recording(self) -> None:
        if self._state != EngineState.IDLE:
            logger.warning(f"Cannot start recording in state: {self._state}")
            return

        self._set_state(EngineState.RECORDING)
        self._recorder.start_recording()
        logger.info("Recording started")

    def stop_and_recognize(self) -> None:
        if self._state != EngineState.RECORDING:
            return

        self._set_state(EngineState.PROCESSING)
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

    def _process_audio(self, audio_data: bytes) -> None:
        try:
            result_text = asyncio.run(self._async_recognize(audio_data))
            processed = self._text_processor.process(result_text)

            if processed:
                self._output_text(processed)
                if self._on_result:
                    self._on_result(processed)
                logger.info(f"Recognition result: {processed}")
            else:
                logger.info("No speech detected")

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
