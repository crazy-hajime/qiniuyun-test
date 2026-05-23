from __future__ import annotations

from voice_input.config import AppConfig, TextConfig
from voice_input.engine import EngineState, VoiceEngine
from voice_input.text.hotwords import HotwordManager
from voice_input.text.processor import TextProcessor


class TestTextProcessor:
    def test_empty_input(self):
        processor = TextProcessor(TextConfig(enable_hotwords=False))
        assert processor.process("") == ""

    def test_strip_trailing_punctuation(self):
        config = TextConfig(
            strip_trailing_punctuation=True,
            merge_single_letters=False,
            enable_hotwords=False,
        )
        processor = TextProcessor(config)
        assert processor.process("你好。") == "你好"
        assert processor.process("你好！") == "你好"
        assert processor.process("你好？") == "你好"
        assert processor.process("你好") == "你好"

    def test_no_strip_punctuation(self):
        config = TextConfig(
            strip_trailing_punctuation=False,
            merge_single_letters=False,
            enable_hotwords=False,
        )
        processor = TextProcessor(config)
        assert processor.process("你好。") == "你好。"

    def test_merge_single_letters(self):
        config = TextConfig(
            strip_trailing_punctuation=False,
            merge_single_letters=True,
            enable_hotwords=False,
        )
        processor = TextProcessor(config)
        result = processor.process("A I 技术")
        assert "AI" in result

    def test_full_pipeline(self):
        config = TextConfig(
            strip_trailing_punctuation=True,
            merge_single_letters=True,
            enable_hotwords=False,
        )
        processor = TextProcessor(config)
        result = processor.process("这是一个 A I 测试。")
        assert "AI" in result
        assert not result.endswith("。")


class TestHotwordManager:
    def test_no_file(self, tmp_path):
        manager = HotwordManager(str(tmp_path / "nonexistent.txt"))
        assert manager.get_hotwords() == []
        assert manager.apply_corrections("test") == "test"

    def test_load_hotwords(self, tmp_path):
        hw_file = tmp_path / "hotwords.txt"
        hw_file.write_text("Python\nChatGPT\n", encoding="utf-8")
        manager = HotwordManager(str(hw_file))
        assert "Python" in manager.get_hotwords()
        assert "ChatGPT" in manager.get_hotwords()

    def test_corrections(self, tmp_path):
        hw_file = tmp_path / "hotwords.txt"
        hw_file.write_text("拆的皮提 -> ChatGPT\n", encoding="utf-8")
        manager = HotwordManager(str(hw_file))
        assert manager.apply_corrections("拆的皮提很好用") == "ChatGPT很好用"

    def test_comments_and_empty_lines(self, tmp_path):
        hw_file = tmp_path / "hotwords.txt"
        hw_file.write_text("# comment\n\nPython\n", encoding="utf-8")
        manager = HotwordManager(str(hw_file))
        assert manager.get_hotwords() == ["Python"]


class TestVoiceEngine:
    def test_initial_state(self):
        config = AppConfig()
        engine = VoiceEngine(config)
        assert engine.state == EngineState.IDLE
        assert not engine.is_recording

    def test_status_callback(self):
        config = AppConfig()
        engine = VoiceEngine(config)
        states = []
        engine.set_on_status_change(lambda s: states.append(s))
        engine._set_state(EngineState.RECORDING)
        assert states == [EngineState.RECORDING]

    def test_result_callback(self):
        config = AppConfig()
        engine = VoiceEngine(config)
        results = []
        engine.set_on_result(lambda t: results.append(t))

    def test_cannot_start_from_recording(self):
        config = AppConfig()
        engine = VoiceEngine(config)
        engine._state = EngineState.RECORDING
        engine.start_recording()
        assert engine.state == EngineState.RECORDING


class TestConfig:
    def test_default_config(self):
        config = AppConfig()
        assert config.audio.sample_rate == 16000
        assert config.asr.backend == "sherpa"
        assert config.hotkey.ptt_key == "f9"

    def test_load_config_missing_file(self):
        config = AppConfig()
        assert config.audio.sample_rate == 16000
