# Ready to post — Show HN

## Title

Show HN: VHScribe – browser-controlled VHS capture for a headless Linux server

## Post

Digitising one VHS tape is a long, real-time job, and I wanted the capture to survive a closed or
disconnected browser. VHScribe is an open-source, local-first application I built to control a USB
capture adapter from a browser while recording runs on a headless Linux server.

FastAPI owns one FFmpeg process, which avoids the common problem of preview and recording competing
for V4L2/ALSA devices. FFmpeg writes a recoverable MKV master and publishes a separate low-latency
stream to MediaMTX for WebRTC preview. Interrupted partials are never automatically deleted.

The repository includes Docker Compose, read-only device discovery, synthetic end-to-end tests,
and manual GHCR release automation. PAL/NTSC masters retain 720×576 or 720×480 dimensions and carry
4:3 display metadata. Current physical validation is deliberately narrow: an EasierCAP-branded
MS210x adapter, PAL, Ubuntu 24.04, and amd64. The service has no authentication and defaults to
loopback.

OpenAI Codex assisted extensively with the code, tests, audit, and documentation; OpenAI does not
endorse the project. I would appreciate critique of the failure model and install path, plus
privacy-safe testing on additional capture devices, physical NTSC input, and ARM64 hardware.

https://github.com/paulcakeface/vhscribe
