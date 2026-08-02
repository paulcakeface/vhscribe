# Reddit draft — self-hosted communities

## Title

VHScribe: a local-first browser control panel for headless VHS capture

## Post

I built VHScribe to run a USB VHS capture adapter on a headless Linux server without keeping a
desktop session beside the tape deck. It provides a private web dashboard for low-latency preview,
named recording, disk status, and non-destructive recovery of interrupted MKV files.

The stack is intentionally small: FastAPI supervises one FFmpeg process, MediaMTX carries the
WebRTC preview, and Docker Compose maps the selected V4L2 and ALSA devices. Public defaults bind to
loopback, containers are not privileged, and synthetic input covers CI and evaluation without
capture hardware.

The reference hardware is a MacroSilicon MS210x with PAL input on Ubuntu Server 24.04/amd64. NTSC
and arm64 builds are tested synthetically, not yet on maintainers' physical hardware. There is no
authentication in v0.1.0, so this belongs on a trusted host/LAN—not the public internet.

The project was developed with extensive OpenAI Codex assistance for implementation, testing,
security review, and documentation; it is not endorsed by OpenAI. I would particularly value
feedback on install clarity, other capture-card results, and safe preservation workflows.

Repository: https://github.com/paulcakeface/vhscribe
