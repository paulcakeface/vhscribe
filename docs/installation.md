# Installation and operations

The [README quick start](../README.md#quick-start) is the shortest path. This page collects the
operational details for a headless host.

## Install

1. Install Docker Engine, Docker Compose v2, Git, `v4l-utils`, and `alsa-utils` from trusted package
   sources for your distribution.
2. Clone the repository and run `./scripts/discover-hardware.sh`.
3. Copy `.env.example` to `.env`, set mode `0600`, and edit the storage, device, standard, bind, and
   timezone values.
4. Create the capture directory and ensure the operator can write it.
5. Start with `docker compose up -d --build` and run `./scripts/verify-installation.sh`.
6. Confirm the dashboard initially reports **Idle**, start and stop preview, then perform a short,
   non-sensitive test recording and inspect both the media and its `.mkv.qc.json` sidecar before
   beginning a long capture.

By default, successful captures calculate SHA-256 fixity (`QC_CHECKSUM=true`). Full-file decode verification is available with `QC_FULL_DECODE=true`, but it adds substantial finalisation time and is disabled by default.

## Routine commands

```bash
docker compose ps
docker compose logs -f --tail=100 app mediamtx
docker compose up -d
docker compose stop -t 45
docker compose down -t 45
```

Always stop an active recording through the API/dashboard first.

## Upgrade

Back up `.env` and the capture directory, read `CHANGELOG.md`, then:

```bash
git pull --ff-only
docker compose build --pull
docker compose up -d
./scripts/verify-installation.sh
```

For GHCR images, set `APP_IMAGE` to an approved immutable version tag and run `docker compose pull`
before `up -d`. Avoid floating tags when rollback certainty matters.

## Backup and restore

The capture directory is the essential data. `.env` is the private deployment configuration. Logs
and state can be recreated. Stop active recording before a filesystem-level backup unless the
storage technology provides a consistent snapshot. Restore media to the configured directory and
recreate `.env`; VHScribe discovers completed and partial files on startup.

## Uninstall without deleting recordings

```bash
docker compose down --remove-orphans
docker image rm vhscribe:local  # optional
```

The bind-mounted capture directory remains. Verify its path before manually removing the repository
checkout. Never use an unreviewed recursive deletion command, and do not add `--volumes` unless you
understand every Compose volume in the resolved model.
