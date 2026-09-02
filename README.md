<div align="center">

# Elide Provider

**Inference services implementing Elide's recognizer contracts.**

Self-hosted NER, OCR, and speech models behind one wire contract, with a
Rust client that speaks it.

[![Build](https://img.shields.io/github/actions/workflow/status/nvisycom/elide-provider/build.yml?branch=main&label=build&style=flat-square)](https://github.com/nvisycom/elide-provider/actions/workflows/build.yml)
[![Security](https://img.shields.io/github/actions/workflow/status/nvisycom/elide-provider/security.yml?branch=main&label=security&style=flat-square)](https://github.com/nvisycom/elide-provider/actions/workflows/security.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](LICENSE)

[**nvisy.com**](https://nvisy.com) · [**docs.nvisy.com**](https://docs.nvisy.com)

</div>

A workspace pairing BentoML-hosted Python model services with Rust client
crates that speak their wire contract. Any
[Elide](https://github.com/nvisycom/elide) consumer, including the
[Elide Runtime](https://github.com/nvisycom/elide-runtime) engine, drops these
in as its `NerBackend`, `OcrBackend`, or `SttBackend` implementation. The
Python side ships as Docker containers deployed as sidecars; the Rust side is
a library crate the consumer embeds directly.

> [!WARNING]
> **Active development: API not stable.** This project is under active
> development. Public APIs, configuration shapes, and wire schemas may
> change without notice between releases. Pin a specific commit if you
> depend on this in production.

## Services

**[bento-gliner2](packages/bento-gliner2)**  
Schema-driven NER and PII detection, so the labels to find are named per call rather than baked into the model.

**[bento-doctr](packages/bento-doctr)**  
The default OCR service, wrapping docTR.

**[bento-paddleocr](packages/bento-paddleocr)**  
Vision-language OCR verification, for text docTR reads with low confidence.

**[bento-whisper](packages/bento-whisper)**  
Speech-to-text, so audio reaches the same detection pipeline as text.

**[bento-core](packages/bento-core)**  
The wire-contract types the services share, and the definition a replacement reproduces.

## Clients

**[elide-bentoml](crates/elide-bentoml)**  
The Rust client for the services above, feature-gated per backend (`ner`, `ocr`, `stt`).

**[elide-gladia](crates/elide-gladia)**  
A Gladia-backed speech-to-text backend, for hosted transcription instead of self-hosted Whisper.

## Bring your own inference

The Rust client speaks each service through its wire contract, not the model
behind it. Any HTTP service reproducing the `/recognize` (NER, OCR, VL) or
`/transcribe` (STT) contract from [`bento-core`](packages/bento-core) is a
drop-in replacement for the shipped packages, including self-hosted or custom
models and weights. Each package README documents its wire shape.

## Quick Start

The fastest way to get started is with [Nvisy Cloud](https://nvisy.com).

For self-hosted use, build and run each service with:

```bash
make sync             # install workspace deps
make serve-gliner2    # or serve-doctr, serve-paddleocr, serve-whisper
```

or build the Docker images:

```bash
make build           # every service
make build-image     # build + containerize
```

## Project

- **Changelog**: [CHANGELOG.md](CHANGELOG.md) for release notes and version history
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md) for setup, local CI targets, and the pull-request process
- **License**: Apache 2.0, see [LICENSE](LICENSE)

## Support

- **Documentation**: [docs.nvisy.com](https://docs.nvisy.com)
- **Issues**: [GitHub Issues](https://github.com/nvisycom/elide-provider/issues)
- **Email**: [support@nvisy.com](mailto:support@nvisy.com)
