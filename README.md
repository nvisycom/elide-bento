# elide-bento

[![Build](https://img.shields.io/github/actions/workflow/status/nvisycom/elide-bento/build.yml?branch=main&label=build&style=flat-square)](https://github.com/nvisycom/elide-bento/actions/workflows/build.yml)
[![Security](https://img.shields.io/github/actions/workflow/status/nvisycom/elide-bento/security.yml?branch=main&label=security&style=flat-square)](https://github.com/nvisycom/elide-bento/actions/workflows/security.yml)

BentoML inference services implementing [elide](https://github.com/nvisycom/elide)'s
recognizer contracts.

A workspace that pairs three BentoML-hosted Python model services (plus a
shared contract library) with a Rust client that speaks their wire
contract. Any elide consumer — the
[runtime](https://github.com/nvisycom/runtime) engine, other
elide-embedding hosts — can drop this in as their `NerBackend` /
`OcrBackend` / `SttBackend` implementation. The Python side ships as
Docker containers deployed as sidecars; the Rust side is a library
crate the consumer embeds directly.

> [!WARNING]
> **Active development: API not stable.** This project is under active
> development. Public APIs, configuration shapes, and wire schemas may
> change without notice between releases. Pin a specific commit if you
> depend on this in production.

## Bring Your Own Inference

The Rust client speaks each service through its wire contract, not the
specific model behind it. Any HTTP service that reproduces the
`/recognize` (NER, OCR, VL) or `/transcribe` (STT) contract from
`bento-core` is a drop-in replacement for the shipped Python
packages, including self-hosted or custom models and weights. Each
package README documents its wire shape.

## Quick Start

The fastest way to get started is with [Nvisy Cloud](https://nvisy.com).

For self-hosted use, build and run each service with:

```bash
make sync            # install workspace deps
make serve-ner       # or serve-ocr, serve-vl
```

or build the Docker images:

```bash
make build           # every service
make build-image     # build + containerize
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, the local CI targets,
and the pull-request process. Notable changes are recorded in the
[CHANGELOG](CHANGELOG.md).

## License

Apache 2.0 License, see [LICENSE](LICENSE)

## Support

- **Documentation**: [docs.nvisy.com](https://docs.nvisy.com)
- **Issues**: [GitHub Issues](https://github.com/nvisycom/elide-bento/issues)
- **Email**: [support@nvisy.com](mailto:support@nvisy.com)
