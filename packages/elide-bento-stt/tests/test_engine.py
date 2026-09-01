"""Tests for the WhisperX result mapping.

These exercise `project()` and the seconds->milliseconds conversion against
fake WhisperX result dicts, so they need no model weights.
"""

import pytest
from elide_bento_stt.engine import _majority_speaker, _to_ms, project
from elide_bento_stt.service import DEFAULT_MODEL


def test_to_ms_rounds_not_truncates():
    # 1.9996s must not report 1999ms while the next word starts at 2000ms.
    assert _to_ms(1.9996) == 2000
    assert _to_ms(0.0) == 0
    assert _to_ms(1.5) == 1500


def test_to_ms_handles_absent_and_negative():
    assert _to_ms(None) is None
    # Alignment can emit a small negative start for a leading word.
    assert _to_ms(-0.01) == 0


def test_project_maps_segments_to_milliseconds():
    result = {"segments": [{"start": 0.0, "end": 2.4, "text": " Hello there. "}], "language": "en"}
    resp = project(result, "large-v3-turbo", "en", 2400)
    seg = resp.segments[0]
    assert (seg.start_ms, seg.end_ms) == (0, 2400)
    # Text is stripped: Whisper pads segments with a leading space.
    assert seg.text == "Hello there."
    assert seg.language == "en"
    assert resp.model_id == "large-v3-turbo" and resp.duration_ms == 2400


def test_project_drops_segments_without_timing():
    """A segment with no usable span is dropped, not given invented values."""
    result = {
        "segments": [
            {"start": None, "end": 1.0, "text": "no start"},
            {"start": 2.0, "end": 1.0, "text": "inverted"},
            {"start": 0.0, "end": 1.0, "text": "good"},
        ]
    }
    assert [s.text for s in project(result, "m", None, None).segments] == ["good"]


def test_project_maps_words_and_drops_unaligned():
    """Alignment leaves timings off words it cannot place; those are dropped."""
    result = {
        "segments": [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "Hi 42",
                "words": [
                    {"word": "Hi", "start": 0.0, "end": 0.4, "score": 0.97},
                    {"word": "42"},  # numerals often have no phoneme alignment
                ],
            }
        ]
    }
    words = project(result, "m", None, None).segments[0].words
    assert [w.text for w in words] == ["Hi"]
    assert words[0].end_ms == 400
    assert words[0].confidence == pytest.approx(0.97)


def test_project_prefers_whisperx_segment_speaker():
    result = {
        "segments": [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "x",
                "speaker": "SPEAKER_01",
                "words": [{"word": "x", "start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}],
            }
        ]
    }
    assert project(result, "m", None, None).segments[0].speaker_id == "SPEAKER_01"


def test_project_derives_speaker_from_words_when_absent():
    """Without a segment-level speaker, the majority word speaker is used."""
    result = {
        "segments": [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "a b c",
                "words": [
                    {"word": "a", "start": 0.0, "end": 0.3, "speaker": "SPEAKER_00"},
                    {"word": "b", "start": 0.3, "end": 0.6, "speaker": "SPEAKER_01"},
                    {"word": "c", "start": 0.6, "end": 1.0, "speaker": "SPEAKER_01"},
                ],
            }
        ]
    }
    assert project(result, "m", None, None).segments[0].speaker_id == "SPEAKER_01"


def test_no_speaker_when_not_diarized():
    result = {"segments": [{"start": 0.0, "end": 1.0, "text": "x"}]}
    assert project(result, "m", None, None).segments[0].speaker_id is None


def test_majority_speaker_ties_are_deterministic():
    assert _majority_speaker([{"speaker": "A"}, {"speaker": "B"}]) == "A"
    assert _majority_speaker([]) is None


def test_log_probability_is_not_reported_as_confidence():
    """faster-whisper's avg_logprob is not a [0,1] confidence; it must not leak."""
    result = {"segments": [{"start": 0.0, "end": 1.0, "text": "x", "avg_logprob": -0.35}]}
    assert project(result, "m", None, None).segments[0].confidence is None


def test_default_model_is_turbo():
    """The default is large-v3-turbo, not large-v3.

    Pinned deliberately: turbo is 2-5x faster for a small accuracy cost, and
    the choice is documented in the README. A silent revert to large-v3 would
    slow every deployment that does not set ELIDE_BENTO_MODEL_NAME.
    """
    assert DEFAULT_MODEL == "large-v3-turbo"


def test_missing_whisperx_explains_itself():
    """A missing `whisperx` names the dependency conflict, not just the module.

    The package is commented out in pyproject.toml, so a bare
    ModuleNotFoundError would look like a botched install rather than the
    deliberate workspace conflict it is.
    """
    import pytest
    from elide_bento_stt.engine import WhisperXUnavailableError, _import_whisperx

    try:
        import whisperx  # noqa: F401
    except ModuleNotFoundError:
        pass
    else:
        pytest.skip("whisperx is installed; the guard cannot trigger")

    with pytest.raises(WhisperXUnavailableError, match="huggingface-hub"):
        _import_whisperx()
