from collections.abc import Iterator
import logging
import os
import threading
import time

import numpy as np
import torch
from kokoro import KModel, KPipeline

from engines.base import (
    BaseEngine,
    encode_mp3,
    encode_silence_mp3,
    stream_mp3,
)
from models import Voice

logger = logging.getLogger(__name__)

REPO_ID = "hexgrad/Kokoro-82M"
SAMPLE_RATE = 24000
LANG_MAP = {
    "a": "en-us",
    "b": "en-gb",
    "e": "es",
    "f": "fr-fr",
    "h": "hi",
    "i": "it",
    "p": "pt-br",
    "j": "ja",
    "z": "zh",
}
STREAM_SPLIT_PATTERN = r"(?:\n+|(?<=[.!?。！？])\s+|(?<=[。！？]))"
VOICES = [
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore",
    "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael",
    "am_onyx", "am_puck", "am_santa",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    "ef_dora", "em_alex", "em_santa",
    "ff_siwis",
    "hf_alpha", "hf_beta", "hm_omega", "hm_psi",
    "if_sara", "im_nicola",
    "jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo",
    "pf_dora", "pm_alex", "pm_santa",
    "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi",
    "zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang",
]


def _select_device() -> str:
    use_cuda = os.environ.get("IZABELA_USE_CUDA", "").strip().lower() in {
        "1", "true", "yes", "on",
    }
    if not use_cuda:
        logger.info("Using CPU for Kokoro inference.")
        return "cpu"

    if not torch.cuda.is_available():
        logger.warning(
            "IZABELA_USE_CUDA is enabled, but no CUDA GPU was detected. Falling back to CPU."
        )
        return "cpu"

    try:
        gpu_name = torch.cuda.get_device_name(0)
        major, minor = torch.cuda.get_device_capability(0)
        # Quick kernel smoke test to verify this PyTorch wheel supports the GPU's SM version
        _ = (torch.ones(1, device="cuda") + 1).item()
        logger.info(
            "Using CUDA GPU: %s (compute capability %d.%d, PyTorch %s)",
            gpu_name,
            major,
            minor,
            torch.__version__,
        )
        return "cuda"
    except Exception as exc:
        logger.warning(
            "CUDA device is incompatible with installed PyTorch build (%s): %s. "
            "If you are using a GTX 900/10-series GPU, use the 'cuda-legacy' Docker profile; "
            "for RTX 50-series+, use the 'cuda' profile. Falling back to CPU.",
            torch.__version__,
            exc,
        )
        return "cpu"



class KokoroEngine(BaseEngine):
    def __init__(self):
        self._lock = threading.Lock()
        self._device = _select_device()

        logger.info("Loading Kokoro model (%s) on %s...", REPO_ID, self._device)
        self._model = KModel(repo_id=REPO_ID).to(self._device).eval()
        self._pipelines: dict[str, KPipeline] = {
            "a": KPipeline(lang_code="a", repo_id=REPO_ID, model=self._model),
        }

    def _get_pipeline(self, lang_code: str, language_label: str) -> KPipeline:
        pipeline = self._pipelines.get(lang_code)
        if pipeline is None:
            logger.info("Loading Kokoro pipeline for language %s...", language_label)
            en_callable = None
            if lang_code == "z":
                en_pipeline = self._pipelines["a"]
                en_callable = lambda text: next(en_pipeline(text, voice="af_heart")).phonemes
            pipeline = KPipeline(
                lang_code=lang_code,
                repo_id=REPO_ID,
                model=self._model,
                en_callable=en_callable,
            )
            self._pipelines[lang_code] = pipeline
        return pipeline

    def list_voices(self) -> list[Voice]:
        voices = []
        for voice in VOICES:
            gender = "Male" if voice[1] == "m" else "Female"
            lang = LANG_MAP[voice[0]]
            speaker = voice.split("_", 1)[1].capitalize()
            voices.append(
                Voice(
                    id=voice,
                    name=f"Kokoro - {speaker} ({gender}) ({lang})",
                    category=self.__class__.__name__,
                    languageCode=lang,
                )
            )
        return voices

    def synthesize_voice(self, voice: Voice, text: str) -> bytes:
        if not text or not text.strip():
            return encode_silence_mp3(SAMPLE_RATE)

        with self._lock:
            pipeline = self._get_pipeline(voice.id[0], voice.languageCode)
            start_time = time.perf_counter()
            chunks: list[torch.Tensor] = []
            for result in pipeline(text, voice=voice.id):
                if result.audio is not None:
                    chunks.append(result.audio)
            elapsed = time.perf_counter() - start_time
            logger.info("Synthesized speech with %s in %.3fs", voice.id, elapsed)

        if not chunks:
            return encode_silence_mp3(SAMPLE_RATE)

        samples = torch.cat(chunks).numpy()
        return encode_mp3(samples, SAMPLE_RATE)

    def _iter_pcm_chunks(self, voice: Voice, text: str) -> Iterator[np.ndarray]:
        with self._lock:
            pipeline = self._get_pipeline(voice.id[0], voice.languageCode)
            stream = pipeline(
                text,
                voice=voice.id,
                split_pattern=STREAM_SPLIT_PATTERN,
            )

        try:
            while True:
                with self._lock:
                    result = next(stream, None)
                if result is None:
                    break
                if result.audio is not None:
                    yield result.audio.numpy()
        finally:
            stream.close()

    def synthesize_voice_stream(self, voice: Voice, text: str) -> Iterator[bytes]:
        if not text or not text.strip():
            yield encode_silence_mp3(SAMPLE_RATE)
            return

        start_time = time.perf_counter()
        yield from stream_mp3(self._iter_pcm_chunks(voice, text), SAMPLE_RATE)
        elapsed = time.perf_counter() - start_time
        logger.info("Streamed speech with %s in %.3fs", voice.id, elapsed)
