from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _run(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout if result.returncode == 0 else ""


def discover_devices(video_standard: str) -> dict[str, Any]:
    """Return read-only device suggestions; never alter host or application config."""
    video: list[dict[str, Any]] = []
    for path in sorted(Path("/dev").glob("video*")):
        item: dict[str, Any] = {"device": str(path), "label": path.name, "formats": []}
        if shutil.which("v4l2-ctl"):
            description = _run(["v4l2-ctl", "--device", str(path), "--info"])
            card = re.search(r"Card type\s*:\s*(.+)", description)
            if card:
                item["label"] = card.group(1).strip()
            formats = _run(["v4l2-ctl", "--device", str(path), "--list-formats-ext"])
            item["formats"] = [
                line.strip() for line in formats.splitlines() if "Size: Discrete" in line
            ][:12]
        video.append(item)

    audio: list[dict[str, str]] = []
    if shutil.which("arecord"):
        listing = _run(["arecord", "-l"])
        pattern = re.compile(r"^card\s+(\d+):\s*([^\[]+).*device\s+(\d+):\s*([^\[]+)", re.I)
        for line in listing.splitlines():
            match = pattern.search(line)
            if not match:
                continue
            card_number, card_label, device_number, device_label = match.groups()
            audio.append(
                {
                    "device": f"hw:{card_number},{device_number}",
                    "label": f"{card_label.strip()} / {device_label.strip()}",
                }
            )

    expected_size = "720x576" if video_standard == "PAL" else "720x480"
    return {
        "read_only": True,
        "video_standard": video_standard,
        "expected_capture_size": expected_size,
        "video": video,
        "audio": audio,
        "tools": {
            "v4l2_ctl": shutil.which("v4l2-ctl") is not None,
            "arecord": shutil.which("arecord") is not None,
        },
    }
