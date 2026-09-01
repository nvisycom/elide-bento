"""Tests for the audio ingress path.

These cover `_decode_audio`'s guards, which run before any model is touched,
so they need no weights.
"""

import base64
import io
import struct
import wave

import pytest
from bento_whisper.service import SAMPLE_RATE, _decode_audio
from bentoml.exceptions import InvalidArgument


def _wav_b64(seconds: float, rate: int = SAMPLE_RATE) -> str:
    """A base64 silent mono WAV of the given length."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = int(seconds * rate)
        w.writeframes(struct.pack(f"<{frames}h", *([0] * frames)))
    return base64.b64encode(buf.getvalue()).decode()


def test_decodes_wav_to_waveform():
    waveform = _decode_audio(_wav_b64(0.5))
    # Half a second at the target rate, within a resampling frame or two.
    assert abs(len(waveform) - SAMPLE_RATE // 2) < 100


def test_rejects_non_base64():
    with pytest.raises(InvalidArgument, match="valid base64"):
        _decode_audio("not base64!!")


def test_rejects_empty_payload():
    with pytest.raises(InvalidArgument, match="empty"):
        _decode_audio("")


def test_rejects_undecodable_bytes():
    with pytest.raises(InvalidArgument, match="not decodable"):
        _decode_audio(base64.b64encode(b"this is not audio").decode())


def test_oversized_payload_rejected_before_decode():
    """The byte cap rejects a long payload without decoding it.

    The point of the guard: an over-long input must not be fully decoded and
    resampled into memory before the duration check rejects it.
    """
    with pytest.raises(InvalidArgument, match="the limit is"):
        _decode_audio(_wav_b64(2.0), max_seconds=0.5)


def test_decode_is_bounded_by_max_seconds():
    """A payload within the byte cap still decodes no more than the bound.

    A highly compressed input can pass the byte check and still be long, so
    the decode itself is capped too.
    """
    waveform = _decode_audio(_wav_b64(1.0), max_seconds=10.0)
    assert abs(len(waveform) - SAMPLE_RATE) < 100
