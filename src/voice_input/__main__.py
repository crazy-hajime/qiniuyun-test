from __future__ import annotations

import argparse
import logging
import os
import sys
import time

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", "-c", default=None)
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--no-gui", action="store_true")
    parser.add_argument("--backend", "-b", default=None)
    parser.add_argument("--device", "-d", type=int, default=None)
    args = parser.parse_args()
    setup_logging(args.verbose)

    _real_stdout = sys.stdout
    _real_stderr = sys.stderr
    sys.stdout = _NullWriter()
    sys.stderr = _NullWriter()

    config = load_config(args.config)
    if args.backend:
        config.asr.backend = args.backend

    engine = VoiceEngine(config)

    spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    si = [0]
    recording = [False]
    ready = [False]

    def _write_status():
        if not ready[0]:
            return
        if recording[0]:
            s = spinner[si[0] % len(spinner)]
            si[0] += 1
            _real_stdout.write("\r  \U0001F3A4 %s 录音中 ...   " % s)
        else:
            _real_stdout.write("\r" + " " * 30 + "\r")
        _real_stdout.flush()

    def on_status(state):
        recording[0] = state == EngineState.RECORDING
        _write_status()

    def on_result(text):
        _write_status()
        recording[0] = False
        _real_stdout.write("%s\n" % text)
        _real_stdout.flush()

    def on_error(msg):
        _write_status()
        _real_stderr.write("\u274C %s\n" % msg)
        _real_stderr.flush()

    engine.set_on_status_change(on_status)
    engine.set_on_result(on_result)
    engine.set_on_error(on_error)

    try:
        engine.initialize()
        ready[0] = True
    except Exception as e:
        sys.stdout = _real_stdout
        sys.stderr = _real_stderr
        print("\u274C 启动失败: %s" % e, file=sys.stderr)
        sys.exit(1)

    sys.stdout = _real_stdout
    sys.stderr = _real_stderr

    engine.start_hotkey()

    try:
        while True:
            _write_status()
            time.sleep(0.08)
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop_hotkey()


if __name__ == "__main__":
    main()
