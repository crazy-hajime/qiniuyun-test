from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time

if __name__ == "__main__":
    _src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _src_dir not in sys.path:
        sys.path.insert(0, os.path.dirname(_src_dir))

from voice_input.config import load_config
from voice_input.engine import EngineState, VoiceEngine


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.ERROR
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.basicConfig(level=level, handlers=[handler], force=True)
    os.environ["MODELSCOPE_DISABLE_REMOTE"] = "1"
    os.environ["TQDM_DISABLE"] = "1"


def main() -> None:
    parser = argparse.ArgumentParser(description="语音输入法 - 按F9开始录音")
    parser.add_argument("--config", "-c", default=None, help="配置文件路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细日志")
    parser.add_argument("--no-gui", action="store_true", help="无GUI模式")
    parser.add_argument("--backend", "-b", default=None, help="ASR后端")
    parser.add_argument("--device", "-d", type=int, default=None, help="GPU设备ID")
    parser.add_argument("--no-stream", action="store_true", help="关闭流式识别")
    parser.add_argument("--polish", action="store_true", help="开启AI润色")
    parser.add_argument("--style", default=None, choices=["auto", "formal", "casual", "technical"], help="润色风格")
    args = parser.parse_args()
    setup_logging(args.verbose)

    _real_stdout = sys.stdout
    _real_stderr = sys.stderr

    def _err(msg):
        _real_stderr.write(msg + "\n")
        _real_stderr.flush()

    def _out(msg):
        _real_stdout.write(msg)
        _real_stdout.flush()

    print("正在启动语音输入法...", end="", flush=True)

    config = None
    engine = None

    try:
        config = load_config(args.config)
        if args.backend:
            config.asr.backend = args.backend
        if args.no_stream:
            config.streaming.enabled = False
        if args.polish:
            config.polish.enabled = True
        if args.style:
            config.polish.style = args.style
        engine = VoiceEngine(config)
    except Exception as e:
        import traceback
        _err("\n❌ 启动失败:")
        _err(str(e))
        traceback.print_exc(file=_real_stderr)
        sys.exit(1)

    features = []
    if config.streaming.enabled:
        features.append("流式识别")
    if config.polish.enabled:
        features.append(f"AI润色({config.polish.style})")
    feature_str = (" | " + " · ".join(features)) if features else ""

    print(f"\r  ⏳ 加载模型中 (约需10-20秒，请耐心等待)...", flush=True)

    _interrupted = [False]
    _orig_sigint = signal.getsignal(signal.SIGINT)

    def _sigint_handler(sig, frame):
        _interrupted[0] = True

    signal.signal(signal.SIGINT, _sigint_handler)

    try:
        engine.initialize()
    except KeyboardInterrupt:
        if _interrupted[0]:
            _out("\r❌ 已取消\n")
            sys.exit(1)
        raise
    except Exception as e:
        import traceback
        _out("\r❌ 模型加载失败\n")
        _err(str(e))
        traceback.print_exc(file=_real_stderr)
        sys.exit(1)
    finally:
        signal.signal(signal.SIGINT, _orig_sigint)

    _out(f"\r✅ 启动完成!{feature_str}  (按 F9 开始录音, Ctrl+C 退出)\n")

    spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    si = [0]
    recording = [False]
    partial_shown = [False]

    def _write_status():
        if recording[0]:
            s = spinner[si[0] % len(spinner)]
            si[0] += 1
            _out(f"\r  🎤 {s} 录音中 ...   ")
        else:
            _out("\r" + " " * 35 + "\r")

    def on_status(state):
        recording[0] = state == EngineState.RECORDING
        if state == EngineState.PROCESSING:
            partial_shown[0] = False
        _write_status()

    def on_partial(text):
        recording[0] = True
        partial_shown[0] = True
        _out(f"\r  🎤 ⠿ {text}   ")

    def on_result(text):
        recording[0] = False
        if partial_shown[0]:
            _out(f"\r  ✅ {text}\n")
        else:
            _write_status()
            _out(text + "\n")
        partial_shown[0] = False

    def on_polished(text):
        _out(f"  ✨ {text}\n")

    def on_error(msg):
        _write_status()
        _err("❌ " + msg)
        partial_shown[0] = False

    engine.set_on_status_change(on_status)
    engine.set_on_partial(on_partial)
    engine.set_on_result(on_result)
    engine.set_on_polished(on_polished)
    engine.set_on_error(on_error)

    try:
        engine.start_hotkey()
    except Exception as e:
        _err("❌ 热键启动失败: " + str(e))
        sys.exit(1)

    try:
        while True:
            _write_status()
            time.sleep(0.08)
    except KeyboardInterrupt:
        _out("\n已退出。\n")
    finally:
        engine.stop_hotkey()


if __name__ == "__main__":
    main()
