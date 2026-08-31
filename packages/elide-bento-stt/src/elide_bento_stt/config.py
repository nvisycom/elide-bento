"""Service configuration, read from the environment.

A WhisperX pipeline serves the deployment: an ASR model named by
``ELIDE_BENTO_MODEL_NAME``, optional forced alignment for word timings, and
optional pyannote diarization for speaker labels. All knobs are env vars so
they show up in the bento manifest and can be set per deployment without a
code change.
"""

from __future__ import annotations

import os

# Compute type for faster-whisper ("int8" on CPU, "float16" on GPU).
COMPUTE_TYPE_ENV = "ELIDE_BENTO_STT_COMPUTE_TYPE"
# Device to run on ("cpu" or "cuda").
DEVICE_ENV = "ELIDE_BENTO_STT_DEVICE"
# Enable pyannote diarization (speaker labels). Off by default: it loads a
# second model, needs a gated HF token, and roughly doubles latency.
DIARIZE_ENV = "ELIDE_BENTO_STT_DIARIZE"
# HF token for the gated pyannote pipeline. Required only when diarizing.
HF_TOKEN_ENV = "ELIDE_BENTO_STT_HF_TOKEN"
# Diarization pipeline id.
DIARIZE_MODEL_ENV = "ELIDE_BENTO_STT_DIARIZE_MODEL"
# Enable wav2vec2 forced alignment for word-level timings. On by default:
# the contract carries per-word timings and raw Whisper does not produce them.
ALIGN_ENV = "ELIDE_BENTO_STT_ALIGN"
# Reject audio longer than this. Transcription is O(duration) and a long clip
# can occupy a worker for minutes.
MAX_DURATION_ENV = "ELIDE_BENTO_STT_MAX_DURATION_SECONDS"
# Bound the diarization search when the caller gives no hint.
MIN_SPEAKERS_ENV = "ELIDE_BENTO_STT_MIN_SPEAKERS"
MAX_SPEAKERS_ENV = "ELIDE_BENTO_STT_MAX_SPEAKERS"

# faster-whisper large-v3, MIT-licensed weights, the WhisperX default.
DEFAULT_MODEL = "large-v3"
# CC-BY-4.0 (gated on Hugging Face). Supersedes speaker-diarization-3.1 and
# is WhisperX's current default reference.
DEFAULT_DIARIZE_MODEL = "pyannote/speaker-diarization-community-1"
DEFAULT_MAX_DURATION_SECONDS = 3600


def compute_type() -> str:
    return os.getenv(COMPUTE_TYPE_ENV) or ("float16" if device() == "cuda" else "int8")


def device() -> str:
    return os.getenv(DEVICE_ENV) or "cpu"


def diarize() -> bool:
    return _flag(DIARIZE_ENV)


def align() -> bool:
    # On unless explicitly disabled.
    return os.getenv(ALIGN_ENV, "1").strip().lower() not in {"0", "false", "no", ""}


def hf_token() -> str | None:
    return os.getenv(HF_TOKEN_ENV) or None


def diarize_model() -> str:
    return os.getenv(DIARIZE_MODEL_ENV) or DEFAULT_DIARIZE_MODEL


def max_duration_seconds() -> int:
    return _positive_int(MAX_DURATION_ENV, DEFAULT_MAX_DURATION_SECONDS)


def min_speakers() -> int | None:
    return _optional_positive_int(MIN_SPEAKERS_ENV)


def max_speakers() -> int | None:
    return _optional_positive_int(MAX_SPEAKERS_ENV)


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be positive, got {value}")
    return value


def _optional_positive_int(name: str) -> int | None:
    raw = os.getenv(name)
    return _positive_int(name, 0) if raw else None
