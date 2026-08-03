from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import main
from app.manager import CaptureConflict


def test_preview_start_endpoint_reports_idempotent_result(monkeypatch) -> None:
    monkeypatch.setattr(main.manager, "start_preview", lambda: False)

    response = main.start_preview()

    assert response == {"accepted": True, "started": False}


def test_preview_stop_endpoint_rejects_recording(monkeypatch) -> None:
    def reject_stop() -> bool:
        raise CaptureConflict("preview cannot be stopped while recording")

    monkeypatch.setattr(main.manager, "stop_preview", reject_stop)

    with pytest.raises(HTTPException) as exc_info:
        main.stop_preview()

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "preview cannot be stopped while recording"


def test_preview_heartbeat_does_not_start_dormant_capture(monkeypatch) -> None:
    monkeypatch.setattr(main.manager, "preview_heartbeat", lambda: False)

    response = main.preview_heartbeat()

    assert response == {"active": False}


def test_status_reports_dormant_without_preview_publisher(monkeypatch) -> None:
    monkeypatch.setattr(
        main.manager,
        "status",
        lambda: {
            "state": "idle",
            "process_alive": False,
            "preview_available": False,
            "filename": None,
        },
    )
    monkeypatch.setattr(main.manager.catalog, "disk", lambda: {"free_bytes": 1})
    monkeypatch.setattr(main.manager.catalog, "interrupted", lambda: [])
    monkeypatch.setattr(main, "preview_service_status", lambda: (True, False))

    response = main.api_status()

    assert response["state"] == "idle"
    assert response["preview_transport_reachable"] is True
    assert response["preview_available"] is False


def test_status_reports_unavailable_preview_transport(monkeypatch) -> None:
    monkeypatch.setattr(
        main.manager,
        "status",
        lambda: {
            "state": "preview_available",
            "process_alive": True,
            "preview_available": True,
            "filename": None,
            "last_error": None,
        },
    )
    monkeypatch.setattr(main.manager.catalog, "disk", lambda: {"free_bytes": 1})
    monkeypatch.setattr(main.manager.catalog, "interrupted", lambda: [])
    monkeypatch.setattr(main, "preview_service_status", lambda: (False, False))

    response = main.api_status()

    assert response["state"] == "error"
    assert response["preview_available"] is False
    assert "MediaMTX" in response["last_error"]
