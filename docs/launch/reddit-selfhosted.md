# Ready to post — r/selfhosted

## Title

VHScribe: open-source, browser-controlled VHS capture for a headless Linux server

## Post

Digitising a VHS tape takes as long as playing it, so a browser disconnect or an interrupted process
should not throw away hours of work. I built the open-source VHScribe to run a USB capture adapter
on a headless Linux server without keeping a desktop session beside the tape deck. Its private web
dashboard provides low-latency preview, named recording, disk status, and non-destructive recovery
of interrupted MKV files. Once started, recording runs on the server independently of the browser.

The stack is intentionally small: FastAPI supervises one FFmpeg process, MediaMTX carries the
WebRTC preview, and Docker Compose maps the selected V4L2 and ALSA devices. Public defaults bind to
loopback, containers are not privileged, and synthetic input covers CI and evaluation without
capture hardware.

The real-hardware reference is an EasierCAP-branded adapter identified as MacroSilicon MS210x, with
PAL input on Ubuntu Server 24.04/amd64. NTSC and ARM64 builds are tested synthetically, not yet on
maintainers' physical hardware. There is no authentication in v0.1.0, so this belongs on a trusted
host/LAN—not the public internet.

Development used extensive OpenAI Codex assistance for implementation, testing, security review,
and documentation; it is not endorsed by OpenAI. Testing and privacy-safe reports from additional
capture devices, physical NTSC setups, and ARM64 hosts would be especially welcome.

Repository: https://github.com/paulcakeface/vhscribe
