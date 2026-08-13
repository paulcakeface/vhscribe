from __future__ import annotations

import logging
import os
import re
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from fractions import Fraction
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from .config import Settings
from .ffmpeg import ProgressParser, build_preview_command, build_record_command
from .recordings import (
    RecordingCatalog,
    atomic_write_json,
    final_path_for,
    probe_media,
    qc_manifest_path,
    require_video_and_audio,
    sha256_file,
    unique_partial_path,
)

_CAPTURE_WARNING_PATTERNS = {
    "corrupt_input": re.compile(r"corrupt(?:ed)? data|discarding corrupt", re.I),
    "audio_xrun": re.compile(r"ALSA buffer xrun|\bxrun\b", re.I),
    "queue_pressure": re.compile(r"Thread message queue blocking|FIFO queue full", re.I),
    "frame_duplication_warning": re.compile(r"frames duplicated", re.I),
    "input_io_error": re.compile(r"Error during demuxing|Input/output error|No such device", re.I),
}


def _same_fraction(actual: str | None, expected: str) -> bool:
    if not actual or actual in {"0/0", "N/A"}:
        return False
    try:
        return Fraction(actual.replace(":", "/")) == Fraction(expected.replace(":", "/"))
    except (ValueError, ZeroDivisionError):
        return False


class CaptureConflict(RuntimeError):
    pass


class InvalidState(RuntimeError):
    pass


class CaptureManager:
    def __init__(
        self,
        settings: Settings,
        *,
        popen_factory: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
        start_monitor: bool = True,
    ) -> None:
        self.settings = settings
        self.catalog = RecordingCatalog(
            settings.capture_dir,
            ffprobe_bin=settings.ffprobe_bin,
            ffmpeg_bin=settings.ffmpeg_bin,
        )
        self._popen_factory = popen_factory
        self._start_monitor = start_monitor
        self._lock = threading.RLock()
        self._process: subprocess.Popen[str] | None = None
        self._process_mode: str | None = None
        self._process_started = 0.0
        self._expected_stop = False
        self._shutdown = False
        self._last_preview_heartbeat: float | None = None
        self._monitor_thread: threading.Thread | None = None
        self._reader_threads: list[threading.Thread] = []
        self._state = "idle"
        self._active_path: Path | None = None
        self._active_started_wall: float | None = None
        self._progress: dict[str, object] = {}
        self._last_error: str | None = None
        self._last_completed: str | None = None
        self._last_qc_status: str | None = None
        self._capture_warning_counts: dict[str, int] = {}
        self._logger = logging.getLogger(f"vhscribe.ffmpeg.{id(self)}")
        self._logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
        self._logger.propagate = False

    def startup(self) -> None:
        self.settings.capture_dir.mkdir(parents=True, exist_ok=True)
        self.settings.log_dir.mkdir(parents=True, exist_ok=True)
        self.settings.state_dir.mkdir(parents=True, exist_ok=True)
        if not self._logger.handlers:
            handler = RotatingFileHandler(
                self.settings.log_dir / "ffmpeg.log",
                maxBytes=5 * 1024 * 1024,
                backupCount=5,
            )
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self._logger.addHandler(handler)
        if self._start_monitor:
            self._monitor_thread = threading.Thread(
                target=self._monitor, name="capture-monitor", daemon=True
            )
            self._monitor_thread.start()
        with self._lock:
            self._state = "idle"

    def _safe_error(self, message: str) -> str:
        message = " ".join(message.strip().split())
        message = message.replace(str(self.settings.capture_dir), "capture storage")
        message = message.replace(self.settings.preview_rtsp_url, "preview service")
        return message[-500:] or "FFmpeg exited unexpectedly"

    def _record_capture_warning(self, line: str) -> None:
        with self._lock:
            for name, pattern in _CAPTURE_WARNING_PATTERNS.items():
                if pattern.search(line):
                    self._capture_warning_counts[name] = (
                        self._capture_warning_counts.get(name, 0) + 1
                    )

    def _log_stderr(self, process: subprocess.Popen[str], mode: str) -> None:
        if process.stderr is None:
            return
        recent: list[str] = []
        for line in process.stderr:
            cleaned = line.rstrip()
            if cleaned:
                self._logger.warning("[%s] %s", mode, cleaned)
                if mode == "recording":
                    self._record_capture_warning(cleaned)
                recent.append(cleaned)
                recent = recent[-8:]
        if recent and process.poll() not in (None, 0) and not self._expected_stop:
            with self._lock:
                self._last_error = self._safe_error(recent[-1])

    def _read_progress(self, process: subprocess.Popen[str]) -> None:
        if process.stdout is None:
            return
        parser = ProgressParser()
        for line in process.stdout:
            update = parser.feed(line)
            if update is not None:
                with self._lock:
                    if self._process is process:
                        self._progress = update

    def _launch(self, command: list[str], mode: str) -> subprocess.Popen[str]:
        self._logger.info("starting %s FFmpeg process", mode)
        process = self._popen_factory(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        self._process = process
        self._process_mode = mode
        self._process_started = time.monotonic()
        self._expected_stop = False
        self._progress = {}
        progress_thread = threading.Thread(target=self._read_progress, args=(process,), daemon=True)
        stderr_thread = threading.Thread(target=self._log_stderr, args=(process, mode), daemon=True)
        self._reader_threads = [progress_thread, stderr_thread]
        progress_thread.start()
        stderr_thread.start()
        return process

    def _stop_process(self, process: subprocess.Popen[str]) -> int:
        if process.poll() is not None:
            return int(process.returncode or 0)
        try:
            process.send_signal(signal.SIGINT)
            return process.wait(timeout=self.settings.graceful_stop_seconds)
        except subprocess.TimeoutExpired:
            self._logger.error("FFmpeg did not stop after SIGINT; sending SIGTERM")
            process.terminate()
            try:
                return process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._logger.error("FFmpeg did not stop after SIGTERM; sending SIGKILL")
                process.kill()
                return process.wait(timeout=5)

    def start_preview(self) -> bool:
        with self._lock:
            if self._shutdown:
                raise InvalidState("capture service is shutting down")
            if self._state in {"starting_recording", "stopping"}:
                raise CaptureConflict("preview cannot start during a capture transition")
            if self._active_path is not None or self._process_mode == "recording":
                self._last_preview_heartbeat = time.monotonic()
                return False
            if self._process is not None and self._process.poll() is None:
                self._last_preview_heartbeat = time.monotonic()
                return False
            if self._process is not None:
                self._process = None
                self._process_mode = None
            self._state = "starting_preview"
            self._last_error = None
            self._last_preview_heartbeat = time.monotonic()
            try:
                self._launch(build_preview_command(self.settings), "preview")
                return True
            except OSError as exc:
                self._state = "error"
                self._last_error = self._safe_error(str(exc))
                self._last_preview_heartbeat = None
                raise InvalidState("FFmpeg preview could not start") from exc

    def preview_heartbeat(self) -> bool:
        with self._lock:
            process_alive = self._process is not None and self._process.poll() is None
            if process_alive and self._process_mode in {"preview", "recording"}:
                self._last_preview_heartbeat = time.monotonic()
                return True
            return False

    def stop_preview(self, *, idle_heartbeat: float | None = None) -> bool:
        with self._lock:
            if self._active_path is not None or self._process_mode == "recording":
                raise CaptureConflict("preview cannot be stopped while recording")
            if self._state == "starting_recording":
                raise CaptureConflict("preview cannot stop during a recording transition")
            if idle_heartbeat is not None and self._last_preview_heartbeat != idle_heartbeat:
                return False
            process = self._process if self._process_mode == "preview" else None
            if process is None or process.poll() is not None:
                if self._process is process:
                    self._process = None
                    self._process_mode = None
                self._state = "idle"
                self._last_preview_heartbeat = None
                return False
            self._expected_stop = True
            self._state = "stopping"
        self._stop_process(process)
        with self._lock:
            if self._process is process:
                self._process = None
                self._process_mode = None
            self._expected_stop = False
            self._progress = {}
            self._last_preview_heartbeat = None
            self._state = "idle"
        return True

    def restart_preview(self) -> None:
        with self._lock:
            if self._state in {"recording", "starting_recording", "stopping"}:
                raise CaptureConflict("preview cannot restart during a recording transition")
        self.stop_preview()
        self.start_preview()

    def start_recording(self, name: str) -> Path:
        with self._lock:
            if self._shutdown:
                raise InvalidState("capture service is shutting down")
            if self._state in {"recording", "starting_recording", "stopping"} or self._active_path:
                raise CaptureConflict("a recording is already active or changing state")
            process = self._process
            self._expected_stop = process is not None
            self._state = "starting_recording"
            self._last_error = None
            self._last_qc_status = None
            self._capture_warning_counts = {}
            self._last_preview_heartbeat = None
        if process is not None:
            self._stop_process(process)
        with self._lock:
            if self._process is process:
                self._process = None
                self._process_mode = None
            output = unique_partial_path(self.settings.capture_dir, name)
            try:
                launched = self._launch(build_record_command(self.settings, output), "recording")
            except OSError as exc:
                self._state = "error"
                self._last_error = self._safe_error(str(exc))
                self._expected_stop = False
                raise InvalidState("FFmpeg could not start") from exc
            self._active_path = output
            self._active_started_wall = time.time()
            self._process = launched
            self._expected_stop = False
            return output

    def _validate_probe(self, data: dict[str, Any]) -> dict[str, str]:
        require_video_and_audio(data)
        video = next(stream for stream in data["streams"] if stream.get("codec_type") == "video")
        audio = next(stream for stream in data["streams"] if stream.get("codec_type") == "audio")
        expected_width, expected_height = (
            int(value) for value in self.settings.video_size.split("x", 1)
        )
        if (video.get("width"), video.get("height")) != (expected_width, expected_height):
            raise ValueError(
                f"recording geometry is {video.get('width')}x{video.get('height')}, "
                f"expected {self.settings.video_size}"
            )
        reported_rates = [
            str(video.get("avg_frame_rate") or ""),
            str(video.get("r_frame_rate") or ""),
        ]
        actual_rate = next(
            (rate for rate in reported_rates if _same_fraction(rate, self.settings.video_fps)),
            None,
        )
        if actual_rate is None:
            reported = ", ".join(rate for rate in reported_rates if rate) or "unknown"
            raise ValueError(
                f"recording frame rate is {reported}, expected {self.settings.video_fps}"
            )
        if not _same_fraction(video.get("sample_aspect_ratio"), self.settings.master_sar):
            raise ValueError(
                f"recording sample aspect is {video.get('sample_aspect_ratio') or 'unknown'}, "
                f"expected {self.settings.master_sar}"
            )
        if not _same_fraction(video.get("display_aspect_ratio"), "4:3"):
            raise ValueError(
                "recording display aspect is "
                f"{video.get('display_aspect_ratio') or 'unknown'}, expected 4:3"
            )
        if str(audio.get("sample_rate") or "") != str(self.settings.audio_rate):
            raise ValueError(
                f"recording audio rate is {audio.get('sample_rate') or 'unknown'}, "
                f"expected {self.settings.audio_rate}"
            )
        if int(audio.get("channels") or 0) != self.settings.audio_channels:
            raise ValueError(
                f"recording audio channels are {audio.get('channels') or 'unknown'}, "
                f"expected {self.settings.audio_channels}"
            )
        duration = float(data.get("format", {}).get("duration", 0) or 0)
        if duration <= 0:
            raise ValueError("recording duration is missing or zero")
        return {
            "geometry": self.settings.video_size,
            "frame_rate": (
                f"{Fraction(self.settings.video_fps).numerator}/"
                f"{Fraction(self.settings.video_fps).denominator}"
            ),
            "sample_aspect_ratio": self.settings.master_sar,
            "display_aspect_ratio": "4:3",
            "audio": f"{self.settings.audio_rate}Hz/{self.settings.audio_channels}ch",
            "duration_seconds": f"{duration:.3f}",
        }

    def _full_decode_check(self, path: Path) -> None:
        result = subprocess.run(
            [
                self.settings.ffmpeg_bin,
                "-hide_banner",
                "-nostdin",
                "-v",
                "error",
                "-xerror",
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=4 * 3600,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError("recording failed the full decode integrity check")

    def _ffmpeg_version(self) -> str:
        try:
            result = subprocess.run(
                [self.settings.ffmpeg_bin, "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return "unknown"
        first = result.stdout.splitlines()[:1]
        return first[0].strip() if result.returncode == 0 and first else "unknown"

    def _validate_and_finalize(self, partial: Path) -> Path:
        if not partial.exists() or partial.stat().st_size <= 0:
            raise ValueError("recording did not produce a non-empty file")
        data = probe_media(self.settings.ffprobe_bin, partial)
        self._validate_probe(data)
        if self.settings.qc_full_decode:
            self._full_decode_check(partial)
        final = final_path_for(partial)
        if final.exists():
            raise FileExistsError("final recording filename already exists")
        os.rename(partial, final)
        return final

    def _write_qc_manifest(
        self,
        final: Path,
        *,
        exit_code: int | None,
        progress: dict[str, object],
        warning_counts: dict[str, int],
        started_wall: float | None,
    ) -> str:
        data = probe_media(self.settings.ffprobe_bin, final)
        validation = self._validate_probe(data)
        warnings = {key: value for key, value in warning_counts.items() if value}
        drop_frames = float(progress.get("drop_frames", 0) or 0)
        dup_frames = float(progress.get("dup_frames", 0) or 0)
        if drop_frames > 0 or dup_frames > 0:
            warnings["progress_frame_anomaly"] = int(drop_frames + dup_frames)
        if exit_code not in {None, 0, 255}:
            warnings["ffmpeg_exit_code"] = int(exit_code)
        checksum: str | None = None
        if self.settings.qc_checksum:
            try:
                checksum = sha256_file(final)
            except OSError:
                warnings["checksum_error"] = 1
        qc_status = "needs_review" if warnings else "verified"
        started = (
            datetime.fromtimestamp(started_wall, UTC).isoformat()
            if started_wall is not None
            else None
        )
        payload: dict[str, Any] = {
            "schema_version": 1,
            "recording": final.name,
            "qc_status": qc_status,
            "capture_started_utc": started,
            "completed_utc": datetime.now(UTC).isoformat(),
            "application": {
                "version": self.settings.app_version,
                "vcs_ref": self.settings.vcs_ref,
                "ffmpeg": self._ffmpeg_version(),
            },
            "capture": {
                "video_standard": self.settings.video_standard,
                "video_size": self.settings.video_size,
                "video_fps": self.settings.video_fps,
                "master_sar": self.settings.master_sar,
                "audio_rate": self.settings.audio_rate,
                "audio_channels": self.settings.audio_channels,
                "video_device": "synthetic test source"
                if self.settings.synthetic_input
                else self.settings.video_device,
                "audio_device": "synthetic sine source"
                if self.settings.synthetic_input
                else self.settings.audio_device,
            },
            "validation": validation,
            "full_decode": {
                "performed": self.settings.qc_full_decode,
                "passed": True if self.settings.qc_full_decode else None,
            },
            "ffmpeg_exit_code": exit_code,
            "progress": progress,
            "warning_counts": warnings,
            "sha256": checksum,
            "probe": data,
        }
        atomic_write_json(qc_manifest_path(final), payload)
        return qc_status

    def stop_recording(self) -> Path:
        with self._lock:
            if self._state not in {"recording", "starting_recording"} or not self._active_path:
                raise InvalidState("no recording is active")
            process = self._process
            partial = self._active_path
            started_wall = self._active_started_wall
            self._state = "stopping"
            self._expected_stop = True
        exit_code: int | None = None
        if process is not None:
            exit_code = self._stop_process(process)
            for thread in self._reader_threads:
                thread.join(timeout=1)
        with self._lock:
            progress = dict(self._progress)
            warning_counts = dict(self._capture_warning_counts)
        final: Path | None = None
        qc_status: str | None = None
        error: Exception | None = None
        try:
            final = self._validate_and_finalize(partial)
            try:
                qc_status = self._write_qc_manifest(
                    final,
                    exit_code=exit_code,
                    progress=progress,
                    warning_counts=warning_counts,
                    started_wall=started_wall,
                )
            except Exception:
                self._logger.exception("recording saved but QC manifest could not be written")
                qc_status = "needs_review"
        except Exception as exc:
            # The partial is deliberately retained on every validation failure.
            error = exc
        with self._lock:
            if self._process is process:
                self._process = None
                self._process_mode = None
            self._active_path = None
            self._active_started_wall = None
            self._progress = {}
            self._capture_warning_counts = {}
            self._expected_stop = False
            if error:
                self._state = "error"
                self._last_error = self._safe_error(str(error))
            else:
                self._last_completed = final.name if final else None
                self._last_qc_status = qc_status
                self._state = "idle"
                self._last_preview_heartbeat = None
        if error:
            raise InvalidState(str(error)) from error
        assert final is not None
        return final

    def _monitor_once(self) -> None:
        expired_heartbeat: float | None = None
        with self._lock:
            process = self._process
            if process is None:
                return
            returncode = process.poll()
            if returncode is None:
                now = time.monotonic()
                if now - self._process_started >= 1:
                    if self._process_mode == "preview" and self._state == "starting_preview":
                        self._state = "preview_available"
                    elif self._process_mode == "recording" and self._state == "starting_recording":
                        self._state = "recording"
                if (
                    self._process_mode == "preview"
                    and self._last_preview_heartbeat is not None
                    and now - self._last_preview_heartbeat
                    >= self.settings.preview_idle_timeout_seconds
                ):
                    expired_heartbeat = self._last_preview_heartbeat
            elif not self._expected_stop:
                failed_mode = self._process_mode
                self._process = None
                self._process_mode = None
                self._last_preview_heartbeat = None
                if failed_mode == "recording":
                    self._active_path = None
                    self._active_started_wall = None
                self._state = "error"
                self._last_error = (
                    self._last_error or f"FFmpeg {failed_mode} process exited ({returncode})"
                )
        if expired_heartbeat is not None:
            # A recording transition may win the lock after the timeout check.
            with suppress(CaptureConflict):
                self.stop_preview(idle_heartbeat=expired_heartbeat)

    def _monitor(self) -> None:
        while not self._shutdown:
            time.sleep(0.5)
            self._monitor_once()

    def status(self) -> dict[str, Any]:
        with self._lock:
            process_alive = self._process is not None and self._process.poll() is None
            elapsed = 0.0
            if self._active_started_wall:
                elapsed = max(0.0, time.time() - self._active_started_wall)
            if self._active_path and isinstance(
                self._progress.get("elapsed_seconds"), (int, float)
            ):
                elapsed = max(elapsed, float(self._progress["elapsed_seconds"]))
            size = 0
            if self._active_path and self._active_path.exists():
                with suppress(OSError):
                    size = self._active_path.stat().st_size
                progress_size = self._progress.get("total_size")
                if isinstance(progress_size, (int, float)):
                    size = max(size, int(progress_size))
            preview_idle_remaining: float | None = None
            if self._process_mode == "preview" and self._last_preview_heartbeat is not None:
                preview_idle_remaining = max(
                    0.0,
                    self.settings.preview_idle_timeout_seconds
                    - (time.monotonic() - self._last_preview_heartbeat),
                )
            return {
                "state": self._state,
                "mode": self._process_mode,
                "process_alive": process_alive,
                "preview_available": process_alive
                and self._process_mode in {"preview", "recording"},
                "recording": self._state in {"starting_recording", "recording", "stopping"}
                and self._active_path is not None,
                "elapsed_seconds": elapsed,
                "filename": self._active_path.name if self._active_path else None,
                "file_size_bytes": size,
                "video_device": "synthetic test source"
                if self.settings.synthetic_input
                else self.settings.video_device,
                "audio_device": "synthetic sine source"
                if self.settings.synthetic_input
                else self.settings.audio_device,
                "last_error": self._last_error,
                "last_completed": self._last_completed,
                "last_qc_status": self._last_qc_status,
                "preview_idle_timeout_seconds": self.settings.preview_idle_timeout_seconds,
                "preview_idle_remaining_seconds": preview_idle_remaining,
                "progress": dict(self._progress),
            }

    def shutdown(self) -> None:
        with self._lock:
            self._shutdown = True
            recording = self._active_path is not None and self._state in {
                "recording",
                "starting_recording",
                "stopping",
            }
            process = self._process
            self._expected_stop = process is not None
        if recording:
            try:
                self.stop_recording()
            except InvalidState:
                self._logger.exception("recording could not be finalized during shutdown")
        elif process is not None:
            self._stop_process(process)
            with self._lock:
                if self._process is process:
                    self._process = None
                    self._process_mode = None
                self._state = "idle"
                self._last_preview_heartbeat = None
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
