#!/usr/bin/env bash
set -Eeuo pipefail

printf 'VHScribe hardware discovery (read-only)\n\n'

for tool in v4l2-ctl arecord udevadm; do
  if command -v "${tool}" >/dev/null 2>&1; then
    printf '[ok] %s: %s\n' "${tool}" "$(command -v "${tool}")"
  else
    printf '[missing] %s\n' "${tool}"
  fi
done

printf '\nCurrent user: %s\n' "$(id -un)"
printf 'Groups: %s\n' "$(id -Gn)"

video_found=false
printf '\nVideo capture devices\n'
for video_device in /dev/video*; do
  [[ -e "${video_device}" ]] || continue
  video_found=true
  printf '\n%s (%s)\n' "${video_device}" "$(stat -c '%A %U:%G' "${video_device}")"
  if [[ ! -r "${video_device}" || ! -w "${video_device}" ]]; then
    printf '  WARNING: current user does not have read/write access. Check video-group membership.\n'
  fi
  if command -v udevadm >/dev/null 2>&1; then
    udevadm info --query=property --name="${video_device}" 2>/dev/null \
      | sed -n -E 's/^(ID_VENDOR|ID_MODEL|ID_BUS)=/  \1: /p'
  fi
  if command -v v4l2-ctl >/dev/null 2>&1; then
    v4l2-ctl --device "${video_device}" --all 2>/dev/null \
      | sed -n -E 's/^[[:space:]]*(Card type|Bus info|Video input|Video Standard)[[:space:]]*:/  \1:/p'
    printf '  Supported formats and frame rates:\n'
    v4l2-ctl --device "${video_device}" --list-formats-ext 2>/dev/null \
      | sed -n -E "/^\[|Size: Discrete|Interval: Discrete/p" \
      | sed 's/^/    /'
  fi
done
if [[ "${video_found}" == false ]]; then
  printf '  No /dev/video* devices found.\n'
fi

printf '\nALSA capture devices\n'
audio_device=''
sound_found=false
for sound_device in /dev/snd/*c; do
  [[ -e "${sound_device}" ]] || continue
  sound_found=true
  printf '  %s (%s)\n' "${sound_device}" "$(stat -c '%A %U:%G' "${sound_device}")"
  if [[ ! -r "${sound_device}" || ! -w "${sound_device}" ]]; then
    printf '    WARNING: current user does not have read/write access. Check audio-group membership.\n'
  fi
done
if [[ "${sound_found}" == false ]]; then
  printf '  No /dev/snd capture endpoints found.\n'
fi
if command -v arecord >/dev/null 2>&1; then
  arecord_output="$(arecord -l 2>/dev/null || true)"
  if [[ -n "${arecord_output}" ]]; then
    printf '%s\n' "${arecord_output}"
    while IFS= read -r audio_line; do
      if [[ "${audio_line}" =~ card[[:space:]]+([0-9]+):[[:space:]]+([^[:space:]]+).*device[[:space:]]+([0-9]+): ]]; then
        audio_device="hw:CARD=${BASH_REMATCH[2]},DEV=${BASH_REMATCH[3]}"
        break
      fi
    done <<< "${arecord_output}"
  else
    printf '  No ALSA capture devices found.\n'
  fi
else
  printf '  Install alsa-utils to enumerate capture devices.\n'
fi

printf '\nLikely configuration\n'
first_video=''
for video_device in /dev/video*; do
  [[ -e "${video_device}" ]] || continue
  first_video="${video_device}"
  break
done
printf '  VIDEO_DEVICE=%s\n' "${first_video:-/dev/video0}"
printf '  AUDIO_DEVICE=%s\n' "${audio_device:-hw:CARD=Device,DEV=0}"
printf '  VIDEO_STANDARD=PAL   # 720x576 at 25 fps\n'
printf '  # or VIDEO_STANDARD=NTSC  # 720x480 at 30000/1001 fps\n'
printf '  PUID=%s\n' "$(id -u)"
printf '  PGID=%s\n' "$(id -g)"
if command -v getent >/dev/null 2>&1; then
  video_group_id="$(getent group video 2>/dev/null | cut -d: -f3 || true)"
  audio_group_id="$(getent group audio 2>/dev/null | cut -d: -f3 || true)"
  printf '  VIDEO_GROUP_ID=%s\n' "${video_group_id:-44}"
  printf '  AUDIO_GROUP_ID=%s\n' "${audio_group_id:-29}"
fi
printf '\nCompose device mappings\n'
printf '  %s:%s\n' "${first_video:-/dev/video0}" "${first_video:-/dev/video0}"
printf '  /dev/snd:/dev/snd\n'
printf '\nDevices sharing a USB vendor/model label are the strongest video/audio pairing candidates.\n'
printf 'Confirm the preview before recording; this script never changes .env or device state.\n'
