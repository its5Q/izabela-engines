import importlib.util
import inspect
import logging
import pathlib

from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from engines.base import BaseEngine
from models import Credentials, SynthesizePayload, Voice

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Loading engines
engines: list[BaseEngine] = []
engine_map: dict[str, int] = {}

engines_path = pathlib.Path(__file__).resolve().parent / "engines"

for engine_file in sorted(engines_path.glob("*.py")):
    module_name = engine_file.stem
    if module_name in {"__init__", "base"}:
        continue

    spec = importlib.util.spec_from_file_location(module_name, str(engine_file))
    if spec is None or spec.loader is None:
        continue
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    classes = [obj for _, obj in inspect.getmembers(module, inspect.isclass)]
    engine_cls = next(
        (cls for cls in classes if issubclass(cls, BaseEngine) and cls is not BaseEngine),
        None,
    )

    if engine_cls:
        engine_map[engine_cls.__name__] = len(engines)
        engines.append(engine_cls())
    else:
        logger.warning("Failed to find engine class in %s", engine_file.name)

# Voice list
voices: list[Voice] = []
for engine in engines:
    voices.extend(engine.list_voices())

logger.info("Loaded %d voices from %d engines", len(voices), len(engines))

app = FastAPI(title="Izabela Engines")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str | int]:
    return {"status": "ok", "engines": len(engines), "voices": len(voices)}


@app.post("/list-voices")
def list_voices(
    credentials: Credentials = Body(default_factory=Credentials, embed=True),
) -> list[Voice]:
    return voices


def _resolve_engine(voice: Voice) -> BaseEngine | None:
    if voice not in voices or voice.category not in engine_map:
        return None
    return engines[engine_map[voice.category]]


@app.post(
    "/synthesize-speech",
    responses={200: {"content": {"audio/mpeg": {}}}},
    response_class=Response,
)
def synthesize_speech(
    payload: SynthesizePayload,
    credentials: Credentials = Body(default_factory=Credentials),
    includeTimestamps: bool = Body(default=False),
) -> Response:
    engine = _resolve_engine(payload.voice)
    if engine is None:
        return Response(status_code=400, content="Voice not found")

    mp3_bytes = engine.synthesize_voice(payload.voice, payload.text)
    return Response(status_code=200, content=mp3_bytes, media_type="audio/mpeg")


@app.post(
    "/synthesize-speech/stream",
    responses={200: {"content": {"audio/mpeg": {}}}},
    response_class=Response,
)
def synthesize_speech_stream(
    payload: SynthesizePayload,
    credentials: Credentials = Body(default_factory=Credentials),
    includeTimestamps: bool = Body(default=False),
) -> Response:
    engine = _resolve_engine(payload.voice)
    if engine is None:
        return Response(status_code=400, content="Voice not found")

    if engine.supports_streaming:
        return StreamingResponse(
            engine.synthesize_voice_stream(payload.voice, payload.text),
            media_type="audio/mpeg",
        )

    mp3_bytes = engine.synthesize_voice(payload.voice, payload.text)
    return Response(status_code=200, content=mp3_bytes, media_type="audio/mpeg")
