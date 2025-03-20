import logging

logging.basicConfig(level=logging.DEBUG)

from fastapi import FastAPI, Body
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import importlib.util
import pathlib
import inspect
from models import *
from engines.base import BaseEngine

# Loading engines
engines: list[BaseEngine] = []
engine_map: dict[str, int] = {}

engines_path = pathlib.Path('engines')

for engine_file in engines_path.glob("*.py"):
    module_name = engine_file.stem

    if module_name == "__init__" or module_name == "base":
        continue

    spec = importlib.util.spec_from_file_location(module_name, str(engine_file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    classes = [obj for name, obj in inspect.getmembers(module, inspect.isclass)]
    engine = next((_class for _class in classes if _class.__base__ is BaseEngine), None)

    if engine:
        engine_map[engine.__name__] = len(engines)
        engines.append(engine())
    else:
        print(f"Failed to find engine class in {engine_file.name}")


# Voice list
voices = []

for i, engine in enumerate(engines):
    engine_voices = engine.list_voices()
    voices.extend(engine_voices)

logging.info(f"Loaded {len(voices)} voices from {len(engines)} engines")
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post('/list-voices')
def list_voices(credentials: Credentials = Body(..., embed=True)) -> list[Voice]:
    return voices

@app.post('/synthesize-speech', responses = {
        200: {
            "content": {"audio/mp3": {}}
        }
    }, response_class=Response)
def synthesize_speech(credentials: Credentials, payload: SynthesizePayload):
    voice = payload.voice
    if voice not in voices:
        return Response(status_code=400, content="Voice not found")

    mp3_bytes = engines[engine_map[voice.category]].synthesize_voice(voice, payload.text)
    return Response(status_code=200, content=mp3_bytes, media_type='audio/mp3')

