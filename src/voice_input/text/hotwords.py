from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class HotwordManager:
    def __init__(self, hotwords_file: str = "hotwords.txt"):
        self._hotwords_file = Path(hotwords_file)
        self._corrections: dict[str, str] = {}
        self._hotwords: list[str] = []
        self.reload()

    def reload(self) -> None:
        self._corrections = {}
        self._hotwords = []

        if not self._hotwords_file.exists():
            logger.debug(f"Hotwords file not found: {self._hotwords_file}")
            return

        try:
            lines = self._hotwords_file.read_text(encoding="utf-8").strip().split("\n")
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if "->" in line:
                    parts = line.split("->", 1)
                    wrong = parts[0].strip()
                    right = parts[1].strip()
                    if wrong and right:
                        self._corrections[wrong] = right
                else:
                    self._hotwords.append(line)

            logger.info(
                f"Loaded {len(self._hotwords)} hotwords, "
                f"{len(self._corrections)} corrections"
            )
        except Exception as e:
            logger.warning(f"Failed to load hotwords: {e}")

    def apply_corrections(self, text: str) -> str:
        for wrong, right in self._corrections.items():
            text = text.replace(wrong, right)
        return text

    def get_hotwords(self) -> list[str]:
        return self._hotwords.copy()

    def get_hotwords_string(self) -> str:
        return " ".join(self._hotwords)

    def add_hotword(self, word: str) -> None:
        if word and word not in self._hotwords:
            self._hotwords.append(word)
            self._save()

    def add_correction(self, wrong: str, right: str) -> None:
        self._corrections[wrong] = right
        self._save()

    def _save(self) -> None:
        try:
            self._hotwords_file.parent.mkdir(parents=True, exist_ok=True)
            lines = []
            for hw in self._hotwords:
                lines.append(hw)
            for wrong, right in self._corrections.items():
                lines.append(f"{wrong} -> {right}")
            self._hotwords_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save hotwords: {e}")
