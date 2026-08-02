# Ready to post — VHS and media-preservation communities

## Title

VHScribe: open-source headless capture control with safe interrupted-recording recovery

## Post

Digitising VHS is a real-time process, and losing a long capture near the end is painful. I built
VHScribe as an open-source local web interface for a USB capture card attached to a headless Linux
server. The goal is operational reliability rather than automatic restoration: see the live signal,
start a named server-side recording that does not depend on keeping the browser open, stop
deliberately, and retain partial MKV files after an interruption.

PAL masters remain 720×576/25 and NTSC masters remain 720×480/30000:1001. VHScribe signals a 4:3
display aspect ratio without scaling the encoded master. The default H.264/AAC profile is a
practical lossy capture format, not a claim of archival losslessness; deinterlacing, correction,
and restoration are left for a later copy.

Confirmed hardware testing currently covers an EasierCAP-branded adapter identified as
MacroSilicon MS210x, with PAL input on Ubuntu Server 24.04/amd64. I am looking for careful,
privacy-safe reports from other V4L2/ALSA adapters, physical NTSC systems, and ARM64 capture hosts.
Please do not share family footage just to report a bug—the project includes a synthetic test
source.

Development involved extensive OpenAI Codex assistance; this independent project is not endorsed
by OpenAI.

Repository: https://github.com/paulcakeface/vhscribe
