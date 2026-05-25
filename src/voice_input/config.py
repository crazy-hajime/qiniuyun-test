from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path.home() / ".voice-input"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.yaml"


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    channels: int = 1
    block_size: int = 1024
    dtype: str = "int16"
    silence_threshold: float = 0.01
    silence_duration: float = 3.0
    max_duration: int = 60
    enable_noise_reduction: bool = True
    noise_profile_frames: int = 8


@dataclass
class FunASRConfig:
    model: str = "iic/SenseVoiceSmall"
    quantize: bool = True
    hotwords_file: str = "hotwords.txt"
    enable_punctuation: bool = True
    language: str = "zh"
    device: str = "auto"


@dataclass
class SherpaConfig:
    model_dir: str = ""
    language: str = "auto"
    provider: str = "cpu"


@dataclass
class CloudConfig:
    provider: str = ""
    api_key: str = ""
    endpoint: str = ""


@dataclass
class ASRConfig:
    backend: str = "funasr"
    funasr: FunASRConfig = field(default_factory=FunASRConfig)
    sherpa: SherpaConfig = field(default_factory=SherpaConfig)
    cloud: CloudConfig = field(default_factory=CloudConfig)


@dataclass
class TextConfig:
    strip_trailing_punctuation: bool = True
    merge_single_letters: bool = True
    enable_traditional_chinese: bool = False
    enable_hotwords: bool = True
    hotwords_file: str = "hotwords.txt"


@dataclass
class OutputConfig:
    mode: str = "both"
    clipboard_delay: float = 0.1
    typing_delay: float = 0.02


@dataclass
class HotkeyConfig:
    ptt_key: str = "f9"
    toggle_key: str = "alt_r"
    mode: str = "ptt"


@dataclass
class GUIConfig:
    show_tray: bool = True
    show_indicator: bool = True
    indicator_opacity: float = 0.8


@dataclass
class OllamaConfig:
    model: str = "qwen2.5:0.5b"
    host: str = "http://localhost:11434"


@dataclass
class OpenAIConfig:
    model: str = "gpt-3.5-turbo"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"


@dataclass
class PolishConfig:
    enabled: bool = False
    backend: str = "ollama"
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    style: str = "auto"


@dataclass
class StreamingConfig:
    enabled: bool = True
    interval: float = 0.3
    show_partial: bool = True


@dataclass
class AppConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    asr: ASRConfig = field(default_factory=ASRConfig)
    text: TextConfig = field(default_factory=TextConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    gui: GUIConfig = field(default_factory=GUIConfig)
    polish: PolishConfig = field(default_factory=PolishConfig)
    streaming: StreamingConfig = field(default_factory=StreamingConfig)


def _deep_update(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_update(result[key], value)
        else:
            result[key] = value
    return result


def _dict_to_dataclass(cls: type, data: dict[str, Any]) -> Any:
    if not isinstance(data, dict):
        return data

    defaults = cls()
    kwargs = {}
    for name in cls.__dataclass_fields__:
        default_val = getattr(defaults, name)
        if name in data:
            value = data[name]
            if hasattr(default_val, "__dataclass_fields__") and isinstance(value, dict):
                kwargs[name] = _dict_to_dataclass(type(default_val), value)
            else:
                kwargs[name] = value
        else:
            kwargs[name] = default_val
    return cls(**kwargs)


def load_config(config_path: Path | str | None = None) -> AppConfig:
    defaults = AppConfig()

    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    config_path = Path(config_path)
    if not config_path.exists():
        search_paths = [
            Path("config.yaml"),
            Path(__file__).parent.parent.parent / "config.yaml",
        ]
        for candidate in search_paths:
            if candidate.exists():
                config_path = candidate
                break
        else:
            return defaults

    with open(config_path, encoding="utf-8") as f:
        user_data = yaml.safe_load(f) or {}

    if not user_data:
        return defaults

    return _dict_to_dataclass(AppConfig, user_data)


def save_config(config: AppConfig, config_path: Path | str | None = None) -> None:
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    def _dataclass_to_dict(obj: Any) -> Any:
        if hasattr(obj, "__dataclass_fields__"):
            return {k: _dataclass_to_dict(v) for k, v in obj.__dict__.items()}
        return obj

    data = _dataclass_to_dict(config)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
