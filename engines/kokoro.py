import io
import time
import urllib.request
import soundfile as sf
import os

from engines.base import BaseEngine
from models import Voice
import logging
from kokoro_onnx import Kokoro
from pathlib import Path
from misaki import espeak, en, zh, ja
from misaki.espeak import EspeakG2P

logging.basicConfig(level=logging.INFO)

class KokoroEngine(BaseEngine):
    models_path = Path("models/kokoro")

    def __init__(self):
        self._g2p = None
        self.loaded_voice = None

        logging.info("Loading Kokoro model...")
        if not self.models_path.exists():
            self.models_path.mkdir(parents=True)

        if not (self.models_path / "kokoro-v1.0.onnx").exists():
            logging.info("Models not found locally, downloading... (~115MB)")
            # if os.environ.get("IZABELA_USE_CUDA"):
            #     model_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.fp16-gpu.onnx"
            # else:
            #     model_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx"
            with urllib.request.urlopen("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.fp16-gpu.onnx") as resp:
                with open(self.models_path / "kokoro-v1.0.onnx", "wb") as f:
                    f.write(resp.read())

            with urllib.request.urlopen("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin") as resp:
                with open(self.models_path / "voices-v1.0.bin", "wb") as f:
                    f.write(resp.read())

        if os.environ.get("IZABELA_USE_CUDA"):
            os.environ["ONNX_PROVIDER"] = "CUDAExecutionProvider"
        self._model = Kokoro(str((self.models_path / "kokoro-v1.0.onnx").absolute()), str((self.models_path / "voices-v1.0.bin").absolute()))

    def list_voices(self) -> list[Voice]:
        lang_map = {'a': 'en-us', 'b': 'en-gb', 'e': 'es', 'f': 'fr-fr', 'h': 'hi', 'i': 'it', 'p': 'pt-br', 'j': 'ja', 'z': 'zh'}
        voices = []
        for voice in self._model.get_voices():
            voices.append(Voice(
                id=voice,
                name=voice.split('_')[1].capitalize() + ' (' + ('Male' if voice[1] == 'm' else 'Female') + ') (' + lang_map[voice[0]] + ')',
                category=self.__class__.__name__,
                languageCode=lang_map[voice[0]]
            ))

        return voices

    def synthesize_voice(self, voice: Voice, text: str) -> bytes:
        if self.loaded_voice != voice.id:
            if voice.languageCode in {'en-us', 'en-gb'}:
                fallback = espeak.EspeakFallback(british=voice.languageCode == 'en-gb')
                self._g2p = en.G2P(trf=False, british=voice.languageCode == 'en-gb', fallback=fallback)
            elif voice.languageCode == 'fr-fr':
                self._g2p = EspeakG2P(language='fr-fr')
            elif voice.languageCode == 'es':
                self._g2p = EspeakG2P(language='es')
            elif voice.languageCode == 'hi':
                self._g2p = EspeakG2P(language='hi')
            elif voice.languageCode == 'it':
                self._g2p = EspeakG2P(language='it')
            elif voice.languageCode == 'pt-br':
                self._g2p = EspeakG2P(language='pt-br')
            elif voice.languageCode == 'ja':
                self._g2p = ja.JAG2P()
            elif voice.languageCode == 'zh':
                self._g2p = zh.ZHG2P()
            self.loaded_voice = voice.id

        start_time = time.time()
        phonemes, _ = self._g2p(text)
        end_time = time.time()
        logging.info(f"Phonemization took {end_time - start_time} seconds")

        start_time = time.time()
        samples, sample_rate = self._model.create(phonemes, voice=voice.id, is_phonemes=True)
        end_time = time.time()
        logging.info(f"Model inference took {end_time - start_time} seconds")
        mp3_bytes = io.BytesIO()
        sf.write(file=mp3_bytes, samplerate=sample_rate, data=samples, format='MP3', bitrate_mode='VARIABLE', compression_level=0.25)
        return mp3_bytes.getvalue()
