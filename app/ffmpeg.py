from __future__ import annotations

from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from .config import Settings


def _preview_video_filter(settings: Settings) -> str:
    width, height = settings.preview_resolution.lower().split("x", 1)
    return f"scale={width}:{height}:flags=fast_bilinear,setsar=1,format=yuv420p"


def _common(settings: Settings) -> list[str]:
    return [
        settings.ffmpeg_bin,
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        settings.ffmpeg_log_level,
        "-stats_period",
        "1",
        "-progress",
        "pipe:1",
    ]


def _inputs(settings: Settings) -> list[str]:
    if settings.synthetic_input:
        return [
            "-re",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={settings.video_size}:rate={settings.video_fps}",
            "-re",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=1000:sample_rate={settings.audio_rate}",
        ]
    return [
        "-thread_queue_size",
        "1024",
        "-fflags",
        "+genpts+discardcorrupt",
        "-f",
        "v4l2",
        "-input_format",
        "yuyv422",
        "-video_size",
        settings.video_size,
        "-framerate",
        str(settings.video_fps),
        "-i",
        settings.video_device,
        "-thread_queue_size",
        "1024",
        "-f",
        "alsa",
        "-ac",
        str(settings.audio_channels),
        "-ar",
        str(settings.audio_rate),
        "-i",
        settings.audio_device,
    ]


def _preview_output(settings: Settings, video_map: str, audio_map: str) -> list[str]:
    return [
        "-map",
        video_map,
        "-map",
        audio_map,
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-profile:v",
        "baseline",
        "-level:v",
        "3.0",
        "-b:v",
        settings.preview_video_bitrate,
        "-maxrate",
        "1000k",
        "-bufsize",
        "1200k",
        "-g",
        str(settings.video_gop),
        "-keyint_min",
        str(settings.video_gop),
        "-sc_threshold",
        "0",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "libopus",
        "-b:a",
        settings.preview_audio_bitrate,
        "-ar",
        "48000",
        "-ac",
        "2",
        "-f",
        "fifo",
        "-fifo_format",
        "rtsp",
        "-queue_size",
        "120",
        "-drop_pkts_on_overflow",
        "1",
        "-attempt_recovery",
        "1",
        "-recover_any_error",
        "1",
        "-recovery_wait_time",
        "1",
        "-restart_with_keyframe",
        "1",
        "-format_opts",
        "rtsp_transport=tcp",
        settings.preview_rtsp_url,
    ]


def build_preview_command(settings: Settings) -> list[str]:
    command = _common(settings) + _inputs(settings)
    command += [
        "-filter_complex",
        f"[0:v]{_preview_video_filter(settings)}[vpreview];"
        "[1:a]aresample=async=1:first_pts=0[apreview]",
    ]
    command += _preview_output(settings, "[vpreview]", "[apreview]")
    return command


def build_record_command(settings: Settings, output: Path) -> list[str]:
    command = _common(settings) + _inputs(settings)
    command += [
        "-filter_complex",
        "[0:v]split=2[vmastersrc][vprevsrc];"
        f"[vmastersrc]setsar={settings.master_sar}[vmain];"
        f"[vprevsrc]{_preview_video_filter(settings)}[vpreview];"
        "[1:a]asplit=2[amainsrc][aprevsrc];"
        "[amainsrc]aresample=async=1:first_pts=0[amaster];"
        "[aprevsrc]aresample=async=1:first_pts=0[apreview]",
        "-map",
        "[vmain]",
        "-map",
        "[amaster]",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-b:v",
        settings.recording_video_bitrate,
        "-maxrate",
        settings.recording_video_maxrate,
        "-bufsize",
        settings.recording_video_buffer,
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(settings.video_fps),
        "-c:a",
        "aac",
        "-b:a",
        settings.recording_audio_bitrate,
        "-ar",
        str(settings.audio_rate),
        "-ac",
        str(settings.audio_channels),
        "-aspect",
        "4:3",
        "-f",
        "matroska",
        "-flush_packets",
        "1",
        "-cluster_time_limit",
        "1000",
        "-cluster_size_limit",
        "2M",
        str(output),
    ]
    command += _preview_output(settings, "[vpreview]", "[apreview]")
    return command


@dataclass
class ProgressParser:
    values: dict[str, str] = field(default_factory=dict)

    def feed(self, line: str) -> dict[str, object] | None:
        line = line.strip()
        if not line or "=" not in line:
            return None
        key, value = line.split("=", 1)
        self.values[key] = value
        if key != "progress":
            return None
        snapshot: dict[str, object] = dict(self.values)
        raw_time = self.values.get("out_time_us") or self.values.get("out_time_ms")
        if raw_time:
            with suppress(ValueError):
                # FFmpeg's out_time_ms value is historically named but is microseconds.
                snapshot["elapsed_seconds"] = max(0.0, int(raw_time) / 1_000_000)
        for numeric in ("frame", "fps", "total_size", "dup_frames", "drop_frames"):
            if numeric in snapshot:
                with suppress(ValueError):
                    snapshot[numeric] = float(str(snapshot[numeric]))
        self.values = {}
        return snapshot


def parse_progress(lines: Iterable[str]) -> list[dict[str, object]]:
    parser = ProgressParser()
    updates = []
    for line in lines:
        update = parser.feed(line)
        if update is not None:
            updates.append(update)
    return updates
