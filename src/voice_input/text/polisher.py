from __future__ import annotations

import asyncio
import json
import logging
import urllib.request

from voice_input.config import PolishConfig

logger = logging.getLogger(__name__)

STYLE_PROMPTS = {
    "formal": "请将以下口语化文本改写为正式书面语，修正语法错误，去除冗余语气词，保持原意不变。只返回改写后的文本：",
    "casual": "请将以下文本改写为轻松随意的口语风格，可以适当添加语气词，保持原意不变。只返回改写后的文本：",
    "technical": "请将以下文本改写为技术文档风格，使用准确的专业术语，结构清晰。只返回改写后的文本：",
    "auto": "请对以下语音识别结果进行润色：修正错别字和语法错误，去除口语冗余词（如'那个那个''就是说'等），保持原意和语气不变。只返回润色后的文本，不要解释：",
}


class AIPolisher:
    def __init__(self, config: PolishConfig):
        self._config = config
        self._enabled = config.enabled
        self._style = config.style

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def set_style(self, style: str) -> None:
        if style in STYLE_PROMPTS:
            self._style = style

    async def polish(self, text: str) -> str:
        if not self._enabled or not text.strip():
            return text

        backend = self._config.backend

        try:
            if backend == "ollama":
                return await self._polish_ollama(text)
            elif backend == "openai":
                return await self._polish_openai(text)
            else:
                logger.warning(f"Unknown polish backend: {backend}")
                return text
        except Exception as e:
            logger.warning(f"AI polish failed ({backend}): {e}")
            return text

    async def _polish_ollama(self, text: str) -> str:
        cfg = self._config.ollama
        prompt = STYLE_PROMPTS.get(self._style, STYLE_PROMPTS["auto"])

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._sync_ollama_request, cfg.host, cfg.model, prompt, text
        )

    def _sync_ollama_request(self, host: str, model: str, prompt: str, text: str) -> str:
        url = f"{host.rstrip('/')}/api/generate"
        payload = json.dumps({
            "model": model,
            "prompt": f"{prompt}\n\n{text}",
            "stream": False,
            "options": {"num_predict": 512, "temperature": 0.3},
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("response", text).strip()
        except Exception:
            raise

    async def _polish_openai(self, text: str) -> str:
        cfg = self._config.openai
        if not cfg.api_key:
            logger.warning("OpenAI API key not configured, skipping polish")
            return text

        prompt = STYLE_PROMPTS.get(self._style, STYLE_PROMPTS["auto"])

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._sync_openai_request, cfg, prompt, text
        )

    def _sync_openai_request(self, cfg, prompt: str, text: str) -> str:
        url = f"{cfg.base_url.rstrip('/')}/chat/completions"
        payload = json.dumps({
            "model": cfg.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
            "max_tokens": 512,
        }).encode("utf-8")

        req = urllib.request.Request(
            url, data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {cfg.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"].strip()
        except Exception:
            raise