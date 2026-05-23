from voice_input.asr.base import ASRBase
from voice_input.asr.cloud_backend import CloudBackend
from voice_input.asr.funasr_backend import FunASRBackend
from voice_input.asr.sherpa_backend import SherpaBackend

__all__ = ["ASRBase", "FunASRBackend", "SherpaBackend", "CloudBackend"]


def create_asr_backend(backend_name: str, config):
    if backend_name == "funasr":
        return FunASRBackend(config)
    elif backend_name == "sherpa":
        return SherpaBackend(config)
    elif backend_name == "cloud":
        return CloudBackend(config)
    else:
        raise ValueError(f"Unknown ASR backend: {backend_name}")
