from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Protocol, runtime_checkable


@runtime_checkable
class ASRProvider(Protocol):
    async def transcribe(self, audio_data: bytes, sample_rate: int) -> str:
        ...

    async def transcribe_stream(
        self, audio_source: AsyncIterator[bytes], sample_rate: int
    ) -> AsyncIterator[ASRResult]:
        ...

    def load_model(self) -> None:
        ...

    def unload_model(self) -> None:
        ...


class ASRResult:
    def __init__(
        self,
        text: str,
        is_final: bool = True,
        confidence: float = 1.0,
    ):
        self.text = text
        self.is_final = is_final
        self.confidence = confidence

    def __repr__(self) -> str:
        return (
            f"ASRResult(text={self.text!r}, "
            f"is_final={self.is_final}, "
            f"confidence={self.confidence:.2f})"
        )


@runtime_checkable
class AudioRecorder(Protocol):
    def start_recording(self) -> None:
        ...

    def stop_recording(self) -> bytes:
        ...

    def is_recording(self) -> bool:
        ...

    def get_audio_data(self) -> bytes:
        ...


@runtime_checkable
class TextProcessor(Protocol):
    def process(self, text: str) -> str:
        ...


@runtime_checkable
class TextOutput(Protocol):
    def output(self, text: str) -> None:
        ...


@runtime_checkable
class HotkeyListener(Protocol):
    def start(
        self,
        on_ptt_press: Callable,
        on_ptt_release: Callable,
        on_toggle: Callable,
    ) -> None:
        ...

    def stop(self) -> None:
        ...
