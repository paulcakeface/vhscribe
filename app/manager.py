from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from .config import Settings
from .ffmpeg import ProgressParser, build_preview_command, build_record_command
from .recordings import RecordingCatalog, final_path_for, probe_media, unique_partial_path


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
        self._restart_at: float | None = None
        self._monitor_thread: threading.Thread | None = None
        self._reader_threads: list[threading.Thread] = []
        self._state = "initialising"
        self._active_path: Path | None = None
        self._active_started_wall: float | None = None
        self._progress: dict[str, object] = {}
        self._last_error: str | None = None
        self._last_completed: str | None = None
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
        if self.settings.auto_preview:
            self.start_preview()
        else:
            with self._lock:
                self._state = "preview_available"

    def _safe_error(self, message: str) -> str:
        message = " ".join(message.strip().split())
        message = message.replace(str(self.settings.capture_dir), "capture storage")
        message = message.replace(self.settings.preview_rtsp_url, "preview service")
        return message[-500:] or "FFmpeg exited unexpectedly"

    def _log_stderr(self, process: subprocess.Popen[str], mode: str) -> None:
        if process.stderr is None:
            return
        recent: list[str] = []
        for line in process.stderr:
            cleaned = line.rstrip()
            if cleaned:
                self._logger.warning("[%s] %s", mode, cleaned)
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

    def start_preview(self) -> None:
        with self._lock:
            if self._shutdown or self._process is not None:
                return
            self._state = "initialising"
            try:
                self._launch(build_preview_command(self.settings), "preview")
                self._restart_at = None
            except OSError as exc:
                self._state = "error"
                self._last_error = self._safe_error(str(exc))
                self._restart_at = time.monotonic() + self.settings.preview_restart_seconds

    def restart_preview(self) -> None:
        with self._lock:
            if self._state in {"recording", "starting_recording", "stopping"}:
                raise CaptureConflict("preview cannot restart during a recording transition")
            process = self._process
            self._expected_stop = process is not None
            self._state = "initialising"
        if process is not None:
            self._stop_process(process)
        with self._lock:
            if self._process is process:
                self._process = None
                self._process_mode = None
            self._expected_stop = False
        self.start_preview()

    def start_recording(self, name: str) -> Path:
        with self._lock:
            if self._state in {"recording", "starting_recording", "stopping"} or self._active_path:
                raise CaptureConflict("a recording is already active or changing state")
            process = self._process
            self._expected_stop = process is not None
            self._state = "starting_recording"
            self._last_error = None
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
                self._restart_at = time.monotonic() + self.settings.preview_restart_seconds
                raise InvalidState("FFmpeg could not start") from exc
            self._active_path = output
            self._active_started_wall = time.time()
            self._process = launched
            self._expected_stop = False
            return output

    def _validate_and_finalize(self, partial: Path) -> Path:
        if not partial.exists() or partial.stat().st_size <= 0:
            raise ValueError("recording did not produce a non-empty file")
        data = probe_media(self.settings.ffprobe_bin, partial)
        stream_types = {stream.get("codec_type") for stream in data.get("streams", [])}
        if not {"video", "audio"}.issubset(stream_types):
            raise ValueError("recording does not contain both video and audio")
        final = final_path_for(partial)
        if final.exists():
            raise FileExistsError("final recording filename already exists")
        os.rename(partial, final)
        return final

    def stop_recording(self, *, restart_preview: bool = True) -> Path:
        with self._lock:
            if self._state not in {"recording", "starting_recording"} or not self._active_path:
                raise InvalidState("no recording is active")
            process = self._process
            partial = self._active_path
            self._state = "stopping"
            self._expected_stop = True
        if process is not None:
            self._stop_process(process)
        final: Path | None = None
        error: Exception | None = None
        try:
            final = self._validate_and_finalize(partial)
        except Exception as exc:  # The partial is deliberately retained on every failure.
            error = exc
        with self._lock:
            if self._process is process:
                self._process = None
                self._process_mode = None
            self._active_path = None
            self._active_started_wall = None
            self._progress = {}
            self._expected_stop = False
            if error:
                self._state = "error"
                self._last_error = self._safe_error(str(error))
            else:
                self._last_completed = final.name if final else None
                self._state = (
                    "initialising"
                    if restart_preview and not self._shutdown
                    else "preview_available"
                )
        if restart_preview and not self._shutdown:
            self.start_preview()
        if error:
            raise InvalidState(str(error)) from error
        assert final is not None
        return final

    def _monitor(self) -> None:
        while not self._shutdown:
            time.sleep(0.5)
            should_restart = False
            with self._lock:
                process = self._process
                if process is not None:
                    returncode = process.poll()
                    if returncode is None:
                        if time.monotonic() - self._process_started >= 1:
                            if self._process_mode == "preview" and self._state == "initialising":
                                self._state = "preview_available"
                            elif (
                                self._process_mode == "recording"
                                and self._state == "starting_recording"
                            ):
                                self._state = "recording"
                        continue
                    if self._expected_stop:
                        continue
                    failed_mode = self._process_mode
                    self._process = None
                    self._process_mode = None
                    if failed_mode == "recording":
                        self._active_path = None
                        self._active_started_wall = None
                    self._state = "error"
                    self._last_error = (
                        self._last_error or f"FFmpeg {failed_mode} process exited ({returncode})"
                    )
                    self._restart_at = time.monotonic() + self.settings.preview_restart_seconds
                if (
                    self._process is None
                    and self.settings.auto_preview
                    and self._restart_at is not None
                    and time.monotonic() >= self._restart_at
                ):
                    should_restart = True
                    self._restart_at = None
            if should_restart:
                self.start_preview()

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
                self.stop_recording(restart_preview=False)
            except InvalidState:
                self._logger.exception("recording could not be finalized during shutdown")
        elif process is not None:
            self._stop_process(process)
            with self._lock:
                if self._process is process:
                    self._process = None
                    self._process_mode = None
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
