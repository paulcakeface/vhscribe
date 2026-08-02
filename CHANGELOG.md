# Changelog

Notable user-facing changes are documented here. This project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) and the structure of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Planned

- Collect community hardware compatibility results.

## [0.1.0] - 2026-08-02

### Added

- Browser dashboard for preview, recording control, disk status, and recent captures.
- Server-side recording that continues independently of the controlling browser.
- Low-latency WebRTC preview through MediaMTX.
- PAL and NTSC profiles with native encoded dimensions and explicit 4:3 display signaling.
- Non-destructive interrupted-MKV recovery.
- Read-only hardware discovery in the CLI and dashboard, tested with an EasierCAP-branded
  MacroSilicon MS210x adapter.
- Private-by-default environment configuration and hardened Docker Compose deployment.
- Synthetic capture tests, CI, multi-architecture build checks, and public project documentation.

### Security

- Sanitized filenames and traversal-safe recording access.
- Shell-free FFmpeg process invocation.
- Loopback-only public defaults, read-only container filesystems, dropped capabilities, and no
  privileged containers.

[Unreleased]: https://github.com/paulcakeface/vhscribe/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/paulcakeface/vhscribe/releases/tag/v0.1.0
