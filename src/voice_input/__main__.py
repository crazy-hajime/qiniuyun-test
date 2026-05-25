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
    parser.add_argument("--device", "-d", type=int, default=None, help="GPU设备ID (0=auto检测)")
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
        if args.device is not None:
            config.asr.funasr.device = f"cuda:{args.device}"
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

    print(f"\r  ⏳ 加载模型中...", flush=True)

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

    feature_parts = []
    if config.streaming.enabled:
        feature_parts.append("流式识别")
    if config.polish.enabled:
        feature_parts.append("AI润色")
    feature_str = " | " + " | ".join(feature_parts) if feature_parts else ""

    gpu_info = ""
    try:
        import torch
        if torch.cuda.is_available():
            count = torch.cuda.device_count()
            if count > 0:
                name = torch.cuda.get_device_name(0)
                mem = torch.cuda.mem_get_info(0).total / 1024**3
                gpu_info = f" | GPU ({name}, {mem/1024:.0f}GB)"
    except Exception:
        pass

    _out(f"\r启动完成!{feature_str}{gpu_info}  (按 F9 开始录音, Ctrl+C 退出)\n")
    _last_partial = [""]

    def _on_status(s: EngineState) -> None:
        if s == EngineState.RECORDING:
            _last_partial[0] = ""
            _out("\033[2K\r  录音中...")

    def _on_partial(t: str) -> None:
        if t == _last_partial[0]:
            return
        _last_partial[0] = t
        _out(f"\033[2K\r  {t}")

    def _on_result(t: str) -> None:
        _last_partial[0] = ""
        _out(f"\033[2K\r→ {t}\n")

    def _on_polished(t: str) -> None:
        _out(f"→ {t}\n")

    def _on_error(e: str) -> None:
        _err(f"  错误: {e}")

    engine.set_on_status_change(_on_status)
    engine.set_on_partial(_on_partial)
    engine.set_on_result(_on_result)
    engine.set_on_polished(_on_polished)
    engine.set_on_error(_on_error)

    engine.start_hotkey()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        _out("\r退出语音输入法\n")
    finally:
        engine.stop_hotkey()


if __name__ == "__main__":
    main()