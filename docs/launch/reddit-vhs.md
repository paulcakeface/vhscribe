# Reddit draft — VHS and digitisation communities

## Title

VHScribe: open-source headless capture control with native PAL/NTSC dimensions

## Post

I have been working on VHScribe, a local web interface for controlling a USB capture card attached
to a headless Linux server. The goal is operational reliability rather than automatic restoration:
see the live signal, enter a tape name, start/stop deliberately, and retain partial MKV files after
an interruption.

PAL masters remain 720×576/25 and NTSC masters remain 720×480/30000:1001. VHScribe signals a 4:3
display aspect ratio without scaling the encoded master. The default H.264/AAC profile is a
practical lossy capture format, not a claim of archival losslessness; deinterlacing, correction,
and restoration are left for a later copy.

Confirmed hardware testing currently covers one MacroSilicon MS210x PAL setup on Ubuntu Server
24.04/amd64. I am looking for careful, privacy-safe reports from other V4L2/ALSA adapters and real
NTSC systems. Please do not share family footage just to report a bug—the project includes a
synthetic test source.

Development involved extensive OpenAI Codex assistance, without OpenAI endorsement.

Repository: https://github.com/paulcakeface/vhscribe
