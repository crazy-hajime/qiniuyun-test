from __future__ import annotations

import argparse
import json
import logging
import sys

from voice_input.config import load_config
from voice_input.engine import VoiceEngine

logger = logging.getLogger(__name__)


def cmd_devices(args) -> None:
    from voice_input.audio.recorder import AudioRecorder

    recorder = AudioRecorder()
    devices = recorder.list_devices()
    print(json.dumps(devices, ensure_ascii=False, indent=2))


def cmd_transcribe(args) -> None:
    config = load_config(args.config)
    if args.backend:
        config.asr.backend = args.backend

    engine = VoiceEngine(config)
    engine.initialize()

    try:
        result = engine.recognize_file(args.input)
        if args.json:
            output = {
                "input": args.input,
                "text": result,
            }
            print(json.dumps(output, ensure_ascii=False))
        else:
            print(result)
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_listen(args) -> None:
    import time

    config = load_config(args.config)
    if args.backend:
        config.asr.backend = args.backend

    engine = VoiceEngine(config)
    engine.initialize()

    print("按 Enter 开始录音，再按 Enter 停止并识别...")
    input()

    engine.start_recording()
    print("录音中...")

    if args.duration:
        time.sleep(args.duration)
    else:
        input("按 Enter 停止录音...")

    engine.stop_and_recognize()

    time.sleep(0.5)


def cmd_download(args) -> None:
    from voice_input.asr.sherpa_backend import (
        DOWNLOAD_MIRRORS,
        MODEL_CACHE_DIR,
        SENSEVOICE_MODEL_DIR_NAME,
        SherpaBackend,
    )

    target_dir = MODEL_CACHE_DIR / SENSEVOICE_MODEL_DIR_NAME
    if target_dir.exists() and not args.force:
        print(f"模型已存在: {target_dir}")
        print("使用 --force 强制重新下载")
        return

    if args.mirror:
        mirrors = [(name, url) for name, url in DOWNLOAD_MIRRORS if name == args.mirror]
        if not mirrors:
            print(f"未找到镜像源: {args.mirror}")
            print(f"可用镜像: {', '.join(n for n, _ in DOWNLOAD_MIRRORS)}")
            sys.exit(1)
    else:
        mirrors = DOWNLOAD_MIRRORS

    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    backend = SherpaBackend.__new__(SherpaBackend)

    for mirror_name, url in mirrors:
        print(f"\n从 {mirror_name} 下载 SenseVoice 模型...")
        try:
            if url.startswith("modelscope:"):
                backend._download_from_modelscope(url)
            else:
                backend._download_from_url(url)
            print(f"模型已安装到: {MODEL_CACHE_DIR}")
            return
        except Exception as e:
            print(f"\n从 {mirror_name} 下载失败: {e}")
            continue

    print("\n所有镜像源下载失败，请手动下载：")
    print("  推荐方式 - pip install modelscope 后运行：")
    print("    python -c \"from modelscope import snapshot_download; "
          "snapshot_download('pengzhendong/sherpa-onnx-sense-voice-zh-en-ja-ko-yue')\"")
    for mirror_name, url in DOWNLOAD_MIRRORS:
        print(f"  {mirror_name}: {url}")
    print(f"解压到: {MODEL_CACHE_DIR}")
    sys.exit(1)


def _download_progress(block_num: int, block_size: int, total_size: int) -> None:
    downloaded = block_num * block_size
    if total_size > 0:
        percent = min(downloaded / total_size * 100, 100)
        mb_downloaded = downloaded / (1024 * 1024)
        mb_total = total_size / (1024 * 1024)
        bar_len = 40
        filled = int(bar_len * percent / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        sys.stdout.write(
            f"\r  [{bar}] {percent:5.1f}% "
            f"({mb_downloaded:.1f}/{mb_total:.1f} MB)"
        )
        sys.stdout.flush()
    else:
        mb_downloaded = downloaded / (1024 * 1024)
        sys.stdout.write(f"\r  已下载: {mb_downloaded:.1f} MB")
        sys.stdout.flush()


def cmd_doctor(args) -> None:
    config = load_config(args.config)
    checks = []

    try:
        import numpy

        checks.append({
            "check": "numpy",
            "status": "ok",
            "detail": f"version {numpy.__version__}",
        })
    except ImportError as e:
        checks.append({"check": "numpy", "status": "fail", "error": str(e)})

    try:
        import sounddevice

        checks.append({
            "check": "sounddevice",
            "status": "ok",
            "detail": f"version {sounddevice.__version__}",
        })
    except ImportError as e:
        checks.append({"check": "sounddevice", "status": "fail", "error": str(e)})

    try:
        import scipy

        checks.append({
            "check": "scipy",
            "status": "ok",
            "detail": f"version {scipy.__version__}",
        })
    except ImportError as e:
        checks.append({"check": "scipy", "status": "fail", "error": str(e)})

    try:
        import pyperclip  # noqa: F401

        checks.append({"check": "pyperclip", "status": "ok"})
    except ImportError as e:
        checks.append({"check": "pyperclip", "status": "fail", "error": str(e)})

    backend = config.asr.backend
    if backend == "funasr":
        try:
            import funasr_onnx  # noqa: F401

            checks.append({
                "check": "funasr_onnx",
                "status": "ok",
                "detail": f"version {funasr_onnx.__version__}",
            })
        except ImportError as e:
            checks.append({"check": "funasr_onnx", "status": "fail", "error": str(e)})
    elif backend == "sherpa":
        try:
            import sherpa_onnx  # noqa: F401

            checks.append({"check": "sherpa_onnx", "status": "ok"})
        except ImportError as e:
            checks.append({"check": "sherpa_onnx", "status": "fail", "error": str(e)})

    try:
        from voice_input.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        devices = recorder.list_devices()
        checks.append({
            "check": "microphone",
            "status": "ok",
            "detail": f"{len(devices)} device(s) found",
        })
    except Exception as e:
        checks.append({"check": "microphone", "status": "fail", "error": str(e)})

    try:
        engine = VoiceEngine(config)
        engine.initialize()
        checks.append({"check": "ASR model load", "status": "ok"})
    except Exception as e:
        checks.append({"check": "ASR model load", "status": "fail", "error": str(e)})

    all_ok = all(c["status"] == "ok" for c in checks)
    result = {"ok": all_ok, "checks": checks}
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not all_ok:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="voice-input-cli",
        description="语音输入法命令行工具",
    )
    parser.add_argument("--config", "-c", help="配置文件路径", default=None)
    parser.add_argument("--verbose", "-v", help="详细日志", action="store_true")

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    devices_parser = subparsers.add_parser("devices", help="列出可用麦克风设备")
    devices_parser.set_defaults(func=cmd_devices)

    transcribe_parser = subparsers.add_parser("transcribe", help="识别音频文件")
    transcribe_parser.add_argument("input", help="音频文件路径")
    transcribe_parser.add_argument("--backend", "-b", help="ASR后端", default=None)
    transcribe_parser.add_argument("--json", help="JSON输出", action="store_true")
    transcribe_parser.set_defaults(func=cmd_transcribe)

    listen_parser = subparsers.add_parser("listen", help="麦克风录音识别")
    listen_parser.add_argument("--backend", "-b", help="ASR后端", default=None)
    listen_parser.add_argument(
        "--duration", "-d", help="录音时长（秒）", type=float, default=None
    )
    listen_parser.set_defaults(func=cmd_listen)

    download_parser = subparsers.add_parser("download", help="下载ASR模型")
    download_parser.add_argument(
        "--mirror", "-m",
        help="镜像源 (GitHub/HuggingFace)",
        default=None,
    )
    download_parser.add_argument(
        "--force", "-f",
        help="强制重新下载",
        action="store_true",
    )
    download_parser.set_defaults(func=cmd_download)

    doctor_parser = subparsers.add_parser("doctor", help="检查环境依赖")
    doctor_parser.set_defaults(func=cmd_doctor)

    args = parser.parse_args()

    if args.verbose:
        log_fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        logging.basicConfig(level=logging.DEBUG, format=log_fmt)
    else:
        logging.basicConfig(level=logging.WARNING)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
