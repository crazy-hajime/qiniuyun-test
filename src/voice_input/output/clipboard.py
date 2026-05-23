from __future__ import annotations

import logging
import time

import pyperclip

from voice_input.config import OutputConfig

logger = logging.getLogger(__name__)


class ClipboardOutput:
    def __init__(self, config: OutputConfig | None = None):
        self._config = config or OutputConfig()

    def output(self, text: str) -> None:
        if not text:
            return

        try:
            pyperclip.copy(text)
            logger.info(f"Copied to clipboard: {text[:50]}...")

            time.sleep(self._config.clipboard_delay)

            try:
                import keyboard

                keyboard.send("ctrl+v")
                logger.debug("Pasted via Ctrl+V")
            except ImportError:
                logger.warning("keyboard module not installed, text copied to clipboard only")
        except Exception as e:
            logger.error(f"Clipboard output failed: {e}")
