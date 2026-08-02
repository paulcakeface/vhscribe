#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"

if ! command -v docker >/dev/null 2>&1; then
  printf 'error: Docker is not installed or not in PATH\n' >&2
  exit 1
fi

printf '[1/6] Validating Compose configuration\n'
docker compose config --quiet

printf '[2/6] Checking required services\n'
running_services="$(docker compose ps --services --filter status=running)"
grep -qx app <<< "${running_services}"
grep -qx mediamtx <<< "${running_services}"

printf '[3/6] Checking the API and capture profile\n'
docker compose exec -T app python -c \
  "import json, urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8090/api/config', timeout=5)); assert data['master_display_aspect_ratio']=='4:3'; print(json.dumps(data, sort_keys=True))"

printf '[4/6] Checking service health\n'
docker compose exec -T app python -c \
  "import json, urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8090/api/health', timeout=5)); assert data['healthy'] is True, data; print(json.dumps(data, sort_keys=True))"

printf '[5/6] Checking read-only hardware discovery endpoint\n'
docker compose exec -T app python -c \
  "import json, urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8090/api/devices', timeout=5)); assert data['read_only'] is True; print('video=%d audio=%d' % (len(data['video']), len(data['audio'])))"

printf '[6/6] Checking media tools\n'
docker compose exec -T app ffmpeg -version | head -n 1
docker compose exec -T app ffprobe -version | head -n 1

printf '\nVHScribe installation checks passed. Start a short named recording from the UI to validate your physical signal path.\n'
