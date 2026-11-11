from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterator
import importlib.util
import json
import logging
import os
import pathlib
import threading
import time
from typing import TYPE_CHECKING, Any
from urllib.request import Request, urlopen

import numpy as np

if TYPE_CHECKING:
    from piper.config import SynthesisConfig
    from piper.voice import PiperVoice

from engines.base import (
    BaseEngine,
    encode_mp3,
    encode_silence_mp3,
    stream_mp3,
)
from models import Voice

logger = logging.getLogger(__name__)

REPO_ID = "rhasspy/piper-voices"
VOICES_JSON_URL = (
    f"https://huggingface.co/{REPO_ID}/resolve/main/voices.json?download=true"
)
VOICES_JSON_TIMEOUT_SECONDS = 10.0
DEFAULT_SAMPLE_RATE = 22050
MAX_LOADED_MODELS = 3
MAX_MULTI_SPEAKERS_DEFAULT = 8

QUALITY_LABELS = {
    "x_low": "X-Low",
    "low": "Low",
    "medium": "Medium",
    "high": "High",
}


def _format_label(raw: str) -> str:
    return " ".join(
        part.upper() if part.isupper() and len(part) > 1 else part.capitalize()
        for part in raw.replace("-", "_").split("_")
        if part
    )


def _parse_model_key(model_key: str) -> tuple[str, str, str, str]:
    locale, voice_name, quality = model_key.split("-", 2)
    lang_family = locale.split("_", 1)[0]
    return lang_family, locale, voice_name, quality


def _resolve_cache_dir() -> pathlib.Path:
    explicit = os.environ.get("IZABELA_PIPER_CACHE_DIR", "").strip()
    if explicit:
        return pathlib.Path(explicit)

    hf_home = os.environ.get("HF_HOME", "").strip()
    if hf_home:
        return pathlib.Path(hf_home) / "piper"

    return pathlib.Path(__file__).resolve().parent.parent / "models" / "piper"


def _locale_supported(locale: str) -> bool:
    if locale.startswith("ja_"):
        return importlib.util.find_spec("pyopenjtalk") is not None
    if locale.startswith("th_"):
        return importlib.util.find_spec("tltk") is not None
    return True


def _extract_model_files(model_key: str, info: dict[str, Any]) -> tuple[str, str]:
    files = info.get("files") or {}
    onnx_file = next(
        (path for path in files if path.endswith(".onnx") and not path.endswith(".onnx.json")),
        None,
    )
    config_file = next((path for path in files if path.endswith(".onnx.json")), None)
    if onnx_file and config_file:
        return onnx_file, config_file

    lang_family, locale, voice_name, quality = _parse_model_key(model_key)
    repo_subdir = f"{lang_family}/{locale}/{voice_name}/{quality}"
    return f"{repo_subdir}/{model_key}.onnx", f"{repo_subdir}/{model_key}.onnx.json"


class PiperEngine(BaseEngine):
    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._voices_cache: OrderedDict[str, PiperVoice] = OrderedDict()
        self._download_dir = _resolve_cache_dir()
        self._voice_specs: dict[str, tuple[str, int | None]] = {}
        self._model_files: dict[str, tuple[str, str]] = {}

    def _load_model(self) -> None:
        import piper  # noqa: F401

        self._download_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Initialized Piper runtime (voice cache: %s).", self._download_dir)

    def _fetch_voices_manifest(self) -> dict[str, Any]:
        cache_path = self._download_dir / "voices.json"
        try:
            req = Request(VOICES_JSON_URL, headers={"User-Agent": "izabela-engines/1.0"})
            with urlopen(req, timeout=VOICES_JSON_TIMEOUT_SECONDS) as response:
                raw_bytes = response.read()
            manifest = json.loads(raw_bytes)
            if isinstance(manifest, dict) and manifest:
                try:
                    self._download_dir.mkdir(parents=True, exist_ok=True)
                    tmp_path = cache_path.with_suffix(".json.tmp")
                    tmp_path.write_bytes(raw_bytes)
                    tmp_path.replace(cache_path)
                except OSError as exc:
                    logger.warning("Failed to cache Piper voices.json to %s: %s", cache_path, exc)
                return manifest
        except Exception as exc:
            logger.warning("Could not fetch live Piper voices.json (%s); checking local cache.", exc)

        if cache_path.is_file():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.error("Failed to read cached Piper voices.json at %s: %s", cache_path, exc)

        logger.error("No Piper voice manifest available (offline and no cached voices.json).")
        return {}

    def _resolve_voice_spec(self, voice_id: str) -> tuple[str, int | None]:
        spec = self._voice_specs.get(voice_id)
        if spec is not None:
            return spec
        if "#" in voice_id:
            model_key, spk = voice_id.split("#", 1)
            return model_key, int(spk)
        return voice_id, None

    def _ensure_voice_files(self, model_key: str) -> tuple[pathlib.Path, pathlib.Path]:
        from huggingface_hub import hf_hub_download

        onnx_filename, config_filename = self._model_files.get(model_key) or _extract_model_files(
            model_key, {}
        )

        local_onnx = self._download_dir / onnx_filename
        local_config = self._download_dir / config_filename
        if local_onnx.is_file() and local_onnx.stat().st_size > 0 and local_config.is_file():
            return local_onnx, local_config

        logger.info("Downloading Piper voice model '%s' from %s...", model_key, REPO_ID)
        config_path = pathlib.Path(
            hf_hub_download(
                repo_id=REPO_ID,
                filename=config_filename,
                local_dir=self._download_dir,
            )
        )
        onnx_path = pathlib.Path(
            hf_hub_download(
                repo_id=REPO_ID,
                filename=onnx_filename,
                local_dir=self._download_dir,
            )
        )
        return onnx_path, config_path

    def _get_piper_voice(self, model_key: str) -> tuple[PiperVoice, type[SynthesisConfig]]:
        from piper.config import SynthesisConfig
        from piper.voice import PiperVoice

        cached = self._voices_cache.get(model_key)
        if cached is not None:
            self._voices_cache.move_to_end(model_key)
            return cached, SynthesisConfig

        onnx_path, config_path = self._ensure_voice_files(model_key)
        logger.info("Loading Piper ONNX session for '%s'...", model_key)
        piper_voice = PiperVoice.load(
            model_path=onnx_path,
            config_path=config_path,
            use_cuda=False,
            download_dir=self._download_dir,
        )
        self._voices_cache[model_key] = piper_voice
        while len(self._voices_cache) > MAX_LOADED_MODELS:
            evicted_key, _ = self._voices_cache.popitem(last=False)
            logger.info("Evicted idle Piper ONNX session '%s' from cache.", evicted_key)

        return piper_voice, SynthesisConfig

    def list_voices(self) -> list[Voice]:
        manifest = self._fetch_voices_manifest()
        if not manifest:
            return []

        include_all_speakers = os.environ.get("IZABELA_PIPER_ALL_SPEAKERS", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        has_zh_pinyin = importlib.util.find_spec("g2pw") is not None

        category = self.__class__.__name__
        voices: list[Voice] = []
        voice_specs: dict[str, tuple[str, int | None]] = {}
        model_files: dict[str, tuple[str, str]] = {}

        # Track which locales already have a single-speaker or small multi-speaker model
        covered_locales: set[str] = set()
        for model_key, info in manifest.items():
            locale = info.get("language", {}).get("code", "")
            num_speakers = int(info.get("num_speakers", 1) or 1)
            if locale and num_speakers <= MAX_MULTI_SPEAKERS_DEFAULT:
                covered_locales.add(locale)

        for model_key in sorted(manifest.keys()):
            info = manifest[model_key]
            locale = info.get("language", {}).get("code") or _parse_model_key(model_key)[1]
            if not _locale_supported(locale):
                continue

            # Chinese g2pW models require piper-tts[zh]; skip only if g2pW isn't installed
            if locale.startswith("zh_") and not has_zh_pinyin and "huayan" not in model_key:
                continue

            voice_name = info.get("name") or _parse_model_key(model_key)[2]
            quality = info.get("quality") or _parse_model_key(model_key)[3]
            num_speakers = int(info.get("num_speakers", 1) or 1)
            speaker_id_map: dict[str, int] = info.get("speaker_id_map") or {}

            model_files[model_key] = _extract_model_files(model_key, info)

            lang_code = locale.lower().replace("_", "-")
            quality_label = QUALITY_LABELS.get(quality, quality.capitalize())
            base_speaker = _format_label(voice_name)

            if num_speakers <= 1 or not speaker_id_map:
                voice_specs[model_key] = (model_key, None)
                voices.append(
                    Voice(
                        id=model_key,
                        name=f"Piper - {base_speaker} ({quality_label}) ({lang_code})",
                        category=category,
                        languageCode=lang_code,
                    )
                )
                continue

            sorted_speakers = sorted(speaker_id_map.items(), key=lambda item: item[1])
            if not include_all_speakers and num_speakers > MAX_MULTI_SPEAKERS_DEFAULT:
                # Avoid flooding the voice picker with 904 LibriTTS speaker IDs unless opted in;
                # still keep 2 speakers if this corpus is the only voice for its locale.
                if locale in covered_locales:
                    sorted_speakers = sorted_speakers[:1]
                else:
                    sorted_speakers = sorted_speakers[:2]

            for speaker_label, speaker_id in sorted_speakers:
                voice_id = f"{model_key}#{speaker_id}"
                voice_specs[voice_id] = (model_key, int(speaker_id))
                speaker_display = f"{base_speaker} / {_format_label(str(speaker_label))}"
                voices.append(
                    Voice(
                        id=voice_id,
                        name=f"Piper - {speaker_display} ({quality_label}) ({lang_code})",
                        category=category,
                        languageCode=lang_code,
                    )
                )

        self._voice_specs = voice_specs
        self._model_files = model_files
        return voices

    def synthesize_voice(self, voice: Voice, text: str) -> bytes:
        if not text or not text.strip():
            return encode_silence_mp3(DEFAULT_SAMPLE_RATE)

        self.ensure_loaded()
        model_key, speaker_id = self._resolve_voice_spec(voice.id)

        with self._lock:
            piper_voice, syn_cfg_cls = self._get_piper_voice(model_key)
            syn_config = syn_cfg_cls(speaker_id=speaker_id) if speaker_id is not None else None
            sample_rate = piper_voice.config.sample_rate

            start_time = time.perf_counter()
            chunks: list[np.ndarray] = []
            for chunk in piper_voice.synthesize(text, syn_config=syn_config):
                if chunk.audio_float_array is not None and len(chunk.audio_float_array) > 0:
                    chunks.append(chunk.audio_float_array)
            elapsed = time.perf_counter() - start_time
            logger.info("Synthesized speech with %s in %.3fs", voice.id, elapsed)

        if not chunks:
            return encode_silence_mp3(sample_rate)

        samples = chunks[0] if len(chunks) == 1 else np.concatenate(chunks)
        return encode_mp3(samples, sample_rate)

    def _iter_pcm_chunks(
        self,
        piper_voice: PiperVoice,
        text: str,
        syn_config: SynthesisConfig | None,
    ) -> Iterator[np.ndarray]:
        with self._lock:
            stream = iter(piper_voice.synthesize(text, syn_config=syn_config))

        try:
            while True:
                with self._lock:
                    chunk = next(stream, None)
                if chunk is None:
                    break
                if chunk.audio_float_array is not None and len(chunk.audio_float_array) > 0:
                    yield chunk.audio_float_array
        finally:
            close_fn = getattr(stream, "close", None)
            if callable(close_fn):
                close_fn()

    def synthesize_voice_stream(self, voice: Voice, text: str) -> Iterator[bytes]:
        if not text or not text.strip():
            yield encode_silence_mp3(DEFAULT_SAMPLE_RATE)
            return

        self.ensure_loaded()
        model_key, speaker_id = self._resolve_voice_spec(voice.id)

        with self._lock:
            piper_voice, syn_cfg_cls = self._get_piper_voice(model_key)
            syn_config = syn_cfg_cls(speaker_id=speaker_id) if speaker_id is not None else None
            sample_rate = piper_voice.config.sample_rate

        start_time = time.perf_counter()
        yield from stream_mp3(
            self._iter_pcm_chunks(piper_voice, text, syn_config),
            sample_rate,
        )
        elapsed = time.perf_counter() - start_time
        logger.info("Streamed speech with %s in %.3fs", voice.id, elapsed)
