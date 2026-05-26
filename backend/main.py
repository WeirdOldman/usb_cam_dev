from __future__ import annotations

import queue
import random
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import os

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from usb_cam_capture import build_extract_cmd
from usb_cam_capture_context import CaptureContext
from usb_cam_capture_helpers import (
    close_capture_resources,
    execute_capture_pipeline,
    finalize_capture_summary,
    handle_capture_exception,
    log_capture_command,
    log_capture_exit_code,
    update_capture_timer_tick,
)
from usb_cam_capture_state import CaptureState
from usb_cam_paths import app_base_dir, find_ffmpeg, safe_image_prefix
from usb_cam_preview import build_preview_cmd, read_preview_frames, start_preview_process, stop_preview_process
from usb_cam_process import (
    parse_ffmpeg_progress_line,
    request_stop_process,
    run_ffmpeg_process,
    windows_popen_kwargs,
)
from usb_cam_runtime import build_capture_meta
from usb_cam_session_finalize import finalize_session
from usb_cam_session_writer import count_frame_files, make_session, write_metadata, write_summary
from usb_cam_stop_prefs import default_auto_stop_prefs
from usb_cam_ui_state import update_capture_metrics


API_HOST = "127.0.0.1"
API_PORT = 8000
FRONTEND_DEV_URL = "http://localhost:5173"
FRONTEND_DIST_DIR = PROJECT_ROOT / "ui_dist"
RUNTIME_LOG_PATH = PROJECT_ROOT / "webview_runtime.log"
MJPEG_PATH = "/api/video/mjpeg"
WS_PATH = "/ws/monitor"
CONTROL_START_PATH = "/api/control/start"
CONTROL_STOP_PATH = "/api/control/stop"
CONFIG_PATH = "/api/config"
SELECT_OUTPUT_DIR_PATH = "/api/dialog/select-output-dir"
WINDOW_MINIMIZE_PATH = "/api/window/minimize"
WINDOW_TOGGLE_MAXIMIZE_PATH = "/api/window/toggle-maximize"
WINDOW_CLOSE_PATH = "/api/window/close"
OPEN_OUTPUT_DIR_PATH = "/api/system/open-output-dir"
FFMPEG_STATUS_PATH = "/api/system/ffmpeg-status"
PREVIEW_START_PATH = "/api/preview/start"
PREVIEW_STOP_PATH = "/api/preview/stop"
EVENTS_PATH = "/api/events"
CAMERA_DEVICES_PATH = "/api/devices/cameras"
MONITOR_PATH = "/api/monitor"
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FRAME_FPS = 10
APP_NAME = "usb_cam_pywebview_demo"
WIDTH = 3840
HEIGHT = 2160
FPS = 25
DEFAULT_CAMERA_NAME = "imx678' UVC "
MAX_LOG_BYTES = 10 * 1024 * 1024
PREVIEW_WIDTH = 640
PREVIEW_FPS = 5


class StartCaptureRequest(BaseModel):
    mode: str = "direct_frames"
    output_dir: str | None = None
    image_prefix: str = "img"
    quality_mode: str = "copy"
    delete_video_after_extract: bool = False
    camera_name: str = DEFAULT_CAMERA_NAME


class UpdateConfigRequest(BaseModel):
    camera_name: str | None = None
    output_dir: str | None = None
    image_prefix: str | None = None
    mode: str | None = None
    quality_mode: str | None = None
    delete_video_after_extract: bool | None = None


class SelectOutputDirRequest(BaseModel):
    current_dir: str | None = None


class RuntimeConfigResponse(BaseModel):
    camera_name: str
    output_dir: str
    image_prefix: str
    mode: str
    quality_mode: str
    delete_video_after_extract: bool
    ffmpeg_path: str
    base_dir: str
    frontend_dev_url: str
    api_base_url: str
    mjpeg_url: str
    websocket_url: str
    control_start_url: str
    control_stop_url: str
    auto_stop: dict


class LimitedLogWriter:
    def __init__(self, path: Path, max_bytes: int = MAX_LOG_BYTES):
        self.path = path
        self.max_bytes = max_bytes
        self.written = 0
        self.truncated = False
        self.fp = open(path, "ab")

    def write(self, text: str):
        if self.truncated:
            return
        data = text.encode("utf-8", errors="replace")
        if self.written + len(data) > self.max_bytes:
            remain = max(0, self.max_bytes - self.written)
            if remain > 0:
                self.fp.write(data[:remain])
                self.written += remain
            marker = "\n\n[LOG TRUNCATED: run_log.txt reached 10MB limit]\n"
            self.fp.write(marker.encode("utf-8"))
            self.truncated = True
        else:
            self.fp.write(data)
            self.written += len(data)
        self.fp.flush()

    def close(self):
        self.fp.close()


@dataclass
class BackendRuntime:
    base_dir: Path
    camera_name: str = DEFAULT_CAMERA_NAME
    image_prefix: str = "img"
    mode: str = "direct_frames"
    quality_mode: str = "copy"
    delete_video_after_extract: bool = False
    ffmpeg_path: str | None = None
    output_dir: Path | None = None
    proc: object | None = None
    worker: threading.Thread | None = None
    preview_proc: object | None = None
    preview_worker: threading.Thread | None = None
    preview_lock: threading.Lock = field(default_factory=threading.Lock)
    latest_preview_frame: bytes | None = None
    preview_enabled: bool = True
    capture_context: CaptureContext = field(default_factory=CaptureContext)
    capture_state: CaptureState = field(default_factory=CaptureState)
    monitor_lock: threading.Lock = field(default_factory=threading.Lock)
    control_lock: threading.Lock = field(default_factory=threading.Lock)
    event_lock: threading.Lock = field(default_factory=threading.Lock)
    last_monitor_payload: dict | None = None
    event_log: list[dict] = field(default_factory=list)
    capture_phase: str = "idle"
    capture_last_error: str | None = None
    capture_last_error_reason: str | None = None
    capture_last_error_code: int | None = None
    capture_last_session_dir: str | None = None

    def __post_init__(self):
        self.output_dir = self.base_dir / "capture_output"
        self.ffmpeg_path = find_ffmpeg() or ""
        self.append_event("system", "System initialized.")
        self.last_monitor_payload = self.build_monitor_payload()

    def append_event(self, kind: str, message: str):
        event = {
            "kind": kind,
            "message": message,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        with self.event_lock:
            self.event_log.append(event)
            if len(self.event_log) > 60:
                self.event_log = self.event_log[-60:]

    def clear_capture_error(self) -> None:
        self.capture_last_error = None
        self.capture_last_error_reason = None
        self.capture_last_error_code = None

    def update_capture_outcome_meta(
        self,
        *,
        result: str,
        phase: str,
        reason: str | None = None,
        message: str | None = None,
        code: int | None = None,
    ) -> None:
        if not self.capture_context.current_meta:
            return
        meta = self.capture_context.current_meta
        meta["capture_result"] = result
        meta["capture_phase"] = phase
        if result == "failed":
            meta["capture_failure_reason"] = reason
            meta["capture_failure_message"] = message
            meta["capture_failure_code"] = code
        else:
            meta.pop("capture_failure_reason", None)
            meta.pop("capture_failure_message", None)
            meta.pop("capture_failure_code", None)

    def persist_capture_session_outputs(self) -> None:
        session_dir = self.capture_context.current_session
        if session_dir is None or not self.capture_context.current_meta:
            return
        try:
            write_metadata(session_dir, self.capture_context.current_meta)
        except Exception as exc:
            if self.capture_context.log_writer:
                self.capture_context.log_writer.write(f"\n[metadata rewrite failed] {exc}\n")
        try:
            write_summary(session_dir, self.capture_context.current_meta)
        except Exception as exc:
            if self.capture_context.log_writer:
                self.capture_context.log_writer.write(f"\n[summary rewrite failed] {exc}\n")

    def idle_status_text(self, status_override: str | None = None) -> str:
        if self.capture_last_error:
            return self.capture_last_error
        if status_override:
            return status_override
        return "Stopped"

    def record_capture_error(
        self,
        *,
        reason: str,
        message: str,
        code: int | None = None,
        session_dir: str | None = None,
    ) -> None:
        self.capture_last_error_reason = reason
        self.capture_last_error = message
        self.capture_last_error_code = code
        if session_dir:
            self.capture_last_session_dir = session_dir
        self.capture_phase = "failed"
        self.update_capture_outcome_meta(
            result="failed",
            phase="failed",
            reason=reason,
            message=message,
            code=code,
        )
        self.persist_capture_session_outputs()
        with self.monitor_lock:
            self.last_monitor_payload = None
        self.append_event("capture", message)

    def mark_capture_completed(self, *, frame_count: int, session_dir: str | None = None) -> str:
        self.clear_capture_error()
        self.capture_phase = "idle"
        if session_dir:
            self.capture_last_session_dir = session_dir
        self.update_capture_outcome_meta(result="succeeded", phase="idle")
        self.persist_capture_session_outputs()
        with self.monitor_lock:
            self.last_monitor_payload = None
        message = f"Capture completed: {frame_count} frames."
        self.append_event("capture", message)
        return message

    def capture_phase_payload(self) -> str:
        if self.capture_state.capture_running:
            if self.capture_phase in {"starting", "stopping"}:
                return self.capture_phase
            return "running"
        if self.capture_last_error_reason:
            return "failed"
        return "idle"

    def recent_events(self):
        with self.event_lock:
            return list(self.event_log)

    def control_config(self) -> dict:
        api_base_url = f"http://{API_HOST}:{API_PORT}"
        return {
            "camera_name": self.camera_name,
            "output_dir": str(self.output_dir),
            "image_prefix": self.image_prefix,
            "mode": self.mode,
            "quality_mode": self.quality_mode,
            "delete_video_after_extract": self.delete_video_after_extract,
            "ffmpeg_path": self.ffmpeg_path or "",
            "base_dir": str(self.base_dir),
            "frontend_dev_url": FRONTEND_DEV_URL,
            "api_base_url": api_base_url,
            "mjpeg_url": f"{api_base_url}{MJPEG_PATH}",
            "websocket_url": f"ws://{API_HOST}:{API_PORT}{WS_PATH}",
            "control_start_url": f"{api_base_url}{CONTROL_START_PATH}",
            "control_stop_url": f"{api_base_url}{CONTROL_STOP_PATH}",
            "preview_start_url": f"{api_base_url}{PREVIEW_START_PATH}",
            "preview_stop_url": f"{api_base_url}{PREVIEW_STOP_PATH}",
            "auto_stop": default_auto_stop_prefs(),
        }

    def update_control_settings(self, request: StartCaptureRequest):
        self.camera_name = request.camera_name
        self.image_prefix = request.image_prefix or "img"
        self.mode = request.mode
        self.quality_mode = request.quality_mode
        self.delete_video_after_extract = bool(request.delete_video_after_extract)
        self.output_dir = Path(request.output_dir) if request.output_dir else self.base_dir / "capture_output"
        self.ffmpeg_path = find_ffmpeg() or ""

    def apply_config_update(self, request: UpdateConfigRequest):
        if request.camera_name is not None:
            self.camera_name = request.camera_name
        if request.image_prefix is not None:
            self.image_prefix = request.image_prefix or "img"
        if request.mode is not None:
            self.mode = request.mode
        if request.quality_mode is not None:
            self.quality_mode = request.quality_mode
        if request.delete_video_after_extract is not None:
            self.delete_video_after_extract = bool(request.delete_video_after_extract)
        if request.output_dir is not None:
            self.output_dir = Path(request.output_dir) if request.output_dir else self.base_dir / "capture_output"
        self.ffmpeg_path = find_ffmpeg() or ""

    def prepare_capture_session(self):
        assert self.output_dir is not None
        current_session, current_frames_dir, current_video_dir = make_session(
            str(self.output_dir),
            "direct_frames_mjpeg_4k" if self.mode == "direct_frames" else "video_then_frames_mjpeg_4k",
        )
        self.capture_context.assign_session_paths(current_session, current_frames_dir, current_video_dir)
        log_path = current_session / "run_log.txt"
        self.capture_context.set_log_writer(LimitedLogWriter(log_path, MAX_LOG_BYTES))
        self.capture_context.set_meta(
            build_capture_meta(
                app_name=APP_NAME,
                created_at=datetime.now().isoformat(timespec="seconds"),
                camera_name=self.camera_name,
                mode=self.mode,
                quality_mode=self.quality_mode,
                width=WIDTH,
                height=HEIGHT,
                fps=FPS,
                image_prefix=safe_image_prefix(self.image_prefix),
                ffmpeg=self.ffmpeg_path or "",
                session_dir=current_session,
                frames_dir=current_frames_dir,
                run_log_path=log_path,
                run_log_max_bytes=MAX_LOG_BYTES,
                delete_video_after_extract=self.delete_video_after_extract,
                manual_start_time=datetime.now().isoformat(timespec="seconds"),
            )
        )
        self.capture_state.start_time = time.time()
        self.capture_state.reset_for_capture()
        self.capture_last_session_dir = str(current_session)
        return log_path

    def prepare_preview_cmd(self, ffmpeg: str):
        return build_preview_cmd(
            ffmpeg=ffmpeg,
            camera_name=self.camera_name,
            width=WIDTH,
            height=HEIGHT,
            fps=FPS,
            preview_fps=PREVIEW_FPS,
            preview_width=PREVIEW_WIDTH,
        )

    def preview_reader(self):
        proc = self.preview_proc
        if proc is None or getattr(proc, "stdout", None) is None:
            return
        try:
            read_preview_frames(proc.stdout, self.set_latest_preview_frame)
        finally:
            with self.preview_lock:
                self.preview_proc = None
                self.preview_worker = None

    def set_latest_preview_frame(self, frame_bytes: bytes):
        self.latest_preview_frame = frame_bytes

    def preview_frame_to_jpeg(self, frame_bytes: bytes) -> bytes | None:
        import cv2
        import numpy as np

        decoded = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if decoded is None:
            return None
        ok, encoded = cv2.imencode(".jpg", decoded)
        if not ok:
            return None
        return encoded.tobytes()

    def ensure_preview_running(self):
        with self.preview_lock:
            if not self.preview_enabled:
                return
            current = self.preview_proc
            if current is not None and getattr(current, "poll", lambda: None)() is None:
                return
            ffmpeg = find_ffmpeg() or ""
            if not ffmpeg:
                raise RuntimeError("FFmpeg not found for preview")
            cmd = self.prepare_preview_cmd(ffmpeg)
            self.preview_proc = start_preview_process(ffmpeg, cmd)
            self.preview_worker = threading.Thread(target=self.preview_reader, daemon=True)
            self.preview_worker.start()

    def stop_preview(self, wait: bool = False):
        with self.preview_lock:
            proc = self.preview_proc
            if proc is None:
                return
            stop_preview_process(proc, wait=wait)
            self.preview_proc = None
            self.preview_worker = None

    def iter_preview_mjpeg_chunks(self):
        while True:
            if self.preview_enabled and not self.capture_state.capture_running and self.preview_proc is None:
                self.ensure_preview_running()
            frame = self.latest_preview_frame
            if frame:
                jpeg_payload = self.preview_frame_to_jpeg(frame)
                if jpeg_payload is None:
                    time.sleep(1.0 / PREVIEW_FPS)
                    continue
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + jpeg_payload
                    + b"\r\n"
                )
            time.sleep(1.0 / PREVIEW_FPS)

    def build_direct_cmd(self, ffmpeg: str):
        assert self.capture_context.current_frames_dir is not None
        output_pattern = self.capture_context.current_frames_dir / f"{safe_image_prefix(self.image_prefix)}_%06d.jpg"
        quality_args = ["-c:v", "copy", "-f", "image2"] if self.quality_mode == "copy" else ["-q:v", "2"]
        return [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-stats_period",
            "0.5",
            "-progress",
            "pipe:2",
            "-f",
            "dshow",
            "-video_size",
            f"{WIDTH}x{HEIGHT}",
            "-framerate",
            str(FPS),
            "-vcodec",
            "mjpeg",
            "-i",
            f"video={self.camera_name}",
            "-map",
            "0:v:0",
            *quality_args,
            str(output_pattern),
            "-map",
            "0:v:0",
            "-vf",
            f"fps={PREVIEW_FPS},scale={PREVIEW_WIDTH}:-1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "pipe:1",
        ]

    def build_record_cmd(self, ffmpeg: str, video_path: Path):
        return [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-stats_period",
            "0.5",
            "-progress",
            "pipe:2",
            "-f",
            "dshow",
            "-video_size",
            f"{WIDTH}x{HEIGHT}",
            "-framerate",
            str(FPS),
            "-vcodec",
            "mjpeg",
            "-i",
            f"video={self.camera_name}",
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            str(video_path),
            "-map",
            "0:v:0",
            "-vf",
            f"fps={PREVIEW_FPS},scale={PREVIEW_WIDTH}:-1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "pipe:1",
        ]

    def build_extract_cmd(self, ffmpeg: str, video_path: Path, fallback_q2: bool = False):
        assert self.capture_context.current_frames_dir is not None
        return build_extract_cmd(
            ffmpeg=ffmpeg,
            video_path=video_path,
            output_dir=self.capture_context.current_frames_dir,
            image_prefix=safe_image_prefix(self.image_prefix),
            fallback_q2=fallback_q2,
        )

    def execute_ffmpeg_command(self, cmd: list[str]):
        if "image2pipe" in cmd and "pipe:2" in cmd:
            return self.execute_capture_preview_command(cmd)
        proc, code = run_ffmpeg_process(
            cmd,
            fps=FPS,
            log_write=self.capture_context.log_writer.write if self.capture_context.log_writer else None,
            frame_callback=lambda frame: setattr(self.capture_state, "last_ffmpeg_frame", frame),
            started_callback=lambda proc: (setattr(self, "proc", proc), setattr(self, "capture_phase", "running")),
        )
        return proc, code

    def execute_capture_preview_command(self, cmd: list[str]):
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **windows_popen_kwargs(),
        )
        self.proc = proc
        self.capture_phase = "running"

        preview_thread = None
        if proc.stdout is not None:
            preview_thread = threading.Thread(
                target=read_preview_frames,
                args=(proc.stdout, self.set_latest_preview_frame),
                daemon=True,
            )
            preview_thread.start()

        last_frame = 0
        if proc.stderr is not None:
            for raw_line in proc.stderr:
                line = raw_line.decode("utf-8", errors="replace")
                if self.capture_context.log_writer:
                    self.capture_context.log_writer.write(line)
                parsed = parse_ffmpeg_progress_line(line, FPS)
                if parsed is not None:
                    last_frame = max(last_frame, parsed)
                    self.capture_state.last_ffmpeg_frame = last_frame

        code = proc.wait()
        if preview_thread is not None:
            preview_thread.join(timeout=1.0)
        return proc, code

    def run_process(self, cmd: list[str], label: str, allow_manual_stop: bool = True):
        log_capture_command(self.capture_context.current_meta, self.capture_context.log_writer, cmd, label)
        _proc, code = self.execute_ffmpeg_command(cmd)
        log_capture_exit_code(self.capture_context.log_writer, label, code)
        self.proc = None
        return code

    def finish_session(self):
        assert self.capture_context.current_session is not None
        assert self.capture_context.current_frames_dir is not None
        result = finalize_session(
            current_session=self.capture_context.current_session,
            current_frames_dir=self.capture_context.current_frames_dir,
            current_meta=self.capture_context.current_meta,
            start_time=self.capture_state.start_time,
        )
        finalize_capture_summary(self.capture_context, result)
        return result

    def classify_capture_failure(self, *, result: dict | None = None, exc: Exception | None = None) -> tuple[str, str, int | None]:
        if not self.ffmpeg_path:
            return "ffmpeg_missing", "FFmpeg not found.", None

        if exc is not None:
            return "runtime_exception", f"Capture runtime exception: {exc}", None

        meta = result.get("current_meta", {}) if result else self.capture_context.current_meta
        session_dir = self.capture_context.current_session
        if result and result.get("current_meta", {}).get("session_dir"):
            session_dir = Path(result["current_meta"]["session_dir"])
        log_path = None
        if isinstance(meta.get("run_log_path"), str):
            log_path = Path(meta["run_log_path"])
        elif session_dir is not None:
            log_path = session_dir / "run_log.txt"

        log_text = ""
        if log_path and log_path.exists():
            try:
                log_text = log_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                log_text = ""

        last_code = None
        exit_codes = meta.get("exit_codes") or []
        for item in reversed(exit_codes):
            if isinstance(item, dict) and item:
                value = next(iter(item.values()))
                if isinstance(value, int):
                    last_code = value
                    break

        lowered = log_text.lower()
        if "device already in use" in lowered:
            return "camera_in_use", "Camera is already in use by another application.", last_code

        invalid_match = re.search(r"could not find video device with name \[(.+?)\]", log_text, re.IGNORECASE)
        if invalid_match:
            return "camera_invalid", f"Selected camera could not be opened: {invalid_match.group(1)}.", last_code
        if "error opening input file video=" in lowered:
            camera_name = meta.get("camera_name") or self.camera_name
            return "camera_invalid", f"Selected camera input could not be opened: {camera_name}.", last_code

        frame_count = None
        if result is not None:
            frame_count = result.get("frame_count")
        if frame_count == 0:
            return "capture_no_frames", "Capture completed without producing frames.", last_code
        return "capture_failed", f"Capture process exited unexpectedly with code {last_code}.", last_code

    def worker_capture(self):
        ffmpeg = self.capture_context.current_meta["ffmpeg"]
        status_override = "Capture completed."
        try:
            execute_capture_pipeline(
                mode=self.mode,
                ffmpeg=ffmpeg,
                current_video_dir=self.capture_context.current_video_dir,
                current_frames_dir=self.capture_context.current_frames_dir,
                delete_video_after_extract=self.delete_video_after_extract,
                current_meta=self.capture_context.current_meta,
                run_process=self.run_process,
                build_direct_cmd=self.build_direct_cmd,
                build_record_cmd=self.build_record_cmd,
                build_extract_cmd=self.build_extract_cmd,
            )
            result = self.finish_session()
            if (result.get("frame_count") or 0) <= 0:
                reason, message, code = self.classify_capture_failure(result=result)
                self.record_capture_error(
                    reason=reason,
                    message=message,
                    code=code,
                    session_dir=str(self.capture_context.current_session) if self.capture_context.current_session else None,
                )
                status_override = message
            else:
                status_override = self.mark_capture_completed(
                    frame_count=result["frame_count"],
                    session_dir=str(self.capture_context.current_session) if self.capture_context.current_session else None,
                )
        except Exception as exc:
            handle_capture_exception(self.capture_context.log_writer, DummyStatusSetter(self), exc)
            if self.capture_context.current_session is not None and self.capture_context.current_frames_dir is not None:
                try:
                    self.finish_session()
                except Exception as finalize_exc:
                    if self.capture_context.log_writer:
                        self.capture_context.log_writer.write(f"\n[finalize after exception failed] {finalize_exc}\n")
            reason, message, code = self.classify_capture_failure(exc=exc)
            self.record_capture_error(
                reason=reason,
                message=message,
                code=code,
                session_dir=str(self.capture_context.current_session) if self.capture_context.current_session else None,
            )
            status_override = message
        finally:
            close_capture_resources(
                self.capture_context.log_writer,
                self.capture_context.clear_log_writer,
                queue.Queue(),
            )
            self.capture_state.capture_running = False
            self.proc = None
            if self.capture_phase != "failed":
                self.capture_phase = "idle"
            self.refresh_monitor_payload(status_override=status_override)

    def start_capture(self, request: StartCaptureRequest):
        with self.control_lock:
            if self.capture_state.capture_running:
                return {"ok": False, "running": True, "status_text": "Capture already running."}

            self.update_control_settings(request)
            if not self.ffmpeg_path:
                self.record_capture_error(reason="ffmpeg_missing", message="FFmpeg not found.")
                self.refresh_monitor_payload(status_override="FFmpeg not found.")
                return {
                    "ok": False,
                    "running": False,
                    "status_text": "FFmpeg not found.",
                    "capture_last_error": self.capture_last_error,
                    "capture_last_error_reason": self.capture_last_error_reason,
                    "capture_last_error_code": self.capture_last_error_code,
                    "capture_last_session_dir": self.capture_last_session_dir,
                }
            if self.preview_proc is not None:
                self.stop_preview(wait=True)

            self.clear_capture_error()
            self.prepare_capture_session()
            self.capture_state.capture_running = True
            self.capture_phase = "starting"
            self.worker = threading.Thread(target=self.worker_capture, daemon=True)
            self.worker.start()
            self.append_event("capture", "Starting pipeline...")
            self.refresh_monitor_payload(status_override="Starting pipeline...")
            return {
                "ok": True,
                "running": True,
                "capture_phase": self.capture_phase_payload(),
                "capture_last_error": self.capture_last_error,
                "capture_last_error_reason": self.capture_last_error_reason,
                "capture_last_error_code": self.capture_last_error_code,
                "capture_last_session_dir": self.capture_last_session_dir,
                "status_text": "Starting pipeline...",
                "config": self.control_config(),
            }

    def stop_capture(self):
        with self.control_lock:
            if not self.capture_state.capture_running:
                self.refresh_monitor_payload()
                return {
                    "ok": False,
                    "running": False,
                    "capture_phase": self.capture_phase_payload(),
                    "capture_last_error": self.capture_last_error,
                    "capture_last_error_reason": self.capture_last_error_reason,
                    "capture_last_error_code": self.capture_last_error_code,
                    "capture_last_session_dir": self.capture_last_session_dir,
                    "status_text": self.idle_status_text(),
                }
            if self.proc is not None:
                request_stop_process(self.proc)
            self.capture_phase = "stopping"
            self.append_event("capture", "Stopping capture...")
            self.refresh_monitor_payload(status_override="Stopping capture...")
            return {
                "ok": True,
                "running": self.capture_state.capture_running,
                "capture_phase": self.capture_phase_payload(),
                "capture_last_error": self.capture_last_error,
                "capture_last_error_reason": self.capture_last_error_reason,
                "capture_last_error_code": self.capture_last_error_code,
                "capture_last_session_dir": self.capture_last_session_dir,
                "status_text": "Stopping capture...",
            }

    def preview_status_text(self) -> str:
        if self.capture_state.capture_running:
            return "Preview sourced from capture pipeline."
        if not self.preview_enabled:
            return "Preview stopped."
        if self.preview_proc is not None:
            return "Preview running."
        return "Preview ready."

    def ui_locks(self) -> dict:
        ffmpeg_missing = not bool(self.ffmpeg_path)
        capture_running = bool(self.capture_state.capture_running)
        return {
            "capture_start_disabled": ffmpeg_missing or capture_running,
            "capture_start_reason": "FFmpeg not found." if ffmpeg_missing else ("Capture already running." if capture_running else ""),
            "capture_stop_disabled": not capture_running,
            "capture_stop_reason": "" if capture_running else "Capture is not running.",
            "preview_toggle_disabled": capture_running,
            "preview_toggle_reason": "Preview control is locked while capture is running." if capture_running else "",
            "path_edit_disabled": capture_running,
            "path_edit_reason": "Path parameters are locked while capture is running." if capture_running else "",
            "config_save_disabled": capture_running,
            "config_save_reason": "Runtime config cannot be saved while capture is running." if capture_running else "",
            "camera_select_disabled": capture_running,
            "camera_select_reason": "Camera input cannot change while capture is running." if capture_running else "",
        }

    def refresh_monitor_payload(self, status_override: str | None = None):
        now = time.time()
        if self.capture_state.capture_running and self.capture_context.current_session is not None:
            metrics = update_capture_timer_tick(
                capture_state=self.capture_state,
                capture_context=self.capture_context,
                now=now,
                fps=FPS,
                update_capture_metrics_fn=update_capture_metrics,
                log_writer=self.capture_context.log_writer,
                auto_stop_prefs=default_auto_stop_prefs(),
            )
            capture_fps_text = metrics.get("capture_fps_text", "-- fps")
            fps_value = float(capture_fps_text.split()[0]) if capture_fps_text not in {"-- fps", None} else 0.0
            status_text = status_override or metrics.get("capture_health_reason", "Running")
            payload = {
                "running": True,
                "capture_phase": self.capture_phase_payload(),
                "runtime_seconds": int(max(0, now - self.capture_state.start_time)),
                "fps": fps_value,
                "cpu_percent": random.randint(35, 50),
                "processed_frames": int(metrics.get("display_count", 0)),
                "acceleration": "CUDA Active",
                "bitrate_mbps": round(random.uniform(4.2, 4.8), 1),
                "resolution": f"{WIDTH}x{HEIGHT}",
                "status_text": status_text,
                "capture_last_error": self.capture_last_error,
                "capture_last_error_reason": self.capture_last_error_reason,
                "capture_last_error_code": self.capture_last_error_code,
                "capture_last_session_dir": self.capture_last_session_dir,
                "preview_enabled": self.preview_enabled,
                "preview_active": True,
                "preview_status": self.preview_status_text(),
                "ui_locks": self.ui_locks(),
                "events": self.recent_events(),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "config": self.control_config(),
            }
        else:
            payload = self.build_monitor_payload()
            payload["status_text"] = self.idle_status_text(status_override)

        with self.monitor_lock:
            self.last_monitor_payload = payload

    def build_monitor_payload(self):
        return {
            "running": False,
            "capture_phase": self.capture_phase_payload(),
            "runtime_seconds": 0,
            "fps": 0.0,
            "cpu_percent": 2,
            "processed_frames": 0,
            "acceleration": "Idle",
            "bitrate_mbps": 0.0,
            "resolution": f"{WIDTH}x{HEIGHT}",
            "status_text": self.idle_status_text(),
            "capture_last_error": self.capture_last_error,
            "capture_last_error_reason": self.capture_last_error_reason,
            "capture_last_error_code": self.capture_last_error_code,
            "capture_last_session_dir": self.capture_last_session_dir,
            "preview_enabled": self.preview_enabled,
            "preview_active": self.preview_proc is not None and getattr(self.preview_proc, "poll", lambda: None)() is None,
            "preview_status": self.preview_status_text(),
            "ui_locks": self.ui_locks(),
            "events": self.recent_events(),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "config": self.control_config(),
        }

    def snapshot(self):
        if self.capture_state.capture_running:
            self.refresh_monitor_payload()
        elif (
            self.last_monitor_payload is None
            or self.capture_last_error_reason
            or bool((self.last_monitor_payload or {}).get("running"))
        ):
            self.refresh_monitor_payload()
        with self.monitor_lock:
            return dict(self.last_monitor_payload or self.build_monitor_payload())


class DummyStatusSetter:
    def __init__(self, runtime: BackendRuntime):
        self.runtime = runtime

    def set(self, value: str):
        self.runtime.refresh_monitor_payload(status_override=value)


runtime_state = BackendRuntime(base_dir=Path(app_base_dir()))
webview_window = None


def validate_runtime_options(mode: str, quality_mode: str):
    if mode not in {"direct_frames", "video_then_frames"}:
        raise HTTPException(status_code=400, detail="Unsupported mode")
    if quality_mode not in {"copy", "q2"}:
        raise HTTPException(status_code=400, detail="Unsupported quality_mode")


def mjpeg_frame_generator():
    import cv2
    import numpy as np

    while True:
        frame = np.random.randint(
            0,
            256,
            (FRAME_HEIGHT, FRAME_WIDTH, 3),
            dtype=np.uint8,
        )
        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            time.sleep(1.0 / FRAME_FPS)
            continue

        payload = encoded.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + payload
            + b"\r\n"
        )
        time.sleep(1.0 / FRAME_FPS)


def open_directory_dialog(current_dir: str | None = None) -> str | None:
    if webview_window is None:
        raise RuntimeError("PyWebView window is not initialized")

    import webview

    initial_dir = current_dir or str(runtime_state.output_dir or runtime_state.base_dir)
    selected = webview_window.create_file_dialog(webview.FOLDER_DIALOG, directory=initial_dir)
    if not selected:
        return None
    if isinstance(selected, (list, tuple)):
        return str(selected[0]) if selected else None
    return str(selected)


def require_window():
    if webview_window is None:
        raise RuntimeError("PyWebView window is not initialized")
    return webview_window


def open_system_path(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        import os

        os.startfile(path)  # type: ignore[attr-defined]
        return
    raise RuntimeError("open_system_path currently only supports Windows")


def list_camera_devices(ffmpeg_path: str | None) -> list[str]:
    if not ffmpeg_path:
        return []

    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-list_devices",
        "true",
        "-f",
        "dshow",
        "-i",
        "dummy",
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        **windows_popen_kwargs(),
    )
    text = f"{proc.stdout}\n{proc.stderr}"
    devices: list[str] = []
    for line in text.splitlines():
        if '"' not in line:
            continue
        quoted = line.split('"')
        if len(quoted) < 2:
            continue
        name = quoted[1].strip()
        if name and name not in devices and "Alternative name" not in line:
            devices.append(name)
    return devices


def append_runtime_log(path: Path, message: str):
    timestamp = datetime.now().isoformat(timespec="seconds")
    with open(path, "a", encoding="utf-8", errors="replace") as fp:
        fp.write(f"[{timestamp}] {message}\n")


def resolve_frontend_target(frontend_dir: Path = FRONTEND_DIST_DIR, dev_url: str = FRONTEND_DEV_URL) -> str:
    candidates = [
        frontend_dir / "index.html",
        frontend_dir.parent / "_internal" / frontend_dir.name / "index.html",
    ]
    for index_file in candidates:
        if index_file.exists():
            return index_file.resolve().as_uri()
    return dev_url


def create_app() -> FastAPI:
    app = FastAPI(title="USB Cam 4K25 Demo Backend")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root():
        return {
            "status": "ok",
            "mjpeg_url": f"http://{API_HOST}:{API_PORT}{MJPEG_PATH}",
            "websocket_url": f"ws://{API_HOST}:{API_PORT}{WS_PATH}",
            "control_start_url": f"http://{API_HOST}:{API_PORT}{CONTROL_START_PATH}",
            "control_stop_url": f"http://{API_HOST}:{API_PORT}{CONTROL_STOP_PATH}",
            "config_url": f"http://{API_HOST}:{API_PORT}{CONFIG_PATH}",
        }

    @app.get(CONFIG_PATH, response_model=RuntimeConfigResponse)
    async def get_config():
        return RuntimeConfigResponse(**runtime_state.control_config())

    @app.put(CONFIG_PATH, response_model=RuntimeConfigResponse)
    async def update_config(request: UpdateConfigRequest):
        with runtime_state.control_lock:
            if runtime_state.capture_state.capture_running:
                raise HTTPException(status_code=409, detail="Cannot update config while capture is running")
            next_mode = request.mode if request.mode is not None else runtime_state.mode
            next_quality_mode = request.quality_mode if request.quality_mode is not None else runtime_state.quality_mode
            validate_runtime_options(next_mode, next_quality_mode)
            runtime_state.apply_config_update(request)
            runtime_state.refresh_monitor_payload()
            return RuntimeConfigResponse(**runtime_state.control_config())

    @app.post(SELECT_OUTPUT_DIR_PATH)
    async def select_output_dir(request: SelectOutputDirRequest):
        with runtime_state.control_lock:
            if runtime_state.capture_state.capture_running:
                raise HTTPException(status_code=409, detail="Cannot select output dir while capture is running")
            selected_dir = open_directory_dialog(request.current_dir)
            if not selected_dir:
                runtime_state.append_event("system", "Output directory selection cancelled.")
                return {"ok": False, "selected_dir": None, "config": runtime_state.control_config()}
            runtime_state.output_dir = Path(selected_dir)
            runtime_state.append_event("system", f"Output directory updated: {selected_dir}")
            runtime_state.refresh_monitor_payload(status_override="Output directory updated.")
            return {"ok": True, "selected_dir": selected_dir, "config": runtime_state.control_config()}

    @app.post(WINDOW_MINIMIZE_PATH)
    async def window_minimize():
        require_window().minimize()
        return {"ok": True}

    @app.post(WINDOW_TOGGLE_MAXIMIZE_PATH)
    async def window_toggle_maximize():
        window = require_window()
        if getattr(window, "state", None) == "maximized":
            window.restore()
        else:
            window.maximize()
        return {"ok": True}

    @app.post(WINDOW_CLOSE_PATH)
    async def window_close():
        require_window().destroy()
        return {"ok": True}

    @app.post(OPEN_OUTPUT_DIR_PATH)
    async def open_output_dir():
        open_system_path(str(runtime_state.output_dir))
        runtime_state.append_event("system", f"Opened output directory: {runtime_state.output_dir}")
        return {"ok": True, "path": str(runtime_state.output_dir)}

    @app.get(FFMPEG_STATUS_PATH)
    async def ffmpeg_status():
        ffmpeg = find_ffmpeg() or ""
        runtime_state.ffmpeg_path = ffmpeg
        runtime_state.append_event("system", "FFmpeg available." if ffmpeg else "FFmpeg not found.")
        runtime_state.refresh_monitor_payload(status_override="FFmpeg available." if ffmpeg else "FFmpeg not found.")
        return {"ok": True, "ffmpeg_found": bool(ffmpeg), "ffmpeg_path": ffmpeg}

    @app.get(CAMERA_DEVICES_PATH)
    async def camera_devices():
        ffmpeg = runtime_state.ffmpeg_path or find_ffmpeg() or ""
        runtime_state.ffmpeg_path = ffmpeg
        devices = list_camera_devices(ffmpeg)
        return {"ok": True, "devices": devices, "selected_device": runtime_state.camera_name}

    @app.post(PREVIEW_START_PATH)
    async def preview_start():
        runtime_state.preview_enabled = True
        if not runtime_state.capture_state.capture_running:
            runtime_state.ensure_preview_running()
        runtime_state.append_event("preview", "Preview started.")
        runtime_state.refresh_monitor_payload(status_override="Preview started.")
        return {
            "ok": True,
            "preview_enabled": runtime_state.preview_enabled,
            "preview_status": runtime_state.preview_status_text(),
        }

    @app.post(PREVIEW_STOP_PATH)
    async def preview_stop():
        if runtime_state.capture_state.capture_running:
            raise HTTPException(status_code=409, detail="Cannot stop preview while capture is running")
        runtime_state.preview_enabled = False
        runtime_state.stop_preview(wait=True)
        runtime_state.append_event("preview", "Preview stopped.")
        runtime_state.refresh_monitor_payload(status_override="Preview stopped.")
        return {
            "ok": True,
            "preview_enabled": runtime_state.preview_enabled,
            "preview_status": runtime_state.preview_status_text(),
        }

    @app.get(MJPEG_PATH)
    async def mjpeg_stream():
        return StreamingResponse(
            runtime_state.iter_preview_mjpeg_chunks(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.get(EVENTS_PATH)
    async def get_events():
        return {"ok": True, "events": runtime_state.recent_events()}

    @app.get(MONITOR_PATH)
    async def get_monitor():
        return runtime_state.snapshot()

    @app.post(CONTROL_START_PATH)
    async def start_capture(request: StartCaptureRequest):
        validate_runtime_options(request.mode, request.quality_mode)
        return runtime_state.start_capture(request)

    @app.post(CONTROL_STOP_PATH)
    async def stop_capture():
        return runtime_state.stop_capture()

    @app.websocket(WS_PATH)
    async def monitor_socket(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                payload = runtime_state.snapshot()
                await websocket.send_json(payload)
                await websocket.receive_text()
        except WebSocketDisconnect:
            return
        except RuntimeError:
            return

    return app


def run_api_server(app: FastAPI):
    config = uvicorn.Config(app, host=API_HOST, port=API_PORT, log_level="info")
    server = uvicorn.Server(config)
    server.run()


def wait_for_frontend_ready(url: str, timeout_seconds: float = 30.0):
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            response = requests.get(url, timeout=1.0)
            if response.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Frontend dev server not reachable: {url}")


def resolve_webview_debug_mode() -> bool:
    raw = (os.environ.get("USB_CAM_WEBVIEW_DEBUG") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def main():
    import webview

    global webview_window

    append_runtime_log(RUNTIME_LOG_PATH, "desktop entry started")
    app = create_app()
    api_thread = threading.Thread(target=run_api_server, args=(app,), daemon=True)
    api_thread.start()
    append_runtime_log(RUNTIME_LOG_PATH, "uvicorn thread launched")

    frontend_target = resolve_frontend_target()
    append_runtime_log(RUNTIME_LOG_PATH, f"frontend target resolved: {frontend_target}")
    if frontend_target.startswith("http://") or frontend_target.startswith("https://"):
        wait_for_frontend_ready(frontend_target)
        append_runtime_log(RUNTIME_LOG_PATH, "frontend dev server reachable")

    webview_window = webview.create_window(
        "USB Cam 4K25",
        frontend_target,
        width=1440,
        height=920,
        resizable=True,
    )
    append_runtime_log(RUNTIME_LOG_PATH, "pywebview window created")
    webview.start(debug=resolve_webview_debug_mode())


if __name__ == "__main__":
    main()
