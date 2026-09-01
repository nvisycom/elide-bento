"""Speech-to-text inference service (faster-whisper) exposed over HTTP via BentoML.

The default implementation of the STT wire contract
(``bento_core.stt.v1``), and the service the Rust client's ``BentoStt``
backend has always been written against.

Diarization is opt-in (``ELIDE_BENTO_STT_DIARIZE``): it loads a second, gated
model and roughly doubles latency, so a deployment that does not need speaker
labels should not pay for them.

Run locally::

    ELIDE_BENTO_MODEL_NAME=large-v3-turbo \\
        uv run bentoml serve bento_whisper.service:SttService --reload
"""

from __future__ import annotations

import base64
import binascii
import io

import bentoml
from bento_core.runtime import get_logger, request_id
from bento_core.stt.v1 import SttRequest, SttResponse
from bentoml.exceptions import BentoMLException, InternalServerError, InvalidArgument
from prometheus_client import Histogram

from bento_whisper.engine import SAMPLE_RATE, AudioTooLongError, Engine

logger = get_logger("nvisy.stt")

# faster-whisper large-v3-turbo: MIT, 99 languages, native word timestamps,
# 2-5x faster than large-v3 for a small accuracy cost (a pruned 4-layer
# decoder). Declared as the ELIDE_BENTO_MODEL_NAME default below (single
# source of truth).
#
# Not the WER leader on the Open ASR Leaderboard - roughly ten open models
# score better - but the leaders (Parakeet, Canary, Voxtral) each need NeMo or
# vLLM, are GPU-bound, and several are English-only. This picks ecosystem fit
# and CPU viability over raw accuracy; see the README.
DEFAULT_MODEL = "large-v3-turbo"

duration_metric = Histogram(
    "bento_whisper_audio_seconds",
    "Duration of audio submitted to one transcribe() call.",
    buckets=(5, 15, 30, 60, 300, 900, 3600),
)

# BentoML builds the image from this config (`bentoml build` + `containerize`);
# no hand-written Dockerfile. The requirements file is exported per-service from
# the workspace lock (scripts/gen_requirements.py); bundled source is scoped by
# bentofile.yaml's `include`. ffmpeg decodes the input containers.
# lock_python_packages=False: the file is already locked + hashed, so BentoML
# must not re-resolve it.
image = (
    bentoml.images.Image(python_version="3.12", lock_python_packages=False)
    .system_packages("ffmpeg")
    .requirements_file("packages/bento-whisper/requirements.txt")
)


@bentoml.service(
    name="bento-whisper",
    image=image,
    resources={"cpu": "4"},
    # Transcription is O(audio duration); a long clip legitimately takes
    # minutes, so the ceiling is well above the other services'.
    traffic={"timeout": 900},
    envs=[
        {"name": "ELIDE_BENTO_MODEL_PATH", "value": "/models"},
        {"name": "ELIDE_BENTO_MODEL_NAME", "value": DEFAULT_MODEL},
    ],
)
class SttService:
    def __init__(self) -> None:
        logger.info("loading faster-whisper")
        self.engine = Engine()
        logger.info(
            "engine ready (model=%s device=%s diarize=%s)",
            self.engine.model_id,
            self.engine.device,
            self.engine.diarizes,
        )

    # Not batchable: clips vary from seconds to an hour, so batching would let
    # one long clip hold short ones hostage behind it. Sync (not async):
    # inference is CPU/GPU-bound and blocking, and BentoML runs sync endpoints
    # in a managed thread pool, so this never blocks the event loop.
    @bentoml.api
    def transcribe(self, request: SttRequest, ctx: bentoml.Context) -> SttResponse:
        rid = request_id(ctx)
        limit = self.engine.max_duration_seconds
        # Decode is bounded by the limit rather than checked after it: a long
        # compressed input would otherwise be fully decoded and resampled into
        # memory before being rejected. One extra second is decoded so an
        # over-length clip is still detectable as over-length.
        audio = _decode_audio(request.audio, max_seconds=limit + 1)

        try:
            seconds = self.engine.check_duration(audio)
        except AudioTooLongError as exc:
            raise InvalidArgument(str(exc)) from exc

        duration_metric.observe(seconds)
        logger.info("transcribe seconds=%.1f req_id=%s", seconds, rid)

        try:
            return self.engine.transcribe(audio, language=request.language)
        except BentoMLException:
            # Typed request errors carry their own status; let them through.
            raise
        except Exception as exc:
            logger.exception("inference failed (req_id=%s)", rid)
            raise InternalServerError("STT inference failed") from exc


def _decode_audio(audio_b64: str, max_seconds: float | None = None):
    """Base64 audio bytes to a mono 16 kHz float32 waveform.

    Decoding goes through ffmpeg (via ``soundfile``/``librosa``) so any
    container the deployment's ffmpeg understands is accepted. A payload that
    is not decodable audio is a 400, not a 500 — it is the caller's input.

    ``max_seconds`` bounds the decode itself, so an over-long input costs the
    worker one bounded read rather than a full decode and resample of however
    much audio the caller sent. The compressed payload is capped first, since
    even the decode's own buffer is the caller's to inflate.
    """
    try:
        raw = base64.b64decode(audio_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InvalidArgument("audio is not valid base64") from exc
    if not raw:
        raise InvalidArgument("audio is empty")
    if max_seconds is not None:
        # A generous ceiling on the compressed bytes: uncompressed 16-bit mono
        # PCM at the target rate is the worst realistic case, so anything past
        # it cannot be within the duration limit whatever the codec.
        max_bytes = int(max_seconds * SAMPLE_RATE * 2)
        if len(raw) > max_bytes:
            raise InvalidArgument(
                f"audio is {len(raw)} bytes; the limit is {max_bytes} "
                f"({max_seconds:.0f}s of uncompressed audio)"
            )

    import librosa

    try:
        waveform, _ = librosa.load(io.BytesIO(raw), sr=SAMPLE_RATE, mono=True, duration=max_seconds)
    except Exception as exc:
        raise InvalidArgument("audio bytes are not decodable audio") from exc
    if waveform.size == 0:
        raise InvalidArgument("audio decodes to an empty waveform")
    return waveform
