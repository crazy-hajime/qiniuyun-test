from __future__ import annotations

import io
import logging
import threading
import time
from collections.abc import Callable

import numpy as np
import soundfile as sf

from voice_input.config import AudioConfig
from voice_input.audio.noise_reducer import NoiseReducer

logger = logging.getLogger(__name__)

_sd = None

def _get_sd():
    global _sd
    if _sd is None:
        import sounddevice as sd
        _sd = sd
    return _sd


class AudioRecorder:
    def __init__(self, config: AudioConfig | None = None):
        self._config = config or AudioConfig()
        self._buffer: list[np.ndarray] = []
        self._is_recording = False
        self._stream = None
        self._lock = threading.Lock()
        self._start_time: float = 0
        self._silence_start: float | None = None
        self._on_silence_callback: Callable[[], None] | None = None
        self._on_level_callback: Callable[[float], None] | None = None
        self._noise_reducer: NoiseReducer | None = None
        if self._config.enable_noise_reduction:
            self._noise_reducer = NoiseReducer(self._config)

    def set_on_silence(self, callback: Callable[[], None]) -> None:
        self._on_silence_callback = callback

    def set_on_level(self, callback: Callable[[float], None]) -> None:
        self._on_level_callback = callback

    def start_recording(self) -> None:
        with self._lock:
            if self._is_recording:
                logger.warning("Already recording")
                return
            self._buffer = []
            self._is_recording = True
            self._start_time = time.time()
            self._silence_start = None

        self._stream = _get_sd().InputStream(
            samplerate=self._config.sample_rate,
            channels=self._config.channels,
            dtype=self._config.dtype,
            blocksize=self._config.block_size,
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.info("Recording started")

    def stop_recording(self) -> bytes:
        with self._lock:
            if not self._is_recording:
                logger.warning("Not recording")
                return b""
            self._is_recording = False

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        audio_data = self._get_wav_bytes()
        duration = time.time() - self._start_time
        logger.info(f"Recording stopped, duration: {duration:.2f}s, size: {len(audio_data)} bytes")
        return audio_data

    def is_recording(self) -> bool:
        return self._is_recording

    def get_audio_data(self) -> bytes:
        return self._get_wav_bytes()

    def get_audio_size(self) -> int:
        if not self._buffer:
            return 0
        audio = np.concatenate(self._buffer, axis=0)
        return audio.nbytes

    def get_duration(self) -> float:
        if not self._is_recording and self._start_time == 0:
            return 0.0
        if self._is_recording:
            return time.time() - self._start_time
        return 0.0

    def list_devices(self) -> list[dict]:
        devices = _get_sd().query_devices()
        result = []
        for i, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                result.append({
                    "index": i,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "sample_rate": int(dev["default_samplerate"]),
                })
        return result

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info, status
    ) -> None:
        if status:
            logger.warning(f"Audio callback status: {status}")

        with self._lock:
            if not self._is_recording:
                return
            self._buffer.append(indata.copy())

        elapsed = time.time() - self._start_time

        if self._noise_reducer and not self._noise_reducer._profile_collected:
            level = float(np.abs(indata).mean())
            if level < self._config.silence_threshold * 3:
                self._noise_reducer.collect_noise_sample(indata)

        if elapsed > self._config.max_duration:
            logger.info("Max duration reached, stopping")
            if self._on_silence_callback:
                self._on_silence_callback()
            return

        level = float(np.abs(indata).mean())
        if self._on_level_callback:
            self._on_level_callback(level)

        if level < self._config.silence_threshold:
            if self._silence_start is None:
                self._silence_start = time.time()
            elif time.time() - self._silence_start > self._config.silence_duration:
                if elapsed > 1.0 and self._on_silence_callback:
                    logger.info("Silence detected, triggering callback")
                    self._on_silence_callback()
        else:
            self._silence_start = None

    def _get_wav_bytes(self) -> bytes:
        if not self._buffer:
            return b""

        audio = np.concatenate(self._buffer, axis=0)

        if self._noise_reducer and self._noise_reducer._profile_collected:
            audio = self._noise_reducer.process(audio)

        buf = io.BytesIO()
        sf.write(buf, audio, self._config.sample_rate, format='WAV', subtype='PCM_16')
        return buf.getvalue()
