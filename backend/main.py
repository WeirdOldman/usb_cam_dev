from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import os

import psutil
from fastapi import FastAPI, HTTPException


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.runtime_api import (
    RuntimeApiConfig,
    RuntimeConfigResponse,
    SelectOutputDirRequest,
    StartCaptureRequest,
    UpdateConfigRequest,
    create_runtime_app,
)
from backend.runtime_capture import (
    apply_config_update as apply_runtime_config_update,
    classify_capture_failure as classify_runtime_capture_failure,
    prepare_capture_session as prepare_runtime_capture_session,
    start_capture as start_runtime_capture,
    stop_capture as stop_runtime_capture,
    update_control_settings as update_runtime_control_settings,
    worker_capture as run_runtime_capture_worker,
)
from backend.runtime_host import (
    append_runtime_log as write_runtime_log,
    open_path_in_system,
    query_camera_devices,
    require_window as require_runtime_window,
    resolve_frontend_target as resolve_frontend_runtime_target,
    resolve_webview_debug_mode as read_webview_debug_mode,
    run_api_server as serve_runtime_api,
    select_output_directory,
    wait_for_frontend_ready as wait_for_frontend_runtime,
)
from backend.runtime_monitor import (
    append_runtime_event,
    build_control_config,
    build_monitor_payload as build_runtime_monitor_payload,
    capture_phase_payload as runtime_capture_phase_payload,
    idle_status_text as runtime_idle_status_text,
    preview_status_text as runtime_preview_status_text,
    recent_runtime_events,
    refresh_monitor_payload as refresh_runtime_monitor_payload,
    snapshot as snapshot_runtime_monitor,
    ui_locks as runtime_ui_locks,
)
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
from usb_cam_session_writer import make_session, write_metadata, write_summary
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
APP_NAME = "usb_cam_pywebview_demo"
WIDTH = 3840
HEIGHT = 2160
FPS = 25
DEFAULT_CAMERA_NAME = "imx678' UVC "
MAX_LOG_BYTES = 10 * 1024 * 1024
PREVIEW_WIDTH = 640
PREVIEW_FPS = 5
UNKNOWN_ACCELERATION = "Unknown"


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
        append_runtime_event(self, kind, message)

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
        return runtime_idle_status_text(self, status_override)

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
        return runtime_capture_phase_payload(self)

    def recent_events(self):
        return recent_runtime_events(self)

    def control_config(self) -> dict:
        return build_control_config(
            self,
            api_host=API_HOST,
            api_port=API_PORT,
            frontend_dev_url=FRONTEND_DEV_URL,
            mjpeg_path=MJPEG_PATH,
            ws_path=WS_PATH,
            control_start_path=CONTROL_START_PATH,
            control_stop_path=CONTROL_STOP_PATH,
            preview_start_path=PREVIEW_START_PATH,
            preview_stop_path=PREVIEW_STOP_PATH,
            auto_stop_prefs_fn=default_auto_stop_prefs,
        )

    def update_control_settings(self, request: StartCaptureRequest):
        update_runtime_control_settings(self, request, find_ffmpeg_fn=lambda: find_ffmpeg() or "")

    def apply_config_update(self, request: UpdateConfigRequest):
        apply_runtime_config_update(self, request, find_ffmpeg_fn=lambda: find_ffmpeg() or "")

    def prepare_capture_session(self):
        return prepare_runtime_capture_session(
            self,
            make_session_fn=make_session,
            limited_log_writer_cls=LimitedLogWriter,
            build_capture_meta_fn=build_capture_meta,
            safe_image_prefix_fn=safe_image_prefix,
            app_name=APP_NAME,
            width=WIDTH,
            height=HEIGHT,
            fps=FPS,
            max_log_bytes=MAX_LOG_BYTES,
        )

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
        return classify_runtime_capture_failure(self, result=result, exc=exc)

    def worker_capture(self):
        run_runtime_capture_worker(
            self,
            execute_capture_pipeline_fn=execute_capture_pipeline,
            finalize_capture_summary_fn=finalize_capture_summary,
            handle_capture_exception_fn=handle_capture_exception,
            close_capture_resources_fn=close_capture_resources,
            status_setter_factory=DummyStatusSetter,
            queue_factory=queue.Queue,
        )

    def start_capture(self, request: StartCaptureRequest):
        return start_runtime_capture(self, request, thread_factory=threading.Thread)

    def stop_capture(self):
        return stop_runtime_capture(self, request_stop_process_fn=request_stop_process)

    def preview_status_text(self) -> str:
        return runtime_preview_status_text(self)

    def ui_locks(self) -> dict:
        return runtime_ui_locks(self)

    def refresh_monitor_payload(self, status_override: str | None = None):
        refresh_runtime_monitor_payload(
            self,
            status_override=status_override,
            now_value=time.time(),
            fps=FPS,
            width=WIDTH,
            height=HEIGHT,
            unknown_acceleration=UNKNOWN_ACCELERATION,
            update_capture_timer_tick_fn=update_capture_timer_tick,
            update_capture_metrics_fn=update_capture_metrics,
            auto_stop_prefs_fn=default_auto_stop_prefs,
            cpu_percent_fn=psutil.cpu_percent,
        )

    def build_monitor_payload(self):
        return build_runtime_monitor_payload(self, width=WIDTH, height=HEIGHT)

    def snapshot(self):
        return snapshot_runtime_monitor(self)


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


def open_directory_dialog(current_dir: str | None = None) -> str | None:
    return select_output_directory(
        webview_window=webview_window,
        current_dir=current_dir,
        fallback_dir=str(runtime_state.output_dir or runtime_state.base_dir),
    )


def require_window():
    return require_runtime_window(webview_window)


def open_system_path(path: str):
    open_path_in_system(path)


def list_camera_devices(ffmpeg_path: str | None) -> list[str]:
    return query_camera_devices(ffmpeg_path, popen_kwargs=windows_popen_kwargs)


def append_runtime_log(path: Path, message: str):
    write_runtime_log(path, message)


def resolve_frontend_target(frontend_dir: Path = FRONTEND_DIST_DIR, dev_url: str = FRONTEND_DEV_URL) -> str:
    return resolve_frontend_runtime_target(frontend_dir, dev_url)


def create_app() -> FastAPI:
    return create_runtime_app(
        runtime_state=runtime_state,
        config=RuntimeApiConfig(
            title="USB Cam 4K25 Demo Backend",
            api_host=API_HOST,
            api_port=API_PORT,
            cors_origins=("http://localhost:5173", "http://127.0.0.1:5173"),
            mjpeg_path=MJPEG_PATH,
            ws_path=WS_PATH,
            control_start_path=CONTROL_START_PATH,
            control_stop_path=CONTROL_STOP_PATH,
            config_path=CONFIG_PATH,
            select_output_dir_path=SELECT_OUTPUT_DIR_PATH,
            window_minimize_path=WINDOW_MINIMIZE_PATH,
            window_toggle_maximize_path=WINDOW_TOGGLE_MAXIMIZE_PATH,
            window_close_path=WINDOW_CLOSE_PATH,
            open_output_dir_path=OPEN_OUTPUT_DIR_PATH,
            ffmpeg_status_path=FFMPEG_STATUS_PATH,
            preview_start_path=PREVIEW_START_PATH,
            preview_stop_path=PREVIEW_STOP_PATH,
            events_path=EVENTS_PATH,
            camera_devices_path=CAMERA_DEVICES_PATH,
            monitor_path=MONITOR_PATH,
            open_directory_dialog=lambda current_dir: open_directory_dialog(current_dir),
            require_window=lambda: require_window(),
            open_system_path=lambda path: open_system_path(path),
            list_camera_devices=lambda ffmpeg_path: list_camera_devices(ffmpeg_path),
            resolve_ffmpeg_path=lambda: find_ffmpeg() or "",
            validate_runtime_options=lambda mode, quality_mode: validate_runtime_options(mode, quality_mode),
        ),
    )


def run_api_server(app: FastAPI):
    serve_runtime_api(app, host=API_HOST, port=API_PORT)


def wait_for_frontend_ready(url: str, timeout_seconds: float = 30.0):
    wait_for_frontend_runtime(url, timeout_seconds=timeout_seconds)


def resolve_webview_debug_mode() -> bool:
    return read_webview_debug_mode(os.environ.get("USB_CAM_WEBVIEW_DEBUG"))


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
