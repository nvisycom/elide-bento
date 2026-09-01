# Contributing

Thank you for your interest in contributing to elide-bento.

This repository is a polyglot workspace: Python [BentoML](https://bentoml.com)
inference services under `packages/`, and a Rust client crate under `crates/`.
Most changes touch one side or the other, and CI is split to match.

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/) — for the services
  (every `pyproject.toml` pins `requires-python = "==3.12.*"`)
- Rust 1.95+ (pinned in `rust-toolchain.toml`) — for the client crate
- Rust nightly — for `cargo fmt` and `cargo doc` only (see below)

Nightly is needed because `rustfmt.toml` uses nightly-only options
(`group_imports`, `imports_granularity`, `reorder_impl_items`) and the crate
gates its per-feature docs behind the `docsrs` cfg. Everything else builds on
the pinned stable toolchain.

```bash
rustup toolchain install nightly --component rustfmt
```

## Setup

```bash
git clone https://github.com/nvisycom/elide-bento.git
cd elide-bento

make sync        # Python: install all workspace dependencies
cargo build      # Rust: build the client crate
```

## Development

Run the checks CI runs, before opening a pull request:

```bash
make ci          # Python: ruff check, ruff format --check, requirements drift, pytest
make ci-rs       # Rust: fmt, clippy -D warnings, test, doc
make ci-all      # both
```

To auto-fix formatting:

```bash
make fmt                  # Python (ruff)
cargo +nightly fmt --all  # Rust
```

Individual Rust targets are also available: `fmt-rs`, `lint-rs`, `test-rs`,
`doc-rs`, `deny-rs`. Run `make help` for the full list.

### Service requirements

Each service ships a `packages/*/requirements.txt` that BentoML uses to build
its image. These are **generated** from `uv.lock` — do not edit them by hand:

```bash
make generate    # regenerate
make check       # fail if stale (this is what CI enforces)
```

Dependabot PRs that touch dependency descriptors regenerate these
automatically via `.github/workflows/dependabot-regen.yml`.

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run `make ci-all` to verify everything passes
5. Submit a pull request

CI is path-filtered: a change under `packages/` runs the Python workflows, a
change under `crates/` runs the Rust workflows. A change to both runs both.

## Project Structure

```text
crates/elide-bentoml/      Rust client for the services below
packages/bento-core/       Shared request/response contracts
packages/bento-gliner2/    Named-entity recognition (GLiNER2)
packages/bento-doctr/      OCR (docTR)
packages/bento-paddleocr/  Vision-language OCR (PaddleOCR-VL)
packages/bento-whisper/    Speech-to-text (faster-whisper + pyannote)
docs/design/               Per-service design notes
scripts/                   Repository tooling
```

The Rust crate implements the backend traits from
[elide](https://github.com/nvisycom/elide) against these services. Those crates
are consumed as git dependencies tracking `main`, matching how other
`nvisycom` repositories pin them.

## Security

- Never commit secrets or API keys
- Use environment variables for configuration
- Validate all external inputs

Python dependencies are audited with `pip-audit` and Rust dependencies with
`cargo-deny`; both run in CI and on a weekly schedule.

## License

By contributing, you agree your contributions will be licensed under the Apache
License 2.0.
