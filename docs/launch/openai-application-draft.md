# OpenAI open-source application draft

## Project

VHScribe is a local-first web control panel for VHS capture hardware connected to a headless Linux
server. It combines a FastAPI control service, one supervised FFmpeg process, MediaMTX WebRTC
preview, and Docker Compose deployment.

## Problem

Digitising a tape is a long, real-time operation. Commodity USB adapters expose separate V4L2 video
and ALSA audio interfaces, device names vary, and an interruption near the end of a capture can
waste substantial time. Desktop capture software also assumes an operator sits at the machine
connected to the adapter. VHScribe gives a trusted local browser an intentionally small set of
controls while keeping the capture process and storage on a headless server.

## Preservation and accessibility value

Personal tapes can contain unique family, community, and local-history material. A self-hosted tool
helps owners keep that material on storage they control and makes the workflow accessible from
another device on the same trusted network. VHScribe preserves native PAL/NTSC encoded dimensions,
signals 4:3 display, validates normal stops, and retains interrupted partials for explicit recovery.
It does not claim that its default lossy profile replaces professional archival capture.

## How Codex contributed

Codex was used extensively as a development collaborator. It inspected an existing working capture
deployment, traced FFmpeg and MediaMTX behavior, implemented and reviewed application changes,
created regression and synthetic tests, checked generated media with `ffprobe`, improved container
configuration, performed publication/privacy and secret audits, and drafted operational and
community documentation. The maintainer supplied the hardware context, made scope decisions, and
retained responsibility for physical-signal and user-interface acceptance testing.

## Current adoption

At the v0.1.0 launch, the project has one private reference deployment. There are no claimed
external users, installations, stars, or outside contributors. Physical testing is limited to an
EasierCAP-branded adapter identified as MacroSilicon MS210x, with PAL input on Ubuntu Server
24.04/amd64.

## Maintenance plan

The maintainer plans to review security and dependency updates, keep synthetic CI reproducible,
triage focused bug reports, document evidence-backed hardware compatibility, and issue small
versioned releases. Recording-safety invariants—single device owner, validated completion, and no
automatic partial deletion—will remain review gates.

## Roadmap

- Collect structured hardware reports and validate more V4L2/ALSA adapters.
- Perform physical NTSC and arm64 capture tests.
- Add guided device/profile selection that always requires operator confirmation.
- Explore optional private-network authentication.
- Improve capture metrics, alerts, and preservation checksums.
- Evaluate conservative tape-end assistance without automatic truncation risk.

## How additional Codex or API support would help

Additional Codex access would help maintain the cross-cutting validation work that small hardware
projects often struggle to sustain: testing configuration permutations, reviewing FFmpeg command
changes, expanding privacy-safe diagnostics, keeping dependency and container automation current,
and turning real hardware bug reports into minimal synthetic reproductions. API support could also
enable an optional, locally controlled troubleshooting assistant in the future, but no recording or
private configuration would be sent externally by default. Any such feature would be separately
designed, disclosed, consent-based, and outside the v0.1.0 scope.

This application describes an independent project developed with extensive Codex assistance. It
does not imply endorsement by OpenAI.
