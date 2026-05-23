from __future__ import annotations

import argparse
import logging
import os
import sys
import time

if __name__ == "__main__":
    _src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _src_dir not in sys.path:
        sys.path.insert(0, os.path.dirname(_src_dir))

from voice_input.config import load_config
from voice_input.engine import EngineState, VoiceEngine


class _NullWriter:
    def write(self, *a, **k): pass
    def flush(self): pass


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
    parser.add_argument("--backend", "-b", default=None, help="ASR后端 (funasr/sherpa/cloud)")
    parser.add_argument("--device", "-d", type=int, default=None, help="GPU设备ID")
    args = parser.parse_args()
    setup_logging(args.verbose)

    _real_stdout = sys.stdout
    _real_stderr = sys.stderr

    def _err(msg):
        _real_stderr.write(msg + "\n")
        _real_stderr.flush()

    print("正在启动语音输入法...", end="", flush=True)

    config = None
    engine = None

    try:
        config = load_config(args.config)
        if args.backend:
            config.asr.backend = args.backend
        engine = VoiceEngine(config)
        engine.initialize()
    except Exception as e:
        import traceback
        _err("\n❌ 启动失败:")
        _err(str(e))
        traceback.print_exc(file=_real_stderr)
        sys.exit(1)

    print(" OK  (按 F9 开始录音)", flush=True)

    spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    si = [0]
    recording = [False]

    def _write_status():
        if recording[0]:
            s = spinner[si[0] % len(spinner)]
            si[0] += 1
            _real_stdout.write(f"\r  🎤 {s} 录音中 ...   ")
        else:
            _real_stdout.write("\r" + " " * 30 + "\r")
        _real_stdout.flush()

    def on_status(state):
        recording[0] = state == EngineState.RECORDING
        _write_status()

    def on_result(text):
        recording[0] = False
        _write_status()
        _real_stdout.write(text + "\n")
        _real_stdout.flush()

    def on_error(msg):
        _write_status()
        _err("❌ " + msg)

    engine.set_on_status_change(on_status)
    engine.set_on_result(on_result)
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
        _real_stdout.write("\n已退出。\n")
        _real_stdout.flush()
    finally:
        engine.stop_hotkey()


if __name__ == "__main__":
    main()
