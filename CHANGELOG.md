# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- BentoML inference services implementing
  [elide](https://github.com/nvisycom/elide)'s recognizer contracts
- Named-entity recognition service backed by GLiNER2, with schema-driven
  label configuration
- OCR service backed by docTR
- Vision-language OCR verification service backed by PaddleOCR-VL
- Shared wire-contract schema and types consumed by every service
- Rust client crate (`elide-bento`) implementing the `NerBackend`,
  `OcrBackend`, and `SttBackend` traits against these services
- Per-service `requirements.txt` generation from `uv.lock`
  (`scripts/gen_requirements.py`), enforced in CI
- Container image publishing to `ghcr.io/nvisycom/elide-bento-*`
- Rust CI: format, check, clippy, docs, test, release build, unused-dependency
  detection, and `cargo-deny`
- Python CI: ruff lint and format, requirements drift check, pytest, and
  `pip-audit`, plus a weekly real-model test run
- Automatic regeneration of service requirements on Dependabot pull requests

### Packages

- **bento-core:** Shared wire-contract schema and types
- **bento-gliner2:** Named-entity recognition service (GLiNER2)
- **bento-doctr:** OCR service (docTR)
- **bento-paddleocr:** Vision-language OCR verification service (PaddleOCR-VL)

### Crates

- **elide-bento:** Rust client implementing elide's NER, OCR, and STT backend
  traits against the BentoML services

### Notes

- The crate's `stt` feature targets an `bento-whisper` service that is not
  yet part of this repository. The backend is implemented and compiles, but
  has no service to talk to until that package lands.
- The `elide-*` dependencies track `main` rather than a tagged release, since
  elide publishes no tags yet. This matches how `nvisycom/runtime` pins them.
