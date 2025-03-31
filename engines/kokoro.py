import io
import time
import urllib.request
import soundfile as sf
import os

import torch

from engines.base import BaseEngine
from models import Voice
import logging
from kokoro import KPipeline, KModel
from pathlib import Path

logging.basicConfig(level=logging.INFO)

class KokoroEngine(BaseEngine):
    def __init__(self):
        self._g2p = None
        self.loaded_voice = 'af_heart'

        logging.info("Loading Kokoro model...")
        self._model = KModel('hexgrad/Kokoro-82M').to('cuda' if os.environ.get('IZABELA_USE_CUDA') else 'cpu').eval()
        self._pipeline = KPipeline('a', model=self._model)

        # TODO: figure out how to get triton working on Windows so we can compile models
        # logging.info("Compiling Kokoro model. This might take some time, but will make the model run much faster.")
        # self._model.compile()

    def list_voices(self) -> list[Voice]:
        lang_map = {'a': 'en-us', 'b': 'en-gb', 'e': 'es', 'f': 'fr-fr', 'h': 'hi', 'i': 'it', 'p': 'pt-br', 'j': 'ja', 'z': 'zh'}
        voices = []
        for voice in ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "bm_fable", "bm_george", "bm_lewis", "ef_dora", "em_alex", "em_santa", "ff_siwis", "hf_alpha", "hf_beta", "hm_omega", "hm_psi", "if_sara", "im_nicola", "jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo", "pf_dora", "pm_alex", "pm_santa", "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi", "zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang"]:
            voices.append(Voice(
                id=voice,
                name='Kokoro - ' + voice.split('_')[1].capitalize() + ' (' + ('Male' if voice[1] == 'm' else 'Female') + ') (' + lang_map[voice[0]] + ')',
                category=self.__class__.__name__,
                languageCode=lang_map[voice[0]]
            ))

        return voices

    def synthesize_voice(self, voice: Voice, text: str) -> bytes:
        if self.loaded_voice[0] != voice.id[0]:
            logging.info(f'Loading pipeline for language {voice.languageCode}...')
            self._pipeline = KPipeline(voice.id[0], model=self._model)
            self.loaded_voice = voice.id

        start_time = time.time()
        generator = self._pipeline(text, voice=voice.id)
        samples = None
        for i, (gs, ps, audio) in enumerate(generator):
            if samples is None:
                samples = audio
            else:
                samples = torch.cat((samples, audio))
        end_time = time.time()
        logging.info(f"Generation took {end_time - start_time} seconds")
        mp3_bytes = io.BytesIO()
        sf.write(file=mp3_bytes, samplerate=24000, data=samples, format='MP3', bitrate_mode='VARIABLE', compression_level=0.25)
        return mp3_bytes.getvalue()
