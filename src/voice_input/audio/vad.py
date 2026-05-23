from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from voice_input.config import AudioConfig

logger = logging.getLogger(__name__)


class VoiceActivityDetector:
    def __init__(self, config: AudioConfig | None = None):
        self._config = config or AudioConfig()
        self._model: Any = None
        self._model_loaded = False

    def load_model(self, model_path: str | Path | None = None) -> None:
        try:
            import sherpa_onnx

            if model_path is None:
                model_path = (
                    Path.home() / ".cache" / "sherpa-onnx" / "silero_vad.onnx"
                )
            model_path = Path(model_path)

            if not model_path.exists():
                logger.warning(
                    f"VAD model not found at {model_path}, VAD disabled"
                )
                return

            self._model = sherpa_onnx.VoiceActivityDetector(
                sherpa_onnx.VadModelConfig(
                    silero_vad=sherpa_onnx.SileroVadModelConfig(str(model_path)),
                    sample_rate=self._config.sample_rate,
                ),
                buffer_size_in_seconds=30,
            )
            self._model_loaded = True
            logger.info("VAD model loaded")
        except ImportError:
            logger.warning("sherpa-onnx not installed, VAD disabled")
        except Exception as e:
            logger.warning(f"Failed to load VAD model: {e}")

    def detect_segments(
        self, audio_data: np.ndarray, sample_rate: int | None = None
    ) -> list[tuple[int, int]]:
        if not self._model_loaded or self._model is None:
            return [(0, len(audio_data))]

        try:
            sr = sample_rate or self._config.sample_rate
            if audio_data.ndim > 1:
                audio_data = audio_data[:, 0]

            float_data = audio_data.astype(np.float32) / 32768.0

            stream = self._model.create_stream()
            stream.accept_waveform(sr, float_data)

            segments = []
            while True:
                segs = self._model.detect(stream)
                if not segs:
                    break
                for seg in segs:
                    start_sample = int(seg.start * sr)
                    end_sample = int(seg.end * sr)
                    segments.append((start_sample, end_sample))

            if not segments:
                return [(0, len(audio_data))]

            return segments
        except Exception as e:
            logger.warning(f"VAD detection failed: {e}, returning full audio")
            return [(0, len(audio_data))]

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        if not self._model_loaded:
            level = float(np.abs(audio_chunk).mean())
            return level > self._config.silence_threshold

        try:
            if audio_chunk.ndim > 1:
                audio_chunk = audio_chunk[:, 0]
            float_data = audio_chunk.astype(np.float32) / 32768.0

            stream = self._model.create_stream()
            stream.accept_waveform(self._config.sample_rate, float_data)

            segs = self._model.detect(stream)
            return len(segs) > 0
        except Exception:
            level = float(np.abs(audio_chunk).mean())
            return level > self._config.silence_threshold
