from models import Voice

class BaseEngine:
    models_path: str = None

    def __init__(self):
        raise NotImplementedError("Can't instantiate base class")

    def list_voices(self) -> list[Voice]:
        raise NotImplementedError()

    def synthesize_voice(self, voice: Voice, text: str) -> bytes:
        raise NotImplementedError()