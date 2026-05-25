from __future__ import annotations

import logging

import numpy as np

from voice_input.config import AudioConfig

logger = logging.getLogger(__name__)


class NoiseReducer:
    def __init__(self, config: AudioConfig):
        self._sample_rate = config.sample_rate
        self._enabled = True
        self._noise_profile: np.ndarray | None = None
        self._noise_frames: list[np.ndarray] = []
        self._profile_frames_needed = 8
        self._profile_collected = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def collect_noise_sample(self, frame: np.ndarray) -> None:
        if self._profile_collected:
            return
        self._noise_frames.append(frame)
        if len(self._noise_frames) >= self._profile_frames_needed:
            self._build_profile()

    def _build_profile(self) -> None:
        try:
            from scipy.signal import stft

            all_noise = np.concatenate(self._noise_frames, axis=0)
            if all_noise.ndim > 1:
                all_noise = all_noise[:, 0]
            all_noise = all_noise.astype(np.float64)

            _, _, Zxx = stft(all_noise, fs=self._sample_rate, nperseg=512)
            self._noise_profile = np.mean(np.abs(Zxx) ** 2, axis=1, keepdims=True)
            self._profile_collected = True
            logger.info("Noise profile built from %d frames", len(self._noise_frames))
        except Exception as e:
            logger.warning(f"Failed to build noise profile: {e}")
            self._profile_collected = False
        finally:
            self._noise_frames.clear()

    def process(self, audio: np.ndarray) -> np.ndarray:
        if not self._enabled or not self._profile_collected or self._noise_profile is None:
            return audio

        try:
            from scipy.signal import istft, stft

            if audio.ndim > 1:
                audio = audio[:, 0]

            audio_float = audio.astype(np.float64)

            _, _, Zxx = stft(audio_float, fs=self._sample_rate, nperseg=512)

            signal_power = np.abs(Zxx) ** 2
            noise_power = self._noise_profile

            if noise_power.shape[0] != signal_power.shape[0]:
                return audio

            alpha = 2.0
            gain = np.maximum(signal_power - alpha * noise_power, 0) / (signal_power + 1e-10)
            gain = np.sqrt(gain)
            gain = np.maximum(gain, 0.1)

            Zxx_clean = Zxx * gain

            _, audio_clean = istft(Zxx_clean, fs=self._sample_rate, nperseg=512)

            if len(audio_clean) > len(audio):
                audio_clean = audio_clean[:len(audio)]
            elif len(audio_clean) < len(audio):
                audio_clean = np.pad(audio_clean, (0, len(audio) - len(audio_clean)))

            peak_in = np.max(np.abs(audio_float)) + 1e-10
            peak_out = np.max(np.abs(audio_clean)) + 1e-10
            audio_clean = audio_clean * (peak_in / peak_out)

            return audio_clean.astype(audio.dtype)

        except Exception as e:
            logger.warning(f"Noise reduction failed: {e}")
            return audio

    def reset(self) -> None:
        self._noise_profile = None
        self._noise_frames.clear()
        self._profile_collected = False
