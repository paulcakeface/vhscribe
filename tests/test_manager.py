from __future__ import annotations

import io
import os
import threading
from pathlib import Path

import pytest

from app.config import Settings
from app.manager import CaptureConflict, CaptureManager, InvalidState
from app.recordings import final_path_for


class FakeProcess:
    def __init__(self) -> None:
        self.returncode = None
        self.stdout = io.StringIO("")
        self.stderr = io.StringIO("")
        self.signals = []

    def poll(self):
        return self.returncode

    def send_signal(self, value):
        self.signals.append(value)
        self.returncode = 0

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def terminate(self):
        self.returncode = 0

    def kill(self):
        self.returncode = -9


class FakePopen:
    def __init__(self) -> None:
        self.calls = []
        self.processes = []

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        process = FakeProcess()
        self.processes.append(process)
        return process


def manager_for(
    tmp_path: Path, *, preview_idle_timeout_seconds: int = 300
) -> tuple[CaptureManager, FakePopen]:
    settings = Settings(
        capture_dir=tmp_path / "captures",
        log_dir=tmp_path / "logs",
        state_dir=tmp_path / "state",
        synthetic_input=True,
        preview_idle_timeout_seconds=preview_idle_timeout_seconds,
    )
    popen = FakePopen()
    manager = CaptureManager(settings, popen_factory=popen, start_monitor=False)
    manager.startup()
    return manager, popen


def finish_recording(manager: CaptureManager, monkeypatch: pytest.MonkeyPatch) -> Path:
    partial = Path(manager.status()["filename"] or "")
    partial = manager.settings.capture_dir / partial
    partial.write_bytes(b"valid test media")
    manager._state = "recording"

    def fake_finalize(path):
        final = final_path_for(path)
        os.rename(path, final)
        return final

    monkeypatch.setattr(manager, "_validate_and_finalize", fake_finalize)
    return manager.stop_recording()


def test_application_starts_dormant_without_ffmpeg(tmp_path) -> None:
    manager, popen = manager_for(tmp_path)

    assert manager.status()["state"] == "idle"
    assert manager.status()["process_alive"] is False
    assert popen.calls == []


def test_preview_starts_on_request(tmp_path) -> None:
    manager, popen = manager_for(tmp_path)

    assert manager.start_preview() is True

    assert len(popen.calls) == 1
    assert manager.status()["state"] == "starting_preview"
    assert manager.status()["mode"] == "preview"


def test_repeated_preview_start_is_idempotent(tmp_path) -> None:
    manager, popen = manager_for(tmp_path)

    assert manager.start_preview() is True
    assert manager.start_preview() is False

    assert len(popen.calls) == 1
    assert sum(process.poll() is None for process in popen.processes) == 1


def test_preview_stops_manually(tmp_path) -> None:
    manager, popen = manager_for(tmp_path)
    manager.start_preview()

    assert manager.stop_preview() is True

    assert popen.processes[0].signals
    assert manager.status()["state"] == "idle"
    assert manager.status()["process_alive"] is False


def test_preview_stops_after_heartbeat_timeout(tmp_path, monkeypatch) -> None:
    clock = [0.0]
    monkeypatch.setattr("app.manager.time.monotonic", lambda: clock[0])
    manager, _ = manager_for(tmp_path, preview_idle_timeout_seconds=10)
    manager.start_preview()

    clock[0] = 11.0
    manager._monitor_once()

    assert manager.status()["state"] == "idle"
    assert manager.status()["process_alive"] is False


def test_heartbeat_prevents_premature_preview_shutdown(tmp_path, monkeypatch) -> None:
    clock = [0.0]
    monkeypatch.setattr("app.manager.time.monotonic", lambda: clock[0])
    manager, _ = manager_for(tmp_path, preview_idle_timeout_seconds=10)
    manager.start_preview()

    clock[0] = 8.0
    assert manager.preview_heartbeat() is True
    clock[0] = 17.0
    manager._monitor_once()

    assert manager.status()["process_alive"] is True
    assert manager.status()["state"] == "preview_available"


def test_timeout_never_stops_active_recording(tmp_path, monkeypatch) -> None:
    clock = [0.0]
    monkeypatch.setattr("app.manager.time.monotonic", lambda: clock[0])
    manager, _ = manager_for(tmp_path, preview_idle_timeout_seconds=1)
    manager.start_recording("Tape")

    clock[0] = 60.0
    manager._monitor_once()

    assert manager.status()["recording"] is True
    assert manager.status()["state"] == "recording"
    assert manager.status()["process_alive"] is True


def test_timeout_race_with_recording_transition_is_safe(tmp_path, monkeypatch) -> None:
    clock = [0.0]
    monkeypatch.setattr("app.manager.time.monotonic", lambda: clock[0])
    manager, _ = manager_for(tmp_path, preview_idle_timeout_seconds=1)
    manager.start_preview()

    def transition_won(**kwargs) -> bool:
        raise CaptureConflict("recording transition won the lock")

    monkeypatch.setattr(manager, "stop_preview", transition_won)
    clock[0] = 2.0

    manager._monitor_once()


def test_recording_starts_from_dormant_state(tmp_path) -> None:
    manager, popen = manager_for(tmp_path)

    manager.start_recording("Tape")

    assert len(popen.calls) == 1
    assert manager.status()["mode"] == "recording"
    assert manager.status()["recording"] is True


def test_recording_starts_from_preview_state(tmp_path) -> None:
    manager, popen = manager_for(tmp_path)
    manager.start_preview()

    manager.start_recording("Tape")

    assert len(popen.calls) == 2
    assert popen.processes[0].poll() == 0
    assert popen.processes[1].poll() is None
    assert manager.status()["mode"] == "recording"


def test_stopping_recording_returns_to_dormant_state(tmp_path, monkeypatch) -> None:
    manager, _ = manager_for(tmp_path)
    manager.start_recording("Tape")

    final = finish_recording(manager, monkeypatch)

    assert final.exists()
    assert manager.status()["state"] == "idle"
    assert manager.status()["recording"] is False
    assert manager.status()["process_alive"] is False


def test_stop_preview_is_rejected_during_recording(tmp_path) -> None:
    manager, _ = manager_for(tmp_path)
    manager.start_recording("Tape")

    with pytest.raises(CaptureConflict, match="while recording"):
        manager.stop_preview()


def test_concurrent_preview_and_recording_keep_one_capture_owner(tmp_path) -> None:
    manager, popen = manager_for(tmp_path)
    barrier = threading.Barrier(3)
    errors: list[Exception] = []

    def request_preview() -> None:
        barrier.wait()
        try:
            manager.start_preview()
        except Exception as exc:  # pragma: no cover - assertion below reports the race failure
            errors.append(exc)

    def request_recording() -> None:
        barrier.wait()
        try:
            manager.start_recording("Concurrent")
        except Exception as exc:  # pragma: no cover - assertion below reports the race failure
            errors.append(exc)

    preview_thread = threading.Thread(target=request_preview)
    recording_thread = threading.Thread(target=request_recording)
    preview_thread.start()
    recording_thread.start()
    barrier.wait()
    preview_thread.join()
    recording_thread.join()

    assert all(isinstance(error, CaptureConflict) for error in errors)
    assert sum(process.poll() is None for process in popen.processes) == 1
    assert manager.status()["mode"] == "recording"


def test_attempt_to_start_second_recording(tmp_path) -> None:
    manager, _ = manager_for(tmp_path)
    manager.start_recording("First")
    with pytest.raises(CaptureConflict):
        manager.start_recording("Second")


def test_stopping_while_idle(tmp_path) -> None:
    manager, _ = manager_for(tmp_path)
    with pytest.raises(InvalidState, match="no recording"):
        manager.stop_recording()


def valid_probe_data() -> dict:
    return {
        "format": {"duration": "12.5", "size": "12345", "format_name": "matroska,webm"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 720,
                "height": 576,
                "r_frame_rate": "25/1",
                "avg_frame_rate": "25/1",
                "sample_aspect_ratio": "16:15",
                "display_aspect_ratio": "4:3",
                "pix_fmt": "yuv420p",
                "field_order": "progressive",
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
            },
        ],
    }


def test_finalize_rejects_wrong_master_geometry(tmp_path, monkeypatch) -> None:
    manager, _ = manager_for(tmp_path)
    partial = manager.settings.capture_dir / "bad.part.mkv"
    partial.write_bytes(b"media")
    probe = valid_probe_data()
    probe["streams"][0]["width"] = 640
    monkeypatch.setattr("app.manager.probe_media", lambda _bin, _path: probe)

    with pytest.raises(ValueError, match="geometry"):
        manager._validate_and_finalize(partial)

    assert partial.exists()
    assert not final_path_for(partial).exists()


def test_stop_recording_writes_qc_manifest_with_checksum(tmp_path, monkeypatch) -> None:
    manager, _ = manager_for(tmp_path)
    manager.start_recording("Tape")
    partial = manager.settings.capture_dir / str(manager.status()["filename"])
    partial.write_bytes(b"valid test media")
    manager._state = "recording"
    monkeypatch.setattr("app.manager.probe_media", lambda _bin, _path: valid_probe_data())

    final = manager.stop_recording()
    manifest = final.with_name(final.name + ".qc.json")

    assert final.exists()
    assert manifest.exists()
    payload = __import__("json").loads(manifest.read_text())
    assert payload["schema_version"] == 1
    assert payload["recording"] == final.name
    assert payload["qc_status"] == "verified"
    assert payload["sha256"]
    assert payload["validation"]["geometry"] == "720x576"
    assert payload["validation"]["frame_rate"] == "25/1"
    assert payload["validation"]["audio"] == "48000Hz/2ch"


def test_stop_recording_marks_capture_drop_as_needs_review(tmp_path, monkeypatch) -> None:
    manager, _ = manager_for(tmp_path)
    manager.start_recording("Tape")
    partial = manager.settings.capture_dir / str(manager.status()["filename"])
    partial.write_bytes(b"valid test media")
    manager._state = "recording"
    manager._progress = {"drop_frames": 3.0, "dup_frames": 0.0}
    monkeypatch.setattr("app.manager.probe_media", lambda _bin, _path: valid_probe_data())

    final = manager.stop_recording()
    payload = __import__("json").loads(final.with_name(final.name + ".qc.json").read_text())

    assert payload["qc_status"] == "needs_review"
    assert payload["progress"]["drop_frames"] == 3.0


def test_start_recording_rejected_after_shutdown_begins(tmp_path) -> None:
    manager, _ = manager_for(tmp_path)
    manager._shutdown = True
    with pytest.raises(InvalidState, match="shutting down"):
        manager.start_recording("Too late")


def test_validation_falls_back_to_r_frame_rate_when_average_is_unknown(
    tmp_path, monkeypatch
) -> None:
    manager, _ = manager_for(tmp_path)
    partial = manager.settings.capture_dir / "valid.part.mkv"
    partial.write_bytes(b"media")
    probe = valid_probe_data()
    probe["streams"][0]["avg_frame_rate"] = "0/0"
    probe["streams"][0]["r_frame_rate"] = "25/1"
    monkeypatch.setattr("app.manager.probe_media", lambda _bin, _path: probe)

    final = manager._validate_and_finalize(partial)

    assert final.exists()
