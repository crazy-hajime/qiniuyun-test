from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import numpy as np

from voice_input.asr.base import ASRBase
from voice_input.config import ASRConfig
from voice_input.protocols import ASRResult

logger = logging.getLogger(__name__)

def _get_safe_cache_dir() -> Path:
    home = Path.home()
    try:
        str(home).encode("ascii")
        return home / ".cache" / "voice-input" / "models"
    except UnicodeEncodeError:
        return Path(tempfile.gettempdir()) / "voice-input-models"


MODEL_CACHE_DIR = _get_safe_cache_dir()

SENSEVOICE_MODEL_ID = "iic/SenseVoiceSmall"


class FunASRBackend(ASRBase):
    def __init__(self, config: ASRConfig):
        self._config = config.funasr
        self._model = None
        self._punc_model = None
        self._loaded = False

    @property
    def name(self) -> str:
        return "funasr"

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load_model(self) -> None:
        if self._loaded:
            return
        try:
            os.environ["MODELSCOPE_DISABLE_REMOTE"] = "1"

            from funasr import AutoModel

            model_name = self._config.model or SENSEVOICE_MODEL_ID

            if Path(model_name).exists():
                model_path = model_name
            else:
                model_path = self._resolve_model_path(model_name)

            logger.info(f"Loading FunASR model: {model_path}")

            device = self._resolve_device()
            self._model = AutoModel(
                model=model_path,
                device=device,
                disable_update=True,
            )

            self._punc_pending = self._config.enable_punctuation

            self._loaded = True
            logger.info("FunASR model loaded successfully")
        except ImportError:
            raise ImportError(
                "funasr is not installed. "
                "Install it with: pip install funasr torch torchaudio"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load FunASR model: {e}")

    def _resolve_model_path(self, model_id: str) -> str:
        local_dir = MODEL_CACHE_DIR / model_id.replace("/", os.sep)
        if local_dir.exists():
            return str(local_dir)

        modelscope_dir = (
            Path.home() / ".cache" / "modelscope" / "hub" / "models"
        )
        ms_local = modelscope_dir / model_id.replace("/", os.sep)
        if ms_local.exists():
            safe_dir = MODEL_CACHE_DIR / model_id.replace("/", os.sep)
            if not safe_dir.exists():
                import shutil
                safe_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(str(ms_local), str(safe_dir))
            return str(safe_dir)

        try:
            from modelscope import snapshot_download

            cache_dir = str(MODEL_CACHE_DIR / "modelscope_cache")
            download_dir = snapshot_download(
                model_id,
                cache_dir=cache_dir,
            )

            download_path = Path(download_dir)
            safe_dir = MODEL_CACHE_DIR / model_id.replace("/", os.sep)
            if not safe_dir.exists() and not self._is_ascii_path(download_path):
                import shutil
                safe_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(str(download_path), str(safe_dir))
                return str(safe_dir)

            return download_dir
        except Exception as e:
            logger.warning(f"Failed to download model {model_id}: {e}")
            return model_id

    @staticmethod
    def _is_ascii_path(path: Path) -> bool:
        try:
            str(path).encode("ascii")
            return True
        except UnicodeEncodeError:
            return False

    def unload_model(self) -> None:
        self._model = None
        self._punc_model = None
        self._loaded = False
        logger.info("FunASR model unloaded")

    def _resolve_device(self) -> str:
        device = self._config.device
        if device == "auto":
            import torch
            if torch.cuda.is_available():
                count = torch.cuda.device_count()
                if count > 0:
                    return "cuda:0"
            logger.warning("CUDA not available, using CPU")
            return "cpu"
        elif device.startswith("cuda"):
            return device
        else:
            return "cpu"

    async def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        if not self._loaded:
            self.load_model()

        audio_array = self._parse_audio(audio_data, sample_rate)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self._sync_transcribe, audio_array, sample_rate
        )
        return result

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

    def _sync_transcribe(self, audio_array: np.ndarray, sample_rate: int) -> str:
        result = self._model.generate(
            input=audio_array,
            language=self._config.language or "zh",
            use_itn=True,
        )

        if not result:
            return ""

        text = ""
        if isinstance(result, list) and len(result) > 0:
            item = result[0]
            if isinstance(item, dict):
                text = item.get("text", "")
            else:
                text = str(item)

        text = self._clean_sensevoice_tags(text)

        if self._punc_pending and self._punc_model is None:
            self._punc_pending = False
            try:
                punc_path = self._resolve_model_path(
                    "iic/punc_ct-transformer_zh-cn-common-vocab272727"
                )
                self._punc_model = AutoModel(
                    model=punc_path,
                    disable_update=True,
                )
            except Exception as e:
                logger.warning(f"Failed to load punctuation model: {e}")

        if self._punc_model and text:
            try:
                punc_result = self._punc_model.generate(input=text)
                if punc_result and isinstance(punc_result, list) and len(punc_result) > 0:
                    item = punc_result[0]
                    if isinstance(item, dict):
                        text = item.get("text", text)
            except Exception as e:
                logger.warning(f"Punctuation model failed: {e}")

        return text.strip()

    @staticmethod
    def _clean_sensevoice_tags(text: str) -> str:
        text = re.sub(r"<\|[^|]*\|>", "", text)
        return text.strip()

    def _parse_audio(self, audio_data: bytes, sample_rate: int) -> np.ndarray:
        try:
            import soundfile as sf

            buf = io.BytesIO(audio_data)
            data, sr = sf.read(buf, dtype="int16")

            if data.ndim > 1:
                data = data[:, 0]

            if sr != 16000:
                logger.warning(f"Sample rate {sr} != 16000, resampling may be needed")

            return data.astype(np.float32) / 32768.0
        except Exception:
            data = np.frombuffer(audio_data, dtype=np.int16)
            if data.ndim > 1:
                data = data[:, 0]
            return data.astype(np.float32) / 32768.0
