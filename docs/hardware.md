# Hardware discovery and configuration

USB video-capture products are frequently sold under reused names and with changing chipsets. Use
the interfaces Linux actually exposes rather than relying only on the name printed on the adapter.

## Automated read-only report

Install `v4l-utils` and `alsa-utils` on the host, then run:

```bash
./scripts/discover-hardware.sh
```

The script lists V4L2 endpoints, USB labels, formats, resolutions, frame intervals, ALSA capture
sources, device permissions, and suggested Compose values. It does not edit `.env`, group
membership, udev rules, Docker, or any device.

The dashboard's **Detected capture hardware** section performs a smaller read-only scan from inside
the application container. It is advisory: VHScribe continues using the explicit `.env` values
until an operator edits them and restarts Compose.

## Video checks

```bash
v4l2-ctl --list-devices
v4l2-ctl --device /dev/video0 --all
v4l2-ctl --device /dev/video0 --list-formats-ext
```

For the provided profiles, look for 720×576 at 25 fps (PAL) or 720×480 around 29.97 fps (NTSC).
Some cards expose several `/dev/video*` nodes but only one carries the actual capture stream.

## Audio checks

```bash
arecord -l
arecord -L
arecord -D hw:CARD=Device,DEV=0 -f S16_LE -r 48000 -c 2 -d 5 /tmp/vhscribe-audio.wav
```

Replace the example card name. Listen to the purpose-made test file, then remove it. A stable ALSA
card name is preferable to `hw:0,0`, because numeric card order can change after reboot.

Video and audio endpoints from the same adapter commonly share a USB manufacturer/model label or
physical bus path. Treat that as a pairing hint, not proof; verify with a safe test signal.

## Permissions

Inspect the device owners and your effective groups:

```bash
ls -l /dev/video* /dev/snd
id
```

On many Ubuntu hosts the relevant groups are `video` and `audio`:

```bash
sudo usermod -aG video,audio "$USER"
```

Log out and back in. Avoid broad `chmod 666` rules. If stable permissions require a udev rule,
scope it to the adapter vendor/product IDs and review it as a host-specific administrative change;
VHScribe never installs one automatically.

Also copy the host IDs reported by `id -u`, `id -g`, and `getent group video audio` into `PUID`,
`PGID`, `VIDEO_GROUP_ID`, and `AUDIO_GROUP_ID`. This lets the unprivileged application process write
files owned by the operator and access only the mapped device groups.

## Docker mappings

The Compose file maps one configured V4L2 endpoint and the ALSA device directory:

```yaml
devices:
  - "/dev/video0:/dev/video0"
  - /dev/snd:/dev/snd
```

This is intentionally narrower than privileged mode. If your selected video endpoint differs,
change `VIDEO_DEVICE` in `.env`; Compose uses that path for both sides of the mapping.

## Compatibility reporting

The maintainers have confirmed a MacroSilicon MS210x on Ubuntu Server 24.04 with PAL input. For any
other combination, use the hardware compatibility issue template and distinguish:

- the product label from USB and driver identity;
- advertised formats from a successful recording;
- synthetic NTSC tests from physical NTSC validation;
- container architecture from capture-device compatibility.

Redact serial numbers, LAN addresses, paths, and recording titles before posting diagnostics.
