from __future__ import annotations

import logging

from voice_input.config import OutputConfig

logger = logging.getLogger(__name__)


class KeyboardTyper:
    def __init__(self, config: OutputConfig | None = None):
        self._config = config or OutputConfig()

    def output(self, text: str) -> None:
        if not text:
            return

        try:
            import keyboard

            keyboard.write(text, delay=int(self._config.typing_delay * 1000))
            logger.info(f"Typed text: {text[:50]}...")
        except ImportError:
            logger.warning("keyboard module not installed, cannot simulate typing")
            try:
                import pyperclip

                pyperclip.copy(text)
                logger.info("Fallback: copied to clipboard")
            except Exception:
                logger.error("Both keyboard and clipboard output failed")
        except Exception as e:
            logger.error(f"Keyboard typing failed: {e}")
