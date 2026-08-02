# Contributing to VHScribe

Thank you for helping make tape preservation more approachable. Focused bug fixes, documentation
improvements, synthetic tests, and clearly described hardware results are welcome.

## Before opening an issue

Search existing issues, run `./scripts/verify-installation.sh`, and collect only diagnostics that
are safe to publish. Remove recording names, paths, LAN addresses, USB serial numbers, and anything
from `.env`. Never upload a private recording just to demonstrate a bug; synthetic input or a short
purpose-made test signal is preferred.

## Development workflow

1. Fork the repository and create a narrowly scoped branch.
2. Follow [docs/development.md](docs/development.md) to create a virtual environment.
3. Add tests for behavioral changes. Hardware-independent code must work with synthetic input.
4. Run Ruff, Pytest, Compose validation, and the synthetic smoke test.
5. Update documentation and `CHANGELOG.md` when users will notice the change.
6. Open a pull request using the template and explain validation and rollback implications.

Do not add `privileged: true`, shell-built FFmpeg commands, automatic partial-file deletion, or a
second process that can open the capture hardware. Changes to these safety invariants need an
architecture discussion first.

## Commits and pull requests

Use clear imperative commit subjects, keep unrelated refactors separate, and avoid generated media
or lock-step formatting churn. By contributing, you agree that your contribution is licensed under
the repository's MIT License.

## Hardware reports

State what you directly tested: operating system, CPU architecture, capture-card identity, driver,
video standard, advertised V4L2 mode, ALSA source, and test duration. Mark inferences as such and
redact serial numbers. A successful synthetic run does not count as hardware validation.
