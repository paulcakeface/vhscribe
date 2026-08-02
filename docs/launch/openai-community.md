# OpenAI developer community announcement draft

## VHScribe: using Codex to help build a safer headless VHS capture workflow

VHScribe is an open-source, local-first control panel for digitising VHS through a USB capture card
attached to a headless Linux server. A browser can view a WebRTC preview, start and stop a named
recording, monitor disk/status information, and recover interrupted MKV files without deleting the
source partial.

Codex assistance was used extensively across the project: reading and preserving an existing live
capture workflow, implementing the FastAPI/FFmpeg state manager, writing synthetic and unit tests,
checking aspect-ratio metadata, reviewing container hardening, auditing the repository for private
deployment details, and producing installation and contributor documentation. Human acceptance
checks remained essential for physical video/audio quality, browser behavior, and deciding which
local infrastructure details must stay private.

The public candidate is intentionally honest about its boundary: current physical validation is
one MS210x/PAL setup on Ubuntu Server 24.04/amd64; NTSC and arm64 are synthetic/build validations;
there is no public adoption data yet; and v0.1.0 has no built-in authentication. The project is not
endorsed by OpenAI.

Repository: https://github.com/paulcakeface/vhscribe
