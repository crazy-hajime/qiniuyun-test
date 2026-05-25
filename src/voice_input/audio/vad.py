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
        self._energy_threshold = config.silence_threshold if config else 0.01

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
                    f"VAD model not found at {model_path}, using energy-based VAD"
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
            logger.info("VAD model loaded (sherpa-onnx)")
        except ImportError:
            logger.info("sherpa-onnx not installed, using energy-based VAD")
        except Exception as e:
            logger.warning(f"Failed to load VAD model: {e}, using energy-based VAD")

    def detect_segments(
        self, audio_data: np.ndarray, sample_rate: int | None = None
    ) -> list[tuple[int, int]]:
        if not self._model_loaded or self._model is None:
            return self._energy_detect_segments(audio_data, sample_rate)

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
                return self._energy_detect_segments(audio_data, sample_rate)

            return segments
        except Exception as e:
            logger.warning(f"VAD detection failed: {e}")
            return self._energy_detect_segments(audio_data, sample_rate)

    def _energy_detect_segments(
        self, audio_data: np.ndarray, sample_rate: int | None = None
    ) -> list[tuple[int, int]]:
        sr = sample_rate or self._config.sample_rate
        if audio_data.ndim > 1:
            audio_data = audio_data[:, 0]

        float_data = np.abs(audio_data.astype(np.float64))
        frame_size = int(sr * 0.03)
        if frame_size == 0:
            return [(0, len(audio_data))]

        threshold = self._energy_threshold * 32768 * 0.5

        n_frames = len(float_data) // frame_size
        if n_frames == 0:
            return [(0, len(audio_data))]

        is_speech = np.zeros(n_frames, dtype=bool)
        for i in range(n_frames):
            start = i * frame_size
            end = start + frame_size
            frame_energy = np.mean(float_data[start:end])
            is_speech[i] = frame_energy > threshold

        pad_frames = int(sr * 0.2 / frame_size)
        speech_padded = is_speech.copy()
        for i in range(n_frames):
            if is_speech[i]:
                start_pad = max(0, i - pad_frames)
                end_pad = min(n_frames, i + pad_frames + 1)
                speech_padded[start_pad:end_pad] = True

        segments = []
        in_segment = False
        seg_start = 0
        for i in range(n_frames):
            if speech_padded[i] and not in_segment:
                in_segment = True
                seg_start = i * frame_size
            elif not speech_padded[i] and in_segment:
                in_segment = False
                seg_end = i * frame_size
                min_len = int(sr * 0.1)
                if seg_end - seg_start >= min_len:
                    segments.append((seg_start, seg_end))

        if in_segment:
            seg_end = n_frames * frame_size
            min_len = int(sr * 0.1)
            if seg_end - seg_start >= min_len:
                segments.append((seg_start, seg_end))

        if not segments:
            return [(0, len(audio_data))]

        return segments

    def trim_silence(self, audio_data: np.ndarray, sample_rate: int | None = None) -> np.ndarray:
        if audio_data.ndim > 1:
            audio_data_1d = audio_data[:, 0]
        else:
            audio_data_1d = audio_data

        segments = self.detect_segments(audio_data_1d, sample_rate)

        if not segments:
            return audio_data

        total_speech_samples = sum(end - start for start, end in segments)
        total_samples = len(audio_data_1d)

        if total_speech_samples >= total_samples * 0.95:
            return audio_data

        trimmed_parts = []
        for start, end in segments:
            actual_end = min(end, len(audio_data_1d))
            if audio_data.ndim > 1:
                trimmed_parts.append(audio_data[start:actual_end])
            else:
                trimmed_parts.append(audio_data[start:actual_end])

        if not trimmed_parts:
            return audio_data

        trimmed = np.concatenate(trimmed_parts, axis=0)
        logger.info(
            f"VAD trimmed: {total_samples} -> {len(trimmed)} samples "
            f"({len(segments)} segments, saved {(1 - len(trimmed)/total_samples)*100:.0f}%)"
        )
        return trimmed

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
