# Show HN draft

## Title

Show HN: VHScribe – browser-controlled VHS capture for a headless Linux server

## Post

VHScribe is a small local-first application I built to control VHS digitisation hardware from a
browser while the USB capture adapter runs on a headless Linux server.

FastAPI owns one FFmpeg process, which avoids the common problem of preview and recording competing
for V4L2/ALSA devices. FFmpeg writes a recoverable MKV master and publishes a separate low-latency
stream to MediaMTX for WebRTC preview. Interrupted partials are never automatically deleted.

The repository includes Docker Compose, read-only device discovery, synthetic end-to-end tests,
and manual GHCR release automation. PAL/NTSC masters retain 720×576 or 720×480 dimensions and carry
4:3 display metadata. Current physical validation is deliberately narrow: MS210x, PAL, Ubuntu
24.04, amd64. The service has no authentication and defaults to loopback.

OpenAI Codex assisted extensively with the code, tests, audit, and documentation; OpenAI does not
endorse the project. I would appreciate critique of the failure model, install path, and ways to
collect compatibility evidence without encouraging people to post private recordings.

https://github.com/paulcakeface/vhscribe
