# elide-bento-stt

Speech-to-text inference service for the elide toolkit, implementing the
`elide_bento_core.stt.v1` wire contract over BentoML. This is the service the
Rust client's `BentoStt` backend targets.

The pipeline is [WhisperX](https://github.com/m-bain/whisperX): faster-whisper
for transcription, wav2vec2 forced alignment for word-level timings, and
optional [pyannote](https://github.com/pyannote/pyannote-audio) diarization for
speaker labels.

## Status: not yet installable

The `whisperx` dependency is **commented out in `pyproject.toml`** because it
cannot currently coexist with the NER service in this workspace's single lock:

| | needs |
|---|---|
| `elide-bento-ner` | `transformers>=5.15.0` → `huggingface-hub>=1.5.0` |
| `whisperx` (all releases ≤3.8.6) | `huggingface-hub<1.0.0` |

Everything else here — the wire contract, the engine mapping, the service, the
tests — is complete and passing. Only the engine's `import whisperx` cannot run
until one of these resolves:

1. **WhisperX relaxes its pin.** It is a transitive constraint from
   `pyannote-audio`/`faster-whisper`, and upstream is active, so this may fix
   itself.
2. **Split the lock.** Give STT its own resolution rather than sharing the
   workspace's, at the cost of the single-lock invariant the repo relies on
   (`scripts/gen_requirements.py` exports per-service requirements from it).
3. **Drop WhisperX for its parts.** `faster-whisper` + `pyannote-audio`
   directly, doing alignment and speaker assignment in `engine.py`. More code,
   no version ceiling.

## Endpoint

`POST /transcribe` — base64 audio in, segments out:

```jsonc
// request
{ "audio": "<base64>", "filename": "call.wav", "language": "en" }

// response
{
  "segments": [
    { "startMs": 0, "endMs": 2400, "text": "Hello there.",
      "speakerId": "SPEAKER_00", "language": "en", "confidence": 0.94,
      "words": [{ "startMs": 0, "endMs": 480, "text": "Hello", "confidence": 0.97 }] }
  ],
  "modelId": "large-v3-turbo", "language": "en", "durationMs": 2400
}
```

Timings are **integer milliseconds**. WhisperX works in float seconds; the
conversion happens once, at the engine boundary.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ELIDE_BENTO_MODEL_NAME` | `large-v3-turbo` | faster-whisper model id |
| `ELIDE_BENTO_MODEL_PATH` | `/models` | BYO weights mount, when present |
| `ELIDE_BENTO_STT_DEVICE` | `cpu` | `cpu` or `cuda` |
| `ELIDE_BENTO_STT_COMPUTE_TYPE` | `int8` (cpu) / `float16` (cuda) | faster-whisper precision |
| `ELIDE_BENTO_STT_ALIGN` | on | wav2vec2 forced alignment for word timings |
| `ELIDE_BENTO_STT_DIARIZE` | off | pyannote speaker labels |
| `ELIDE_BENTO_STT_HF_TOKEN` | — | required when diarizing (gated model) |
| `ELIDE_BENTO_STT_DIARIZE_MODEL` | `pyannote/speaker-diarization-community-1` | diarization pipeline |
| `ELIDE_BENTO_STT_MIN_SPEAKERS` / `_MAX_SPEAKERS` | — | bound the speaker search |
| `ELIDE_BENTO_STT_MAX_DURATION_SECONDS` | `3600` | reject longer clips |

## Why `large-v3-turbo`

MIT-licensed, 99 languages, native word timestamps, and 2-5x faster than
`large-v3` (its decoder is pruned from 32 layers to 4) for a small accuracy
cost.

It is **not** the WER leader. On the
[Open ASR Leaderboard](https://huggingface.co/spaces/hf-audio/open_asr_leaderboard)
roughly ten open models score better — but each fails a bar that matters more
here:

| Model | Why not |
|---|---|
| NVIDIA Parakeet-TDT-0.6B-v3 | ~50x faster, but needs the NeMo runtime, is GPU-oriented, and covers 25 European languages rather than 99 |
| NVIDIA Canary-Qwen-2.5B | English-only |
| Mistral Voxtral Small | vLLM, ~55GB VRAM |
| ARK-ASR-3B, MOSS-Transcribe | Preview models from newer labs; licences not independently confirmed |

So this is a deliberate trade of raw accuracy for ecosystem fit, CPU viability
and language coverage — the same bar the NER service sets for its default
("Apache-2.0, CPU-viable, multilingual"). Parakeet is the one worth revisiting
if this service ever moves to GPU, and especially if the WhisperX dependency
is resolved by dropping WhisperX (see above), since that already means
rewriting the engine internals.

## Diarization

Off by default, deliberately: it loads a second model, roughly doubles
latency, and the pipeline is **gated on Hugging Face**. To enable it, accept
the model's terms on its HF page, then set `ELIDE_BENTO_STT_DIARIZE=1` and
`ELIDE_BENTO_STT_HF_TOKEN`.

The default pipeline `pyannote/speaker-diarization-community-1` is CC-BY-4.0.
Note this differs from the Apache-2.0 weights the other services default to —
if your deployment has a licence policy, check it before enabling.

`speakerId` is the engine's own label (`SPEAKER_00`, …). It groups segments
*within one transcript*; it is not a stable identity across calls.

## Run locally

Not yet possible — see the status section above. Once `whisperx` is
installable, this is the command, and `make serve-stt` wraps it:

```bash
uv run bentoml serve elide_bento_stt.service:SttService --reload
```
