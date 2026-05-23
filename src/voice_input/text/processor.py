from __future__ import annotations

import logging
import re

from voice_input.config import TextConfig
from voice_input.text.hotwords import HotwordManager

logger = logging.getLogger(__name__)


class TextProcessor:
    def __init__(self, config: TextConfig | None = None):
        self._config = config or TextConfig()
        self._hotword_manager: HotwordManager | None = None

        if self._config.enable_hotwords:
            self._hotword_manager = HotwordManager(self._config.hotwords_file)

    def process(self, text: str) -> str:
        if not text:
            return ""

        text = text.strip()

        if self._hotword_manager:
            text = self._hotword_manager.apply_corrections(text)

        if self._config.merge_single_letters:
            text = self._merge_single_letters(text)

        if self._config.strip_trailing_punctuation:
            text = self._strip_trailing_punctuation(text)

        if self._config.enable_traditional_chinese:
            text = self._to_simplified(text)

        return text

    def _merge_single_letters(self, text: str) -> str:
        pattern = r"\b([A-Za-z])\s+(?=[A-Za-z]\b)"
        while re.search(pattern, text):
            text = re.sub(pattern, r"\1", text)
        return text

    def _strip_trailing_punctuation(self, text: str) -> str:
        text = text.rstrip("。！？，、；：")
        text = text.rstrip(".!?,:;")
        return text

    def _to_simplified(self, text: str) -> str:
        try:
            from opencc import OpenCC

            cc = OpenCC("t2s")
            return cc.convert(text)
        except ImportError:
            logger.debug("opencc not installed, skipping traditional to simplified conversion")
            return text

    def reload_hotwords(self) -> None:
        if self._hotword_manager:
            self._hotword_manager.reload()
