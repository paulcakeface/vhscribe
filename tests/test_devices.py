from __future__ import annotations

from pathlib import Path

from app import devices


def test_device_discovery_is_read_only(monkeypatch) -> None:
    monkeypatch.setattr(Path, "glob", lambda _self, _pattern: [])
    monkeypatch.setattr(devices.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(
        devices,
        "_run",
        lambda command: (
            "card 2: Capture [USB Capture], device 0: USB Audio [USB Audio]\n"
            if command[:2] == ["arecord", "-l"]
            else ""
        ),
    )

    result = devices.discover_devices("PAL")

    assert result["read_only"] is True
    assert result["expected_capture_size"] == "720x576"
    assert result["video"] == []
    assert result["audio"] == [{"device": "hw:2,0", "label": "Capture / USB Audio"}]
