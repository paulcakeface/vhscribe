# Development

VHScribe intentionally uses a small FastAPI service and framework-free HTML/CSS/JavaScript. Keep
changes focused and preserve the single-process capture model.

## Local Python setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
ruff format --check .
ruff check .
pytest -q
```

Unit tests do not require devices, Docker, or private configuration.

## Synthetic integration stack

The override removes host device mappings and replaces them with FFmpeg's `testsrc2` video and sine
audio. Use public-safe loopback settings rather than a private deployment `.env`:

```bash
cp .env.example .env.synthetic
docker compose --env-file .env.synthetic \
  -f compose.yaml -f compose.synthetic.yaml up -d --build
./scripts/verify-installation.sh
```

Exercise preview on demand, then start a short recording from dormant mode and inspect the generated
file under the ignored `test-artifacts/captures/` directory:

```bash
curl -fsS -X POST http://127.0.0.1:8090/api/preview/start
curl -fsS -X POST http://127.0.0.1:8090/api/preview/heartbeat
curl -fsS -X POST http://127.0.0.1:8090/api/preview/stop
curl -fsS -X POST -H 'Content-Type: application/json' \
  -d '{"name":"Synthetic test"}' http://127.0.0.1:8090/api/recordings/start
sleep 8
curl -fsS -X POST http://127.0.0.1:8090/api/recordings/stop
ffprobe -v error -show_entries \
  stream=codec_type,codec_name,width,height,sample_aspect_ratio,display_aspect_ratio \
  -of json test-artifacts/captures/*.mkv
```

Then stop the synthetic stack:

```bash
docker compose --env-file .env.synthetic \
  -f compose.yaml -f compose.synthetic.yaml down -t 45
```

`.env.synthetic` and all generated media remain ignored. Never point synthetic cleanup commands at
a real capture directory.

## Validation matrix

- `ruff format --check .` — formatting
- `ruff check .` — Python lint and common bug patterns
- `pytest -q` — preview lifecycle, concurrency, state, filename, profile, command, and metadata behavior
- `docker compose config --quiet` — resolved configuration
- `docker build .` — production image
- `pip-audit -r requirements.txt` — published Python dependency advisories
- `gitleaks git . --redact` — secret patterns in Git history
- ShellCheck — shell scripts
- Lychee — documentation links
- Synthetic preview lifecycle plus API recording and `ffprobe` — complete media path

CI runs without private hardware. Physical tests are maintainer-controlled because workflows must
never depend on USB devices or private recordings.

## Changing the capture command

FFmpeg commands must remain argument arrays. Add a unit test that proves the master resolution,
rate, aspect metadata, codecs, and preview branch. A real capture test is required before claiming
physical support. Never modify existing recordings to validate a command change.

## Release process

Update `CHANGELOG.md` and release notes, run the full validation matrix, and review the image/context
for private material. The release workflow is manual and defaults to a dry run. Publishing requires
an explicit `publish=true` dispatch after maintainer approval. Tags and GitHub releases are created
separately and are never automatic.
