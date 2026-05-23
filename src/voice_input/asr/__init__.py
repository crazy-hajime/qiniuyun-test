from voice_input.asr.base import ASRBase

__all__ = ["ASRBase", "create_asr_backend"]


def _get_backend_class(backend_name: str):
    if backend_name == "funasr":
        from voice_input.asr.funasr_backend import FunASRBackend
        return FunASRBackend
    elif backend_name == "sherpa":
        from voice_input.asr.sherpa_backend import SherpaBackend
        return SherpaBackend
    elif backend_name == "cloud":
        from voice_input.asr.cloud_backend import CloudBackend
        return CloudBackend
    else:
        raise ValueError(f"Unknown ASR backend: {backend_name}")


def create_asr_backend(backend_name: str, config):
    cls = _get_backend_class(backend_name)
    return cls(config)
