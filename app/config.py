from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

VIDEO_STANDARDS = {
    "PAL": {"size": "720x576", "fps": "25", "gop": 25, "sar": "16/15"},
    "NTSC": {"size": "720x480", "fps": "30000/1001", "gop": 30, "sar": "8/9"},
}


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _integer(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _resolution(name: str, default: str) -> str:
    value = os.getenv(name, default).strip().lower()
    match = re.fullmatch(r"([1-9][0-9]{1,4})x([1-9][0-9]{1,4})", value)
    if not match:
        raise ValueError(f"{name} must use WIDTHxHEIGHT, for example 640x480")
    return value


@dataclass(frozen=True)
class Settings:
    capture_dir: Path = Path("/captures")
    log_dir: Path = Path("/app/logs")
    state_dir: Path = Path("/app/state")
    video_device: str = "/dev/video0"
    audio_device: str = "hw:CARD=Device,DEV=0"
    video_standard: str = "PAL"
    video_size: str = "720x576"
    video_fps: str = "25"
    video_gop: int = 25
    master_sar: str = "16/15"
    preview_resolution: str = "640x480"
    preview_video_bitrate: str = "800k"
    preview_audio_bitrate: str = "64k"
    recording_video_bitrate: str = "2000k"
    recording_video_maxrate: str = "2400k"
    recording_video_buffer: str = "4000k"
    recording_audio_bitrate: str = "128k"
    audio_rate: int = 48000
    audio_channels: int = 2
    preview_rtsp_url: str = "rtsp://mediamtx:8554/vhs"
    mediamtx_api_url: str = "http://mediamtx:9997"
    webrtc_http_port: int = 8889
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    ffmpeg_log_level: str = "warning"
    log_level: str = "INFO"
    synthetic_input: bool = False
    auto_preview: bool = True
    preview_restart_seconds: float = 3.0
    graceful_stop_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> Settings:
        standard = os.getenv("VIDEO_STANDARD", "PAL").strip().upper()
        if standard not in VIDEO_STANDARDS:
            raise ValueError("VIDEO_STANDARD must be PAL or NTSC")
        preset = VIDEO_STANDARDS[standard]
        return cls(
            capture_dir=Path(os.getenv("CAPTURE_DIR", "/captures")),
            log_dir=Path(os.getenv("LOG_DIR", "/app/logs")),
            state_dir=Path(os.getenv("STATE_DIR", "/app/state")),
            video_device=os.getenv("VIDEO_DEVICE", "/dev/video0"),
            audio_device=os.getenv("AUDIO_DEVICE", "hw:CARD=Device,DEV=0"),
            video_standard=standard,
            video_size=str(preset["size"]),
            video_fps=str(preset["fps"]),
            video_gop=int(preset["gop"]),
            master_sar=str(preset["sar"]),
            preview_resolution=_resolution("PREVIEW_RESOLUTION", "640x480"),
            preview_video_bitrate=os.getenv("PREVIEW_VIDEO_BITRATE", "800k"),
            preview_audio_bitrate=os.getenv("PREVIEW_AUDIO_BITRATE", "64k"),
            recording_video_bitrate=os.getenv("RECORDING_VIDEO_BITRATE", "2000k"),
            recording_video_maxrate=os.getenv("RECORDING_VIDEO_MAXRATE", "2400k"),
            recording_video_buffer=os.getenv("RECORDING_VIDEO_BUFFER", "4000k"),
            recording_audio_bitrate=os.getenv("RECORDING_AUDIO_BITRATE", "128k"),
            audio_rate=_integer("AUDIO_RATE", 48000),
            audio_channels=_integer("AUDIO_CHANNELS", 2),
            preview_rtsp_url=os.getenv("PREVIEW_RTSP_URL", "rtsp://mediamtx:8554/vhs"),
            mediamtx_api_url=os.getenv("MEDIAMTX_API_URL", "http://mediamtx:9997"),
            webrtc_http_port=_integer("WEBRTC_HTTP_PORT", 8889),
            ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
            ffprobe_bin=os.getenv("FFPROBE_BIN", "ffprobe"),
            ffmpeg_log_level=os.getenv("FFMPEG_LOG_LEVEL", "warning"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            synthetic_input=_bool("SYNTHETIC_INPUT"),
            auto_preview=_bool("AUTO_PREVIEW", True),
            preview_restart_seconds=float(os.getenv("PREVIEW_RESTART_SECONDS", "3")),
            graceful_stop_seconds=float(os.getenv("GRACEFUL_STOP_SECONDS", "30")),
        )
