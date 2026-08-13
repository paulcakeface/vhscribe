from __future__ import annotations

from datetime import datetime

import pytest

from app.recordings import (
    RecordingCatalog,
    safe_capture_file,
    sanitize_recording_name,
    unique_partial_path,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Family Holiday 1994", "Family Holiday 1994"),
        ("Tape_01-final", "Tape_01-final"),
        ("../../etc/passwd", "etcpasswd"),
        ("name; $(touch hacked) | test", "name touch hacked test"),
        ("   ", "recording"),
    ],
)
def test_filename_sanitisation(raw: str, expected: str) -> None:
    assert sanitize_recording_name(raw) == expected


def test_duplicate_name_prevention(tmp_path) -> None:
    now = datetime(2026, 8, 1, 12, 30, 45)
    first = unique_partial_path(tmp_path, "Tape", now)
    first.touch()
    second = unique_partial_path(tmp_path, "Tape", now)
    assert first.name == "Tape_2026-08-01_12-30-45.part.mkv"
    assert second.name == "Tape_2026-08-01_12-30-45-2.part.mkv"


def test_safe_capture_file_rejects_traversal(tmp_path) -> None:
    with pytest.raises(ValueError):
        safe_capture_file(tmp_path, "../secret.mkv")
    assert safe_capture_file(tmp_path, "safe.mkv") == tmp_path / "safe.mkv"


def test_interrupted_recording_discovery(tmp_path) -> None:
    (tmp_path / "old.part.mkv").write_bytes(b"partial")
    (tmp_path / "done.mkv").write_bytes(b"done")
    catalog = RecordingCatalog(tmp_path)
    assert [item.name for item in catalog.interrupted()] == ["old.part.mkv"]


def test_recording_list_metadata(tmp_path, monkeypatch) -> None:
    completed = tmp_path / "completed.mkv"
    completed.write_bytes(b"media")
    partial = tmp_path / "interrupted.part.mkv"
    partial.write_bytes(b"partial")

    def fake_probe(_bin, _path):
        return {
            "format": {"duration": "12.5", "size": "5"},
            "streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
        }

    monkeypatch.setattr("app.recordings.probe_media", fake_probe)
    items = RecordingCatalog(tmp_path).list()
    by_name = {item["filename"]: item for item in items}
    assert by_name["completed.mkv"]["duration_seconds"] == 12.5
    assert by_name["completed.mkv"]["streams"] == ["video", "audio"]
    assert by_name["interrupted.part.mkv"]["interrupted"] is True
    assert by_name["interrupted.part.mkv"]["recoverable"] is True


def test_catalog_hides_recovering_and_marks_preserved_recovered_partial(
    tmp_path, monkeypatch
) -> None:
    partial = tmp_path / "Tape_2026-08-13_07-00-00.part.mkv"
    completed = tmp_path / "Tape_2026-08-13_07-00-00.mkv"
    recovering = tmp_path / "Other_2026-08-13_07-00-00.recovering.mkv"
    partial.write_bytes(b"partial")
    completed.write_bytes(b"completed")
    recovering.write_bytes(b"transitional")

    monkeypatch.setattr(
        "app.recordings.probe_media",
        lambda _bin, _path: {
            "format": {"duration": "12.0"},
            "streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
        },
    )

    items = RecordingCatalog(tmp_path).list()
    by_name = {item["filename"]: item for item in items}

    assert recovering.name not in by_name
    assert by_name[partial.name]["recovered"] is True
    assert by_name[partial.name]["recoverable"] is False


def test_recovery_rejects_audio_less_result_and_removes_transitional_file(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "Tape_2026-08-13_07-00-00.part.mkv"
    source.write_bytes(b"partial")

    class Result:
        returncode = 0
        stderr = ""

    monkeypatch.setattr("app.recordings.subprocess.run", lambda *args, **kwargs: Result())
    monkeypatch.setattr(
        "app.recordings.probe_media",
        lambda _bin, _path: {
            "format": {"duration": "12.0"},
            "streams": [{"codec_type": "video"}],
        },
    )

    catalog = RecordingCatalog(tmp_path)
    with pytest.raises(ValueError, match="audio"):
        catalog.recover(source.name)

    assert source.exists()
    assert not (tmp_path / "Tape_2026-08-13_07-00-00.recovering.mkv").exists()
    assert not (tmp_path / "Tape_2026-08-13_07-00-00.mkv").exists()
