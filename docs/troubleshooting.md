# Troubleshooting

Start with these non-destructive checks:

```bash
docker compose config --quiet
docker compose ps
./scripts/verify-installation.sh
./scripts/discover-hardware.sh
docker compose logs --tail=100 app mediamtx
```

Review logs before sharing them; even though VHScribe avoids logging full recording paths, device
drivers and local configuration can reveal host details.

## The app container does not start

- Confirm `.env` exists and the capture directory exists and is writable.
- Confirm `VIDEO_DEVICE` exists before Compose tries to map it.
- Run `docker compose config` to see the resolved, non-secret Compose model.
- Check that the configured host ports are not already in use.

Use `compose.synthetic.yaml` to separate an application problem from a hardware-mapping problem.

## Preview is initialising or unavailable

- Confirm `docker compose ps` reports both services healthy.
- Check the application log for an FFmpeg input error and MediaMTX logs for a `vhs` publisher.
- Confirm PAL/NTSC matches the active tape deck signal.
- On a LAN client, verify both the configured WebRTC TCP port and UDP port are allowed by the host
  firewall. HTTP access alone is not enough for the media path.
- A browser with strict WebRTC/network policy may fail even when the dashboard loads; test a clean,
  current browser profile.

## Device busy

Only VHScribe should open the adapter. Stop VLC capture, test FFmpeg commands, and other recording
software before starting the stack:

```bash
sudo fuser -v /dev/video0 /dev/snd/* 2>/dev/null
```

Do not kill an unknown process until you understand what it is doing. If VHScribe is recording, use
the dashboard stop action first.

## Video is black, unstable, or the wrong shape

- Check the physical input and whether the tape deck outputs PAL or NTSC.
- Verify that the selected V4L2 node supports the profile's resolution and rate.
- The encoded PAL master should remain 720×576 and report 4:3 display; NTSC should remain 720×480
  and report 4:3. See [aspect-ratio verification](aspect-ratio-verification.md).
- Analog time-base instability is a source-signal issue. A hardware or line time-base corrector may
  help, but no specific external device is claimed as tested by this project.

## Audio is absent, distorted, or from the wrong source

- Run a five-second `arecord` test using the exact configured ALSA name.
- Confirm stereo/48 kHz is accepted and the correct USB card is selected.
- Prefer a named card identifier over a numeric index that can move after reboot.
- Check cabling and the capture card's input selection before changing encoder settings.

## Recording stops but remains partial

VHScribe retains partials when FFmpeg exits abnormally or validation fails. Do not edit the source.
Use the dashboard **Recover** action, which stream-copies to a separate output and preserves the
partial. If recovery fails, copy the file before experimenting with standalone FFmpeg tools.

## The dashboard is reachable from an unintended network

Stop the stack, set `SERVER_ADDRESS=127.0.0.1` or one exact private interface address, then recreate:

```bash
docker compose up -d --force-recreate
```

Review firewall and router port-forwarding separately. VHScribe does not configure either.
