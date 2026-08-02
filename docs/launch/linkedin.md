# Ready to post — LinkedIn

Old tapes present a surprisingly modern systems problem: the source is fragile and real-time, USB
capture hardware varies, and a failed long recording can waste hours. I built the open-source
VHScribe to make that workflow easier to operate from a headless Linux server.

VHScribe provides a local browser dashboard for preview, named recording, disk visibility, and
recovery of interrupted Matroska files. Recording runs on the server and continues if the browser
disconnects. Its architecture deliberately gives one FastAPI-supervised FFmpeg process exclusive
ownership of V4L2 video and ALSA audio, while MediaMTX supplies a WebRTC preview. PAL and NTSC
profiles retain their native encoded dimensions and explicitly signal 4:3 display.

The initial public release includes private-by-default Docker Compose configuration, read-only
hardware discovery, synthetic automated tests, multi-architecture container builds, security
guidance, and practical installation documentation. Current physical testing covers an
EasierCAP-branded adapter identified as MacroSilicon MS210x, with PAL input on Ubuntu Server
24.04/amd64; wider compatibility remains to be demonstrated by evidence, not assumed from product
labels. Testing on additional capture devices, physical NTSC setups, and ARM64 hosts is welcome.

OpenAI Codex contributed extensively throughout development—helping implement and review code,
expand tests, investigate edge cases, audit the release surface, and shape documentation. This is
an independent open-source project and is not sponsored or endorsed by OpenAI.

Repository: https://github.com/paulcakeface/vhscribe
