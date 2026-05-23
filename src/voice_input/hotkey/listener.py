from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from voice_input.config import HotkeyConfig

logger = logging.getLogger(__name__)


class HotkeyListener:
    def __init__(self, config: HotkeyConfig | None = None):
        self._config = config or HotkeyConfig()
        self._running = False
        self._on_ptt_press: Callable[[], None] | None = None
        self._on_ptt_release: Callable[[], None] | None = None
        self._on_toggle: Callable[[], None] | None = None
        self._listener = None
        self._thread: threading.Thread | None = None
        self._toggle_active = False
        self._ptt_held = False
        self._toggle_fired = False

    def start(
        self,
        on_ptt_press: Callable[[], None],
        on_ptt_release: Callable[[], None],
        on_toggle: Callable[[], None],
    ) -> None:
        self._on_ptt_press = on_ptt_press
        self._on_ptt_release = on_ptt_release
        self._on_toggle = on_toggle
        self._running = True

        try:
            self._start_pynput()
        except ImportError:
            logger.info("pynput not available, trying keyboard module")
            try:
                self._start_keyboard()
            except ImportError:
                logger.warning(
                    "No hotkey library available. "
                    "Install pynput or keyboard: pip install pynput"
                )

    def stop(self) -> None:
        self._running = False
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def _start_pynput(self) -> None:
        from pynput import keyboard as kb

        ptt_key = self._parse_pynput_key(self._config.ptt_key)
        toggle_key = self._parse_pynput_key(self._config.toggle_key)

        def on_press(key):
            if not self._running:
                return
            try:
                if key == ptt_key:
                    if not self._ptt_held:
                        self._ptt_held = True
                        if self._on_ptt_press:
                            self._on_ptt_press()
                elif key == toggle_key:
                    if not self._toggle_fired:
                        self._toggle_fired = True
                        if self._on_toggle:
                            self._on_toggle()
            except Exception as e:
                logger.error(f"Hotkey press error: {e}")

        def on_release(key):
            if not self._running:
                return False
            try:
                if key == ptt_key:
                    self._ptt_held = False
                    if self._on_ptt_release:
                        self._on_ptt_release()
                elif key == toggle_key:
                    self._toggle_fired = False
            except Exception as e:
                logger.error(f"Hotkey release error: {e}")
            return True

        self._listener = kb.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()
        logger.info(
            f"Hotkey listener started (pynput): "
            f"PTT={self._config.ptt_key}, Toggle={self._config.toggle_key}"
        )

    def _start_keyboard(self) -> None:
        import keyboard

        ptt_key = self._config.ptt_key
        toggle_key = self._config.toggle_key

        keyboard.on_press_key(
            ptt_key, lambda _: self._on_ptt_press and self._on_ptt_press()
        )
        keyboard.on_release_key(
            ptt_key, lambda _: self._on_ptt_release and self._on_ptt_release()
        )
        keyboard.on_press_key(
            toggle_key, lambda _: self._on_toggle and self._on_toggle()
        )

        logger.info(
            f"Hotkey listener started (keyboard): PTT={ptt_key}, Toggle={toggle_key}"
        )

    def _parse_pynput_key(self, key_name: str):
        from pynput import keyboard as kb

        key_map = {
            "f1": kb.Key.f1,
            "f2": kb.Key.f2,
            "f3": kb.Key.f3,
            "f4": kb.Key.f4,
            "f5": kb.Key.f5,
            "f6": kb.Key.f6,
            "f7": kb.Key.f7,
            "f8": kb.Key.f8,
            "f9": kb.Key.f9,
            "f10": kb.Key.f10,
            "f11": kb.Key.f11,
            "f12": kb.Key.f12,
            "alt": kb.Key.alt,
            "alt_l": kb.Key.alt_l,
            "alt_r": kb.Key.alt_r,
            "ctrl": kb.Key.ctrl,
            "ctrl_l": kb.Key.ctrl_l,
            "ctrl_r": kb.Key.ctrl_r,
            "shift": kb.Key.shift,
            "shift_l": kb.Key.shift_l,
            "shift_r": kb.Key.shift_r,
            "space": kb.Key.space,
            "tab": kb.Key.tab,
            "enter": kb.Key.enter,
            "esc": kb.Key.esc,
            "cmd": kb.Key.cmd,
            "cmd_l": kb.Key.cmd_l,
        }

        key_lower = key_name.lower()
        if key_lower in key_map:
            return key_map[key_lower]

        if len(key_name) == 1:
            return kb.KeyCode.from_char(key_name)

        return kb.KeyCode.from_char(key_name)
