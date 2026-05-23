from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from voice_input.asr.base import ASRBase
from voice_input.config import ASRConfig
from voice_input.protocols import ASRResult

logger = logging.getLogger(__name__)


class CloudBackend(ASRBase):
    def __init__(self, config: ASRConfig):
        self._config = config.cloud
        self._loaded = False

    @property
    def name(self) -> str:
        return f"cloud-{self._config.provider}"

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load_model(self) -> None:
        if not self._config.provider:
            raise ValueError("Cloud ASR provider is not configured")
        if not self._config.api_key:
            raise ValueError("Cloud ASR API key is not configured")
        self._loaded = True
        logger.info(f"Cloud ASR backend initialized: {self._config.provider}")

    def unload_model(self) -> None:
        self._loaded = False

    async def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        if not self._loaded:
            self.load_model()

        provider = self._config.provider.lower()

        if provider == "openai":
            return await self._transcribe_openai(audio_data)
        elif provider == "volcengine":
            return await self._transcribe_volcengine(audio_data, sample_rate)
        else:
            raise ValueError(f"Unsupported cloud provider: {provider}")

    async def transcribe_stream(
        self, audio_source: AsyncIterator[bytes], sample_rate: int = 16000
    ) -> AsyncIterator[ASRResult]:
        chunks = []
        async for chunk in audio_source:
            chunks.append(chunk)

        all_audio = b"".join(chunks)
        if not all_audio:
            return

        text = await self.transcribe(all_audio, sample_rate)
        yield ASRResult(text=text, is_final=True)

    async def _transcribe_openai(self, audio_data: bytes) -> str:
        import urllib.error
        import urllib.request

        url = self._config.endpoint or "https://api.openai.com/v1/audio/transcriptions"

        boundary = "----VoiceInputBoundary"
        body = self._build_multipart(audio_data, boundary)

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self._urllib_request, req)

        result = json.loads(response.decode("utf-8"))
        return result.get("text", "").strip()

    async def _transcribe_volcengine(self, audio_data: bytes, sample_rate: int) -> str:
        logger.warning("Volcengine ASR not yet implemented")
        return ""

    def _build_multipart(self, audio_data: bytes, boundary: str) -> bytes:
        lines = []
        lines.append(f"--{boundary}".encode())
        lines.append(
            b'Content-Disposition: form-data; name="file"; filename="audio.wav"'
        )
        lines.append(b"Content-Type: audio/wav")
        lines.append(b"")
        lines.append(audio_data)

        lines.append(f"--{boundary}".encode())
        lines.append(b'Content-Disposition: form-data; name="model"')
        lines.append(b"")
        lines.append(b"whisper-1")

        lines.append(f"--{boundary}".encode())
        lines.append(b'Content-Disposition: form-data; name="language"')
        lines.append(b"")
        lines.append(b"zh")

        lines.append(f"--{boundary}--".encode())
        lines.append(b"")

        return b"\r\n".join(lines)

    @staticmethod
    def _urllib_request(req) -> bytes:
        import urllib.error
        import urllib.request

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Cloud ASR HTTP {e.code}: {body}")
