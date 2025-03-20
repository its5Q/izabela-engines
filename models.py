from pydantic import BaseModel

class Credentials(BaseModel):
    apiKey: str

class Voice(BaseModel):
    id: str
    name: str
    category: str # Stores the engine class where the voice originates from
    languageCode: str

class SynthesizePayload(BaseModel):
    text: str
    voice: Voice