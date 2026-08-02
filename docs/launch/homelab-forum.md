# Homelab/forum announcement

VHScribe turns a headless Linux machine and a V4L2/ALSA USB capture adapter into a private VHS
capture station. A lightweight browser dashboard controls one supervised FFmpeg process while
MediaMTX provides the WebRTC preview. Recordings go directly to a configured host directory and
interrupted `.part.mkv` files are retained for explicit recovery.

Deployment is Docker Compose, with loopback-only defaults, explicit device mappings, dropped
capabilities, read-only container roots, health checks, and no privileged mode. The repository also
includes read-only hardware discovery, a verification script, synthetic CI, amd64/arm64 container
build checks, and operational documentation.

This is the initial v0.1.0 release. It has no authentication or TLS and should stay on a trusted
host or LAN. Maintainer hardware testing is currently an EasierCAP-branded MS210x adapter with PAL
input on Ubuntu Server 24.04/amd64; broader compatibility is not yet claimed.

The project was developed with extensive OpenAI Codex assistance, but is independent and not
endorsed by OpenAI. Feedback on the Compose experience and capture-device compatibility would be
welcome: https://github.com/paulcakeface/vhscribe
