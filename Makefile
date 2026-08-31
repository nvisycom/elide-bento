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

# Python services, keyed by package suffix (packages/elide-bento-<suffix>).
# `stt` is intentionally absent: its whisperx dependency cannot resolve
# alongside elide-bento-ner yet (see packages/elide-bento-stt/README.md), so
# `build`/`build-image` would fail on it. Add it here once that is resolved.
SERVICES := ocr vl ner


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

.PHONY: serve-ocr
serve-ocr: ## Python: serve the OCR (docTR) service locally with reload.
	@$(call log,Serving elide-bento-ocr...)
	@uv run bentoml serve elide_bento_ocr.service:OcrService --reload

.PHONY: serve-vl
serve-vl: ## Python: serve the vision-language OCR (PaddleOCR-VL) service locally with reload.
	@$(call log,Serving elide-bento-vl...)
	@uv run bentoml serve elide_bento_vl.service:OcrVlService --reload

.PHONY: serve-ner
serve-ner: ## Python: serve the NER (GLiNER) service locally with reload.
	@$(call log,Serving elide-bento-ner...)
	@uv run bentoml serve elide_bento_ner.service:NerService --reload

.PHONY: serve-stt
serve-stt: ## Python: serve the STT (WhisperX) service locally with reload.
	@$(call log,Serving elide-bento-stt...)
	@uv run bentoml serve elide_bento_stt.service:SttService --reload

.PHONY: build
build: ## Python: build all Bentos from their bentofiles.
	@for s in $(SERVICES); do \
		$(call log,Building elide-bento-$$s...); \
		uv run bentoml build -f packages/elide-bento-$$s/bentofile.yaml . ; \
	done
	@$(call log,Bentos built.)

.PHONY: build-image
build-image: ## Python: build + containerize all Bentos into local Docker images.
	@for s in $(SERVICES); do \
		$(call log,Containerizing elide-bento-$$s...); \
		uv run bentoml build -f packages/elide-bento-$$s/bentofile.yaml --containerize . ; \
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
