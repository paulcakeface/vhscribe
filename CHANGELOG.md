# Changelog

Notable user-facing changes are documented here. This project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) and the structure of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0] - 2026-08-16

### Added

- Explicit preview start, stop, and heartbeat API/dashboard controls with a configurable `PREVIEW_IDLE_TIMEOUT_SECONDS` inactivity timeout.
- Post-capture QC sidecars containing capture/build provenance, FFmpeg version, probe evidence, media-invariant results, warning evidence, and final `verified` / `needs_review` status.
- Optional SHA-256 recording fixity with `QC_CHECKSUM` and optional full-decode verification with `QC_FULL_DECODE`.
- QC state in the recent-recordings API and dashboard.
- Regression coverage for preview lifecycle, stronger finalisation, QC manifests, shutdown behaviour, and interrupted-recording recovery.

### Changed

- VHScribe now starts dormant without FFmpeg and releases capture devices when preview is unused.
- Recording can start from dormant or preview mode and returns to dormant mode after validation.
- Completed recordings now require video and audio plus the configured geometry, rational frame rate, sample aspect ratio, 4:3 display aspect, audio sample rate/channel count, and positive duration before a `.part.mkv` is promoted.
- Recovery now stream-copies through a temporary `.recovering.mkv`, requires both video and audio, preserves the original partial, and recognises an already recovered result.
- FFmpeg warning/progress evidence is retained in QC metadata so recoverable captures can be marked `needs_review` instead of silently appearing clean.
- Build version and source revision are embedded in the runtime and QC metadata.

### Fixed

- Failed finalisation no longer promotes an invalid partial recording.
- Failed recovery no longer leaves a transitional file in the normal recording catalogue.
- Repeated recovery no longer offers an impossible second recovery after a valid recovered output already exists.
- Recording startup is rejected once application shutdown has begun.
- The recording download route now serves only explicit completed media rather than arbitrary files from the capture directory.

### Security

- Preserved the private-by-default bind model and hardened Compose settings while tightening capture-directory file serving.

## [0.1.0] - 2026-08-02

### Added

- Browser dashboard for preview, recording control, disk status, and recent captures.
- Server-side recording that continues independently of the controlling browser.
- Low-latency WebRTC preview through MediaMTX.
- PAL and NTSC profiles with native encoded dimensions and explicit 4:3 display signaling.
- Non-destructive interrupted-MKV recovery.
- Read-only hardware discovery in the CLI and dashboard, tested with an EasierCAP-branded MacroSilicon MS210x adapter.
- Private-by-default environment configuration and hardened Docker Compose deployment.
- Synthetic capture tests, CI, multi-architecture build checks, and public project documentation.

### Security

- Sanitized filenames and traversal-safe recording access.
- Shell-free FFmpeg process invocation.
- Loopback-only public defaults, read-only container filesystems, dropped capabilities, and no privileged containers.

[Unreleased]: https://github.com/paulcakeface/vhscribe/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/paulcakeface/vhscribe/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/paulcakeface/vhscribe/releases/tag/v0.1.0
