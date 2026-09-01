# Makefile for the elide-bento workspace: Python BentoML packages
# (`packages/`) and the Rust client crate (`crates/`). Python targets
# are unsuffixed; Rust targets carry an `-rs` suffix.

# Default to a single recipe shell so a failure inside a piped
# command (e.g. server panics under `tee`) is reported by make.
.SHELLFLAGS := -eu -o pipefail -c
SHELL       := /bin/bash

# Timestamped log line, tagged with the running target. Use as `$(call log,msg)`.
define log
printf "[%s] [MAKE] [$(MAKECMDGOALS)] $(1)\n" "$$(date '+%Y-%m-%d %H:%M:%S')"
endef

# Python services, keyed by package suffix (packages/bento-<suffix>).
SERVICES := doctr paddleocr gliner2 whisper


# ─── Python ────────────────────────────────────────────────────

.PHONY: sync
sync: ## Python: install BentoML and all workspace dependencies into the venv.
	@$(call log,Syncing workspace...)
	@uv sync --all-packages
	@$(call log,Workspace ready.)

.PHONY: lint
lint: ## Python: ruff check + format check.
	@$(call log,Running ruff check...)
	@uv run ruff check .
	@$(call log,Running format check...)
	@uv run ruff format --check .
	@$(call log,Lint passed.)

.PHONY: fmt
fmt: ## Python: auto-format with ruff.
	@$(call log,Formatting...)
	@uv run ruff format .
	@uv run ruff check --fix .
	@$(call log,Formatted.)

.PHONY: test
test: ## Python: run the test suite.
	@$(call log,Running tests...)
	@uv run pytest

.PHONY: generate
generate: ## Python: regenerate per-service requirements.
	@$(call log,Regenerating service requirements...)
	@uv run python scripts/gen_requirements.py
	@$(call log,Generated.)

.PHONY: check
check: ## Python: fail if generated per-service requirements are stale (CI parity).
	@$(call log,Checking service requirements...)
	@uv run python scripts/gen_requirements.py --check
	@$(call log,Generated artifacts up to date.)

.PHONY: serve-doctr
serve-doctr: ## Python: serve the OCR (docTR) service locally with reload.
	@$(call log,Serving bento-doctr...)
	@uv run bentoml serve bento_doctr.service:OcrService --reload

.PHONY: serve-paddleocr
serve-paddleocr: ## Python: serve the vision-language OCR (PaddleOCR-VL) service locally with reload.
	@$(call log,Serving bento-paddleocr...)
	@uv run bentoml serve bento_paddleocr.service:OcrVlService --reload

.PHONY: serve-gliner2
serve-gliner2: ## Python: serve the NER (GLiNER) service locally with reload.
	@$(call log,Serving bento-gliner2...)
	@uv run bentoml serve bento_gliner2.service:NerService --reload

.PHONY: serve-whisper
serve-whisper: ## Python: serve the STT (faster-whisper) service locally with reload.
	@$(call log,Serving bento-whisper...)
	@uv run bentoml serve bento_whisper.service:SttService --reload

.PHONY: build
build: ## Python: build all Bentos from their bentofiles.
	@for s in $(SERVICES); do \
		$(call log,Building bento-$$s...); \
		uv run bentoml build -f packages/bento-$$s/bentofile.yaml . ; \
	done
	@$(call log,Bentos built.)

.PHONY: build-image
build-image: ## Python: build + containerize all Bentos into local Docker images.
	@for s in $(SERVICES); do \
		$(call log,Containerizing bento-$$s...); \
		uv run bentoml build -f packages/bento-$$s/bentofile.yaml --containerize . ; \
	done
	@$(call log,Images built.)

.PHONY: ci
ci: lint check test ## Python: full CI matrix.
	@$(call log,Python CI passed.)


# ─── Rust ──────────────────────────────────────────────────────
#
# Mirrors `.github/workflows/rust-build.yml`. `fmt-rs` and `doc-rs`
# need nightly: `rustfmt.toml` uses nightly-only options, and the
# `docsrs` cfg in `lib.rs` enables `feature(doc_cfg)`.

.PHONY: fmt-rs
fmt-rs: ## Rust: check formatting (nightly).
	@$(call log,Checking Rust formatting...)
	@cargo +nightly fmt --all --check

.PHONY: lint-rs
lint-rs: ## Rust: clippy with warnings denied.
	@$(call log,Running clippy...)
	@cargo clippy --workspace -- -D warnings
	@cargo clippy --workspace --all-features --all-targets -- -D warnings

.PHONY: test-rs
test-rs: ## Rust: run the test suite.
	@$(call log,Running Rust tests...)
	@cargo test --workspace
	@cargo test --workspace --all-features

.PHONY: doc-rs
doc-rs: ## Rust: build docs as docs.rs publishes them (nightly).
	@$(call log,Building Rust docs...)
	@RUSTDOCFLAGS="--cfg docsrs -D warnings" \
		cargo +nightly doc --workspace --no-deps --all-features

.PHONY: build-rs
build-rs: ## Rust: release build.
	@$(call log,Building release...)
	@cargo build --release

.PHONY: machete-rs
machete-rs: ## Rust: detect unused dependencies.
	@$(call log,Checking for unused dependencies...)
	@cargo machete

.PHONY: deny-rs
deny-rs: ## Rust: cargo-deny over advisories, bans, licenses, sources.
	@$(call log,Running cargo deny...)
	@cargo deny check all

# One target per `rust-build.yml` job, so a green `ci-rs` means the
# build workflow will be green too. `deny-rs` lives in `rust-security.yml`,
# not `rust-build.yml`, so it stays out of `ci-rs` — same split as the
# Python side, where `pip-audit` is outside `ci`.
.PHONY: ci-rs
ci-rs: fmt-rs lint-rs test-rs doc-rs build-rs machete-rs ## Rust: full CI matrix.
	@$(call log,Rust CI passed.)

# Both build workflows plus the Rust security scan.
.PHONY: ci-all
ci-all: ci ci-rs deny-rs ## Python + Rust: everything CI runs.
	@$(call log,All CI passed.)


# `help` parses the `## …` doc comment after each target name and
# prints `target — description`. Keeping help auto-generated from
# the targets themselves means new targets don't need a manual
# entry to show up.
.PHONY: help
help:  ## Show this help.
	@awk 'BEGIN { FS = ":.*## " } /^[a-zA-Z0-9_.-]+:.*## / { printf "  %-16s  %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
