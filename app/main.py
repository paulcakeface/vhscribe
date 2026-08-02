from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Settings
from .devices import discover_devices
from .manager import CaptureConflict, CaptureManager, InvalidState
from .recordings import safe_capture_file, sanitize_recording_name

settings = Settings.from_env()
manager = CaptureManager(settings)


class StartRequest(BaseModel):
    name: str = Field(default="recording", max_length=200)


@asynccontextmanager
async def lifespan(_: FastAPI):
    manager.startup()
    try:
        yield
    finally:
        manager.shutdown()


app = FastAPI(title="VHScribe", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


def preview_service_ready() -> bool:
    try:
        with urllib.request.urlopen(
            f"{settings.mediamtx_api_url}/v3/paths/list", timeout=0.75
        ) as response:
            data = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False
    return any(
        item.get("name") == "vhs" and item.get("ready") is True and "H264" in item.get("tracks", [])
        for item in data.get("items", [])
    )


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = (Path(__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/api/status")
def api_status() -> dict:
    status = manager.status()
    preview_ready = status["process_alive"] and preview_service_ready()
    status["preview_available"] = preview_ready
    status["preview_service_available"] = preview_ready
    if status["state"] == "preview_available" and not preview_ready:
        status["state"] = "initialising"
    status["disk"] = manager.catalog.disk()
    status["interrupted_count"] = sum(
        1 for path in manager.catalog.interrupted() if path.name != status.get("filename")
    )
    return status


@app.get("/api/health")
def api_health() -> JSONResponse:
    checks = {
        "capture_directory": settings.capture_dir.is_dir(),
        "capture_directory_writable": settings.capture_dir.is_dir()
        and os.access(settings.capture_dir, os.W_OK),
        "video_device": settings.synthetic_input or Path(settings.video_device).exists(),
        "ffmpeg_process": manager.status()["process_alive"] or not settings.auto_preview,
        "mediamtx_preview": False,
    }
    checks["mediamtx_preview"] = preview_service_ready()
    healthy = all(checks.values())
    return JSONResponse({"healthy": healthy, "checks": checks}, status_code=200 if healthy else 503)


@app.post("/api/recordings/start", status_code=202)
def start_recording(payload: StartRequest) -> dict:
    clean_name = sanitize_recording_name(payload.name)
    try:
        output = manager.start_recording(clean_name)
    except CaptureConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidState as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"accepted": True, "filename": output.name, "sanitized_name": clean_name}


@app.post("/api/recordings/stop")
def stop_recording() -> dict:
    try:
        output = manager.stop_recording()
    except InvalidState as exc:
        status = 409 if "no recording" in str(exc) else 500
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return {"stopped": True, "filename": output.name}


@app.get("/api/recordings")
def list_recordings() -> dict:
    active = manager.status().get("filename")
    recordings = [item for item in manager.catalog.list() if item["filename"] != active]
    return {"recordings": recordings, "disk": manager.catalog.disk()}


@app.post("/api/recordings/{filename}/recover")
def recover_recording(filename: str) -> dict:
    active = manager.status().get("filename")
    try:
        output = manager.catalog.recover(filename, active_filename=active)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"recovered": True, "filename": output.name, "partial_preserved": True}


@app.post("/api/preview/restart", status_code=202)
def restart_preview() -> dict:
    try:
        manager.restart_preview()
    except CaptureConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"accepted": True}


@app.get("/recordings/{filename}")
def recording_file(filename: str, download: bool = Query(False)) -> FileResponse:
    try:
        path = safe_capture_file(settings.capture_dir, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid filename") from exc
    if not path.is_file() or path.name.endswith(".part.mkv"):
        raise HTTPException(status_code=404, detail="completed recording not found")
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path, filename=path.name if download else None, content_disposition_type=disposition
    )


@app.get("/api/config")
def api_config(request: Request) -> dict:
    return {
        "preview_url": (
            f"{request.url.scheme}://{request.url.hostname}:{settings.webrtc_http_port}/vhs"
        ),
        "allowed_name_characters": "letters, numbers, spaces, underscores, and hyphens",
        "video_standard": settings.video_standard,
        "master_resolution": settings.video_size,
        "master_display_aspect_ratio": "4:3",
    }


@app.get("/api/devices")
def api_devices() -> dict:
    devices = discover_devices(settings.video_standard)
    devices["configured"] = {
        "video": "synthetic test source" if settings.synthetic_input else settings.video_device,
        "audio": "synthetic sine source" if settings.synthetic_input else settings.audio_device,
    }
    return devices
