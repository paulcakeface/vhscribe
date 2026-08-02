# Architecture

VHScribe keeps capture ownership deliberately narrow: the FastAPI application supervises exactly
one FFmpeg process. MediaMTX is a transport component and never opens the hardware itself.

```mermaid
flowchart TB
    subgraph Host[Linux capture host]
        USB[USB capture adapter]
        Disk[(Configured capture directory)]
        subgraph Compose[Docker Compose]
            App[FastAPI application<br/>process/state manager]
            FF[One FFmpeg process]
            MTX[MediaMTX]
        end
    end
    Browser[Trusted browser]
    USB -->|mapped V4L2 + ALSA devices| FF
    App -->|argument-array subprocess| FF
    FF -->|H.264/AAC Matroska| Disk
    FF -->|H.264/Opus RTSP| MTX
    MTX -->|WebRTC| Browser
    Browser -->|HTTP/JSON| App
```

Without Mermaid: the browser calls FastAPI; FastAPI owns FFmpeg; FFmpeg reads the USB adapter,
writes the MKV, and sends a separate low-bitrate preview to MediaMTX; MediaMTX sends WebRTC to the
browser.

## Process state

```mermaid
stateDiagram-v2
    [*] --> Initialising
    Initialising --> PreviewAvailable: preview publisher ready
    PreviewAvailable --> StartingRecording: start accepted
    StartingRecording --> Recording: FFmpeg stable
    Recording --> Stopping: stop accepted
    Stopping --> Initialising: validated and renamed
    Initialising --> Error: process/device failure
    Recording --> Error: unexpected exit; partial retained
    Error --> Initialising: supervised preview restart
```

State changes are serialized by one manager lock. Starting a recording first stops the preview
process and then starts one combined recording/preview process. This prevents two readers opening
the same V4L2 or ALSA endpoint.

## File lifecycle

1. A sanitized recording name and timestamp create a unique `*.part.mkv` path.
2. FFmpeg writes Matroska clusters frequently so an interrupted file has a better chance of being
   recoverable.
3. A normal stop sends `SIGINT`, waits for FFmpeg to close the container, and then runs `ffprobe`.
4. Only a non-empty file containing video and audio is atomically renamed to `*.mkv`.
5. A failed validation leaves the partial file unchanged.
6. Manual recovery stream-copies a partial into a separate MKV and preserves the source.

## Video paths

The recording filter splits the decoded input once. The master branch applies only sample-aspect
metadata: PAL uses 16:15 and NTSC uses 8:9, both yielding 4:3 display. The preview branch scales to
the configured preview resolution. The master never inherits that preview scaling.

## Trust boundaries

- The capture directory and devices are explicit host mounts.
- The application container has a read-only root filesystem; only capture, log, state, and temporary
  mounts are writable.
- MediaMTX accepts an RTSP publisher only on the internal Compose network; public host mappings are
  limited to its WebRTC player/signaling and media ports.
- There is no end-user authentication in 0.1.x. Host binds and firewall policy are the access
  control boundary.

## Design invariants

- Never use `privileged: true`.
- Never build FFmpeg commands through a shell.
- Never run two hardware capture processes.
- Never delete or silently replace partial recordings.
- Never call a file complete before media validation.
