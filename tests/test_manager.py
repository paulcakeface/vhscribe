from __future__ import annotations

import io
import os
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


def manager_for(tmp_path: Path) -> CaptureManager:
    settings = Settings(
        capture_dir=tmp_path / "captures",
        log_dir=tmp_path / "logs",
        state_dir=tmp_path / "state",
        synthetic_input=True,
        auto_preview=False,
    )
    manager = CaptureManager(settings, popen_factory=FakePopen(), start_monitor=False)
    manager.startup()
    return manager


def test_state_transitions_start_and_stop(tmp_path, monkeypatch) -> None:
    manager = manager_for(tmp_path)
    partial = manager.start_recording("Tape")
    assert manager.status()["state"] == "starting_recording"
    assert manager.status()["recording"] is True
    partial.write_bytes(b"valid test media")
    manager._state = "recording"

    def fake_finalize(path):
        final = final_path_for(path)
        os.rename(path, final)
        return final

    monkeypatch.setattr(manager, "_validate_and_finalize", fake_finalize)
    final = manager.stop_recording(restart_preview=False)
    assert final.exists()
    assert manager.status()["state"] == "preview_available"
    assert manager.status()["recording"] is False


def test_attempt_to_start_second_recording(tmp_path) -> None:
    manager = manager_for(tmp_path)
    manager.start_recording("First")
    with pytest.raises(CaptureConflict):
        manager.start_recording("Second")


def test_stopping_while_idle(tmp_path) -> None:
    manager = manager_for(tmp_path)
    with pytest.raises(InvalidState, match="no recording"):
        manager.stop_recording()
