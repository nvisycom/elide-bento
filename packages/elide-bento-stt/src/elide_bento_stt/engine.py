"""WhisperX engine: load the pipeline, transcribe, map onto the contract.

The heavy ``whisperx`` import lives inside :func:`_load` so importing this
module stays cheap.

The pipeline runs in up to three stages:

- **transcribe** (always): faster-whisper produces segments with float-second
  timings and no per-word detail.
- **align** (default on): wav2vec2 forced alignment adds per-word timings,
  which the wire contract carries and raw Whisper does not produce.
- **diarize** (opt-in): pyannote assigns a speaker label per word, which we
  fold up to the segment.

Translation happens at one boundary: WhisperX speaks **float seconds**, the
wire contract speaks **integer milliseconds**. :func:`_to_ms` is the only
place that conversion is allowed to happen.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from elide_bento_core.stt.v1 import Segment, SttResponse, Word

from elide_bento_stt import config

if TYPE_CHECKING:
    from collections.abc import Sequence


class AudioTooLongError(ValueError):
    """Audio exceeds the configured duration limit."""


def _to_ms(seconds: float | None) -> int | None:
    """Float seconds to whole milliseconds, or ``None`` when absent.

    Rounds rather than truncates so a word ending at 1.9996s does not report
    1999ms while the next starts at 2000ms. Negative values (which some
    alignment backends emit for a leading word) clamp to zero.
    """
    if seconds is None or (isinstance(seconds, float) and math.isnan(seconds)):
        return None
    return max(0, round(float(seconds) * 1000))


class Engine:
    """Owns the loaded WhisperX pipeline and the result translation."""

    def __init__(self) -> None:
        from elide_bento_core.runtime import resolve_model

        self.model_id = resolve_model()
        self.device = config.device()
        self.max_duration_seconds = config.max_duration_seconds()
        self._diarize = config.diarize()
        self._align = config.align()

        self._model = _load(self.model_id, self.device, config.compute_type())
        # Alignment models are per-language and loaded lazily on first use:
        # the language is not known until a clip has been transcribed.
        self._align_cache: dict[str, Any] = {}
        self._diarizer = _load_diarizer(self.device) if self._diarize else None

    def check_duration(self, audio: Sequence[float]) -> float:
        """Reject over-long audio, returning its duration in seconds.

        The duration is returned rather than discarded so the caller can report
        it without measuring the clip a second time.
        """
        seconds = len(audio) / SAMPLE_RATE
        if seconds > self.max_duration_seconds:
            raise AudioTooLongError(
                f"audio is {seconds:.1f}s; the limit is {self.max_duration_seconds}s"
            )
        return seconds

    def transcribe(self, audio: Any, language: str | None = None) -> SttResponse:
        """Run the pipeline over one clip and map it onto the contract."""
        whisperx = _import_whisperx()

        result = self._model.transcribe(audio, language=language)
        detected = result.get("language") or language

        if self._align and detected:
            aligner = self._alignment_model(detected)
            if aligner is not None:
                model_a, metadata = aligner
                result = whisperx.align(
                    result["segments"],
                    model_a,
                    metadata,
                    audio,
                    self.device,
                    return_char_alignments=False,
                )
                # `align` drops the language key; carry it forward.
                result["language"] = detected

        if self._diarizer is not None:
            diarization = self._diarizer(
                audio,
                min_speakers=config.min_speakers(),
                max_speakers=config.max_speakers(),
            )
            result = whisperx.assign_word_speakers(diarization, result)

        return project(result, self.model_id, detected, _to_ms(len(audio) / SAMPLE_RATE))

    def _alignment_model(self, language: str) -> tuple[Any, Any] | None:
        """The cached wav2vec2 aligner for ``language``, or ``None``.

        Alignment models do not exist for every language WhisperX can
        transcribe. A missing one is not an error: we fall back to
        segment-level timings and emit no words.
        """
        if language in self._align_cache:
            return self._align_cache[language]
        whisperx = _import_whisperx()

        try:
            model_a, metadata = whisperx.load_align_model(
                language_code=language, device=self.device
            )
        except (ValueError, KeyError):
            self._align_cache[language] = None
            return None
        self._align_cache[language] = (model_a, metadata)
        return self._align_cache[language]


# WhisperX resamples everything to 16 kHz mono on load.
SAMPLE_RATE = 16_000


class WhisperXUnavailableError(RuntimeError):
    """`whisperx` is not installed in this environment.

    Raised in place of a bare ``ModuleNotFoundError`` so the reason — a
    workspace dependency conflict, not a missing install step — is visible
    at the point of failure rather than only in the README.
    """

    def __init__(self) -> None:
        super().__init__(
            "whisperx is not installed. It pins huggingface-hub<1.0.0, which "
            "conflicts with elide-bento-ner's transformers>=5.15.0, so it is "
            "commented out in packages/elide-bento-stt/pyproject.toml. See "
            "that package's README for the three ways to resolve it."
        )


def _import_whisperx():
    """The `whisperx` module, or a pointed error explaining its absence."""
    try:
        import whisperx
    except ModuleNotFoundError as exc:  # pragma: no cover - env-dependent
        raise WhisperXUnavailableError from exc
    return whisperx


def _load(model_id: str, device: str, compute_type: str):
    whisperx = _import_whisperx()

    return whisperx.load_model(model_id, device, compute_type=compute_type)


def _load_diarizer(device: str):
    """The pyannote diarization pipeline.

    The model is gated on Hugging Face: without an accepted licence and a
    token the load fails, so we surface a pointed error rather than whatever
    huggingface_hub raises.
    """
    whisperx = _import_whisperx()

    token = config.hf_token()
    if not token:
        raise RuntimeError(
            f"{config.DIARIZE_ENV} is set but {config.HF_TOKEN_ENV} is not. "
            f"{config.diarize_model()} is gated: accept its terms on Hugging Face "
            "and supply a token."
        )
    return whisperx.DiarizationPipeline(
        model_name=config.diarize_model(), use_auth_token=token, device=device
    )


def project(
    result: dict[str, Any],
    model_id: str,
    language: str | None,
    duration_ms: int | None,
) -> SttResponse:
    """Map a WhisperX result dict onto the typed response.

    WhisperX segments carry float-second ``start``/``end``, ``text``, and —
    after alignment — a ``words`` list. After diarization each word may carry
    a ``speaker``; the segment's own ``speaker`` is WhisperX's majority vote,
    which we prefer when present and otherwise derive ourselves.

    Segments with no usable timing are dropped rather than emitted with
    invented values.
    """
    segments: list[Segment] = []
    for raw in result.get("segments", []):
        start_ms = _to_ms(raw.get("start"))
        end_ms = _to_ms(raw.get("end"))
        if start_ms is None or end_ms is None or end_ms < start_ms:
            continue

        words = [w for w in (_word(rw) for rw in raw.get("words", [])) if w is not None]
        segments.append(
            Segment(
                start_ms=start_ms,
                end_ms=end_ms,
                text=(raw.get("text") or "").strip(),
                speaker_id=raw.get("speaker") or _majority_speaker(raw.get("words", [])),
                language=raw.get("language") or language,
                confidence=_confidence(raw),
                words=words,
            )
        )

    return SttResponse(
        segments=segments, model_id=model_id, language=language, duration_ms=duration_ms
    )


def _word(raw: dict[str, Any]) -> Word | None:
    """One aligned word, or ``None`` when it has no usable timing.

    Alignment leaves timings off words it could not place (numerals and
    symbols with no phoneme mapping); such a word is dropped rather than
    emitted with a fabricated span.
    """
    start_ms = _to_ms(raw.get("start"))
    end_ms = _to_ms(raw.get("end"))
    text = (raw.get("word") or raw.get("text") or "").strip()
    if start_ms is None or end_ms is None or end_ms < start_ms or not text:
        return None
    return Word(start_ms=start_ms, end_ms=end_ms, text=text, confidence=_confidence(raw))


def _confidence(raw: dict[str, Any]) -> float | None:
    """A ``[0, 1]`` confidence from whichever key the stage used.

    Alignment reports ``score``; faster-whisper reports ``avg_logprob`` (a log
    probability, not a confidence). Only the former maps onto the contract, so
    a log-probability is left absent rather than squashed into a fake score.
    """
    score = raw.get("score")
    if score is None:
        return None
    value = float(score)
    if not 0.0 <= value <= 1.0:
        return None
    return value


def _majority_speaker(words: list[dict[str, Any]]) -> str | None:
    """The most common speaker across ``words``, or ``None``.

    Used only when WhisperX did not put a ``speaker`` on the segment itself.
    A tie resolves to whichever speaker appears first, keeping the result
    deterministic.
    """
    counts: dict[str, int] = {}
    for word in words:
        speaker = word.get("speaker")
        if speaker:
            counts[speaker] = counts.get(speaker, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda s: counts[s])
