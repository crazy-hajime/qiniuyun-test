from __future__ import annotations

import asyncio
import io
import logging
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from voice_input.asr.base import ASRBase
from voice_input.config import ASRConfig
from voice_input.protocols import ASRResult

logger = logging.getLogger(__name__)

MODEL_CACHE_DIR = Path.home() / ".cache" / "voice-input" / "models"

SENSEVOICE_MODEL_DIR_NAME = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"

DOWNLOAD_MIRRORS = [
    (
        "ModelScope",
        "modelscope:pengzhendong/sherpa-onnx-sense-voice-zh-en-ja-ko-yue",
    ),
    (
        "GitHub",
        (
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
            "asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17.tar.bz2"
        ),
    ),
    (
        "HuggingFace",
        (
            "https://huggingface.co/csukuangfj/"
            "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main/"
            "model.int8.onnx"
        ),
    ),
]


class SherpaBackend(ASRBase):
    def __init__(self, config: ASRConfig):
        self._config = config.sherpa
        self._recognizer = None
        self._loaded = False

    @property
    def name(self) -> str:
        return "sherpa"

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load_model(self) -> None:
        if self._loaded:
            return
        try:
            import sherpa_onnx

            model_dir = self._resolve_model_dir()

            self._recognizer = self._create_recognizer(sherpa_onnx, model_dir)
            self._loaded = True
            logger.info(f"Sherpa model loaded from {model_dir}")
        except ImportError:
            raise ImportError(
                "sherpa-onnx is not installed. "
                "Install it with: pip install sherpa-onnx"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load Sherpa model: {e}")

    def _resolve_model_dir(self) -> Path:
        if self._config.model_dir:
            model_dir = Path(self._config.model_dir)
            if model_dir.exists():
                return model_dir
            raise FileNotFoundError(f"Sherpa model directory not found: {model_dir}")

        sensevoice_dir = MODEL_CACHE_DIR / SENSEVOICE_MODEL_DIR_NAME
        if sensevoice_dir.exists():
            return sensevoice_dir

        logger.info("No model directory configured, attempting auto-download...")
        self._download_sensevoice()
        return MODEL_CACHE_DIR / SENSEVOICE_MODEL_DIR_NAME

    def _download_sensevoice(self) -> None:
        target_dir = MODEL_CACHE_DIR / SENSEVOICE_MODEL_DIR_NAME
        if target_dir.exists():
            return

        MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        last_error = None
        for mirror_name, url in DOWNLOAD_MIRRORS:
            print(f"\n尝试从 {mirror_name} 下载 SenseVoice 模型...")
            logger.info(f"Downloading from {mirror_name}: {url}")

            try:
                if url.startswith("modelscope:"):
                    self._download_from_modelscope(url)
                else:
                    self._download_from_url(url)
                print(f"模型已安装到: {MODEL_CACHE_DIR}")
                return
            except Exception as e:
                last_error = e
                print(f"\n从 {mirror_name} 下载失败: {e}")
                logger.warning(f"Download from {mirror_name} failed: {e}")
                continue

        print("\n" + "=" * 60)
        print("自动下载失败，请手动下载模型：")
        print("  方式1 - 使用 ModelScope SDK（推荐国内用户）：")
        print("    pip install modelscope")
        print("    python -c \"from modelscope import snapshot_download; "
              "snapshot_download('pengzhendong/sherpa-onnx-sense-voice-zh-en-ja-ko-yue', "
              f"cache_dir='{MODEL_CACHE_DIR}')\"")
        print("  方式2 - 直接下载：")
        for mirror_name, url in DOWNLOAD_MIRRORS:
            print(f"     {mirror_name}: {url}")
        print(f"  解压到: {MODEL_CACHE_DIR}")
        print("  或在 config.yaml 中设置 asr.sherpa.model_dir")
        print("=" * 60)
        raise RuntimeError(
            f"Failed to download model. Last error: {last_error}"
        )

    def _download_from_modelscope(self, url: str) -> None:
        model_id = url.replace("modelscope:", "")
        print(f"  使用 ModelScope SDK 下载: {model_id}")
        print("  (首次使用需安装: pip install modelscope)")

        from modelscope import snapshot_download

        download_dir = snapshot_download(
            model_id,
            cache_dir=str(MODEL_CACHE_DIR / "modelscope_cache"),
            ignore_file_pattern=["model.onnx"],
        )

        src_dir = Path(download_dir)
        dst_dir = MODEL_CACHE_DIR / SENSEVOICE_MODEL_DIR_NAME

        if dst_dir.exists():
            return

        import shutil

        shutil.copytree(src_dir, dst_dir)
        print("  ModelScope 下载完成")

    def _download_from_url(self, url: str) -> None:
        import tarfile
        import tempfile
        import urllib.request

        print(f"  URL: {url}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "model.tar.bz2"
            urllib.request.urlretrieve(
                url,
                str(tmp_path),
                reporthook=self._download_progress,
            )
            print("\n  下载完成，正在解压...")
            logger.info("Download complete, extracting...")
            with tarfile.open(str(tmp_path), "r:bz2") as tar:
                tar.extractall(path=str(MODEL_CACHE_DIR))
            logger.info(f"Model extracted to {MODEL_CACHE_DIR}")

    @staticmethod
    def _download_progress(block_num: int, block_size: int, total_size: int) -> None:
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(downloaded / total_size * 100, 100)
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            bar_len = 40
            filled = int(bar_len * percent / 100)
            bar = "█" * filled + "░" * (bar_len - filled)
            sys.stdout.write(
                f"\r  [{bar}] {percent:5.1f}% "
                f"({mb_downloaded:.1f}/{mb_total:.1f} MB)"
            )
            sys.stdout.flush()
        else:
            mb_downloaded = downloaded / (1024 * 1024)
            sys.stdout.write(f"\r  已下载: {mb_downloaded:.1f} MB")
            sys.stdout.flush()

    def _create_recognizer(self, sherpa_onnx, model_dir: Path):
        model_dir = Path(model_dir)

        int8_model = model_dir / "model.int8.onnx"
        fp32_model = model_dir / "model.onnx"

        if int8_model.exists():
            model_path = str(int8_model)
        elif fp32_model.exists():
            model_path = str(fp32_model)
        else:
            raise FileNotFoundError(f"No model.onnx or model.int8.onnx in {model_dir}")

        tokens_path = str(model_dir / "tokens.txt")

        if not Path(tokens_path).exists():
            raise FileNotFoundError(f"tokens.txt not found in {model_dir}")

        is_sensevoice = "sense" in model_path.lower()

        if is_sensevoice:
            return sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=model_path,
                tokens=tokens_path,
                num_threads=2,
                provider=self._config.provider,
                language=self._config.language,
                use_itn=True,
            )
        else:
            return sherpa_onnx.OfflineRecognizer.from_paraformer(
                model=model_path,
                tokens=tokens_path,
                num_threads=2,
                provider=self._config.provider,
            )

    def unload_model(self) -> None:
        self._recognizer = None
        self._loaded = False
        logger.info("Sherpa model unloaded")

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
        if audio_array.dtype != np.float32:
            audio_array = audio_array.astype(np.float32) / 32768.0

        stream = self._recognizer.create_stream()
        stream.accept_waveform(sample_rate, audio_array)
        self._recognizer.decode_stream(stream)
        return stream.result.text.strip()

    def _parse_audio(self, audio_data: bytes, sample_rate: int) -> np.ndarray:
        buf = io.BytesIO(audio_data)
        sr, data = wavfile.read(buf)

        if data.ndim > 1:
            data = data[:, 0]

        return data
