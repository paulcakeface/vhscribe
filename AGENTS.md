# VHScribe development guide

## Safety constraints

- Keep every application, Compose, documentation, and test file inside this repository.
- Treat all existing files outside this repository as read-only unless a separately documented change is required.
- Never delete, overwrite, rename, or edit recordings in the configured capture directory.
- Only one FFmpeg process may open the physical capture devices at once.
- Never build FFmpeg commands with a shell. Pass argument arrays to `subprocess`.
- Do not use Docker privileged mode. Map the discovered video and ALSA devices explicitly.
- Active recordings use `.part.mkv`. Only rename after a graceful stop and a successful `ffprobe` validation.
- Never delete interrupted `.part.mkv` files automatically.
- Keep the service private. It binds to loopback by default; do not add a public reverse proxy.

## Architecture

- `app`: Python/FastAPI control service; owns the single FFmpeg process and serves the HTML UI/API.
- `mediamtx`: receives the low-latency preview and exposes its browser player through WebRTC.
- Capture devices: configurable V4L2 video and ALSA audio devices (container device `/dev/snd`).
- Recordings: the configured host directory, mounted as `/captures` in the app.
- Persistent operational data: repository `logs/` and `state/` directories.

## Important commands

```bash
cd vhscribe
docker compose config
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f app mediamtx
docker compose stop -t 45
docker compose down -t 45
docker compose run --rm --no-deps app pytest -q
curl -fsS http://127.0.0.1:8090/api/health
curl -fsS http://127.0.0.1:8090/api/status
```

Use `POST /api/recordings/stop` before stopping Compose whenever a recording is active.

## Development conventions

- Python code lives in `app/`; templates and static files remain framework-free.
- Hardware and FFmpeg values are environment-configurable, with discovered values as defaults.
- Keep process/state transitions serialized by the manager lock.
- Add or update tests for process/state changes, filename handling, recovery, and metadata parsing.
- Run `pytest`, Compose config validation, image build, health checks, and a real capture smoke test before handoff.
