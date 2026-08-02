from __future__ import annotations

import pytest

from app.config import Settings


def test_pal_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEO_STANDARD", "pal")
    settings = Settings.from_env()
    assert settings.video_standard == "PAL"
    assert settings.video_size == "720x576"
    assert settings.video_fps == "25"
    assert settings.master_sar == "16/15"


def test_ntsc_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEO_STANDARD", "NTSC")
    settings = Settings.from_env()
    assert settings.video_size == "720x480"
    assert settings.video_fps == "30000/1001"
    assert settings.master_sar == "8/9"


def test_invalid_video_standard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEO_STANDARD", "SECAM")
    with pytest.raises(ValueError, match="PAL or NTSC"):
        Settings.from_env()


def test_invalid_preview_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PREVIEW_RESOLUTION", "full-hd")
    with pytest.raises(ValueError, match="WIDTHxHEIGHT"):
        Settings.from_env()
