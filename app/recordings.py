from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

ALLOWED_MEDIA_SUFFIXES = {".mkv", ".mp4", ".mov", ".avi"}


def sanitize_recording_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = re.sub(r"[^\w -]", "", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip(" ._-")
    value = value[:80].rstrip(" ._-")
    return value or "recording"


def unique_partial_path(directory: Path, name: str, now: datetime | None = None) -> Path:
    timestamp = (now or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
    base = f"{sanitize_recording_name(name)}_{timestamp}"
    candidate = directory / f"{base}.part.mkv"
    number = 2
    while (
        candidate.exists()
        or candidate.with_name(candidate.name.replace(".part.mkv", ".mkv")).exists()
    ):
        candidate = directory / f"{base}-{number}.part.mkv"
        number += 1
    return candidate


def final_path_for(partial: Path) -> Path:
    if not partial.name.endswith(".part.mkv"):
        raise ValueError("not a partial MKV filename")
    return partial.with_name(partial.name[: -len(".part.mkv")] + ".mkv")


def safe_capture_file(directory: Path, filename: str) -> Path:
    if not filename or Path(filename).name != filename or filename in {".", ".."}:
        raise ValueError("invalid filename")
    path = directory / filename
    resolved_parent = path.resolve(strict=False).parent
    if resolved_parent != directory.resolve():
        raise ValueError("invalid filename")
    return path


def probe_media(ffprobe_bin: str, path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,"
            "r_frame_rate,sample_aspect_ratio,display_aspect_ratio,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("ffprobe could not validate this media file")
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if not any(item.get("codec_type") == "video" for item in streams):
        raise ValueError("media file has no video stream")
    return data


class RecordingCatalog:
    def __init__(
        self,
        directory: Path,
        ffprobe_bin: str = "ffprobe",
        ffmpeg_bin: str = "ffmpeg",
    ) -> None:
        self.directory = directory
        self.ffprobe_bin = ffprobe_bin
        self.ffmpeg_bin = ffmpeg_bin
        self._cache: dict[str, tuple[int, int, dict[str, Any]]] = {}
        self._lock = Lock()

    def interrupted(self) -> list[Path]:
        return sorted(
            self.directory.glob("*.part.mkv"), key=lambda p: p.stat().st_mtime, reverse=True
        )

    def _metadata(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        cached = self._cache.get(path.name)
        if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
            return cached[2]
        metadata: dict[str, Any] = {}
        try:
            probe = probe_media(self.ffprobe_bin, path)
            fmt = probe.get("format", {})
            metadata["duration_seconds"] = float(fmt.get("duration", 0) or 0)
            metadata["streams"] = [stream.get("codec_type") for stream in probe.get("streams", [])]
        except (ValueError, subprocess.SubprocessError, json.JSONDecodeError):
            metadata["duration_seconds"] = None
            metadata["streams"] = []
        self._cache[path.name] = (stat.st_mtime_ns, stat.st_size, metadata)
        return metadata

    def list(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        with self._lock:
            for path in self.directory.iterdir():
                if not path.is_file():
                    continue
                interrupted = path.name.endswith(".part.mkv")
                if not interrupted and path.suffix.lower() not in ALLOWED_MEDIA_SUFFIXES:
                    continue
                stat = path.stat()
                metadata = self._metadata(path)
                items.append(
                    {
                        "filename": path.name,
                        "date": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                        "size_bytes": stat.st_size,
                        "duration_seconds": metadata.get("duration_seconds"),
                        "streams": metadata.get("streams", []),
                        "interrupted": interrupted,
                        "recoverable": interrupted and stat.st_size > 0,
                    }
                )
        return sorted(items, key=lambda item: item["date"], reverse=True)

    def disk(self) -> dict[str, int]:
        usage = shutil.disk_usage(self.directory)
        return {"total_bytes": usage.total, "used_bytes": usage.used, "free_bytes": usage.free}

    def recover(self, filename: str, active_filename: str | None = None) -> Path:
        source = safe_capture_file(self.directory, filename)
        if not source.name.endswith(".part.mkv") or not source.is_file():
            raise ValueError("recoverable partial MKV not found")
        if source.name == active_filename:
            raise ValueError("cannot recover an active recording")
        destination = final_path_for(source)
        if destination.exists():
            raise FileExistsError("the recovered destination already exists")
        working = destination.with_name(destination.stem + ".recovering.mkv")
        if working.exists():
            raise FileExistsError("a recovery is already in progress")
        result = subprocess.run(
            [
                self.ffmpeg_bin,
                "-hide_banner",
                "-nostdin",
                "-loglevel",
                "warning",
                "-i",
                str(source),
                "-map",
                "0",
                "-c",
                "copy",
                "-f",
                "matroska",
                str(working),
            ],
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("FFmpeg could not remux the interrupted recording")
        probe_media(self.ffprobe_bin, working)
        os.rename(working, destination)
        return destination
