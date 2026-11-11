from collections.abc import Iterable, Iterator
import io

import numpy as np
import soundfile as sf

from models import Voice

SILENCE_DURATION_SECONDS = 0.1
MP3_COMPRESSION_LEVEL = 0.25


class MP3StreamBuffer:
    """Append-only file-like sink for incremental libsndfile CBR MP3 encoding."""

    def __init__(self) -> None:
        self._pending = bytearray()
        self._pos = 0
        self._length = 0

    def write(self, data: bytes | memoryview) -> int:
        chunk = bytes(data)
        end = self._pos + len(chunk)
        if end > self._length:
            new_start = max(0, self._length - self._pos)
            new_bytes = chunk[new_start:]
            # Skip libsndfile's reserved Xing/Info header frame at offset 0
            # (4-byte MPEG sync word followed by zeros, normally rewritten via seek on close).
            if not (self._length == 0 and len(new_bytes) > 4 and not any(new_bytes[4:])):
                self._pending.extend(new_bytes)
            self._length = end
        self._pos = end
        return len(chunk)

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self._pos = offset
        elif whence == 1:
            self._pos += offset
        elif whence == 2:
            self._pos = self._length + offset
        return self._pos

    def tell(self) -> int:
        return self._pos

    def flush(self) -> None:
        pass

    def drain(self) -> bytes:
        data = bytes(self._pending)
        self._pending.clear()
        return data


def make_silence(sample_rate: int, duration: float = SILENCE_DURATION_SECONDS) -> np.ndarray:
    return np.zeros(int(sample_rate * duration), dtype=np.float32)


def encode_mp3(
    samples: np.ndarray,
    sample_rate: int,
    compression_level: float = MP3_COMPRESSION_LEVEL,
) -> bytes:
    mp3_bytes = io.BytesIO()
    sf.write(
        file=mp3_bytes,
        samplerate=sample_rate,
        data=samples,
        format="MP3",
        bitrate_mode="VARIABLE",
        compression_level=compression_level,
    )
    return mp3_bytes.getvalue()


def encode_silence_mp3(
    sample_rate: int,
    duration: float = SILENCE_DURATION_SECONDS,
    compression_level: float = MP3_COMPRESSION_LEVEL,
) -> bytes:
    return encode_mp3(
        make_silence(sample_rate, duration),
        sample_rate=sample_rate,
        compression_level=compression_level,
    )


def stream_mp3(
    pcm_chunks: Iterable[np.ndarray],
    sample_rate: int,
    channels: int = 1,
    compression_level: float = MP3_COMPRESSION_LEVEL,
) -> Iterator[bytes]:
    stream_buffer = MP3StreamBuffer()
    wrote_audio = False

    with sf.SoundFile(
        file=stream_buffer,
        mode="w",
        samplerate=sample_rate,
        channels=channels,
        format="MP3",
        bitrate_mode="CONSTANT",
        compression_level=compression_level,
    ) as mp3_file:
        for samples in pcm_chunks:
            if samples is None or len(samples) == 0:
                continue
            wrote_audio = True
            mp3_file.write(samples)
            chunk = stream_buffer.drain()
            if chunk:
                yield chunk

        if not wrote_audio:
            mp3_file.write(make_silence(sample_rate))
            chunk = stream_buffer.drain()
            if chunk:
                yield chunk

    tail = stream_buffer.drain()
    if tail:
        yield tail


class BaseEngine:
    models_path: str = None

    def __init__(self):
        raise NotImplementedError("Can't instantiate base class")

    @property
    def supports_streaming(self) -> bool:
        return type(self).synthesize_voice_stream is not BaseEngine.synthesize_voice_stream

    def list_voices(self) -> list[Voice]:
        raise NotImplementedError()

    def synthesize_voice(self, voice: Voice, text: str) -> bytes:
        raise NotImplementedError()

    def synthesize_voice_stream(self, voice: Voice, text: str) -> Iterator[bytes]:
        raise NotImplementedError()