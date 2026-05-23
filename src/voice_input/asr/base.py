from __future__ import annotations

import abc
from collections.abc import AsyncIterator

from voice_input.protocols import ASRResult


class ASRBase(abc.ABC):
    @abc.abstractmethod
    def load_model(self) -> None:
        ...

    @abc.abstractmethod
    def unload_model(self) -> None:
        ...

    @abc.abstractmethod
    async def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        ...

    @abc.abstractmethod
    async def transcribe_stream(
        self, audio_source: AsyncIterator[bytes], sample_rate: int = 16000
    ) -> AsyncIterator[ASRResult]:
        ...

    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def is_loaded(self) -> bool:
        ...
