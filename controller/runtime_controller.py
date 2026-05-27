from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import psutil

from controller.runtime_capture import (
    apply_config_update as apply_runtime_config_update,
    classify_capture_failure as classify_runtime_capture_failure,
    prepare_capture_session as prepare_runtime_capture_session,
    start_capture as start_runtime_capture,
    stop_capture as stop_runtime_capture,
    update_control_settings as update_runtime_control_settings,
    worker_capture as run_runtime_capture_worker,
)
from controller.runtime_monitor import (
    append_runtime_event,
    capture_phase_payload as runtime_capture_phase_payload,
    idle_status_text as runtime_idle_status_text,
    preview_status_text as runtime_preview_status_text,
    recent_runtime_events,
    refresh_monitor_payload as refresh_runtime_monitor_payload,
    snapshot as snapshot_runtime_monitor,
    ui_locks as runtime_ui_locks,
)
from controller.contracts import (
    ActionResult,
    RuntimeConfig,
    RuntimeConfigPatch,
    RuntimeEvent,
    RuntimeSnapshot,
    RuntimeUiLocks,
    StartCaptureRequest,
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
from usb_cam_paths import find_ffmpeg, safe_image_prefix
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


WIDTH = 3840
HEIGHT = 2160
FPS = 25
DEFAULT_CAMERA_NAME = "imx678' UVC "
MAX_LOG_BYTES = 10 * 1024 * 1024
PREVIEW_WIDTH = 480
PREVIEW_FPS = 3
UNKNOWN_ACCELERATION = "Unknown"
APP_NAME = "usb_cam_pyside6"


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
class RuntimeController:
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
    preview_enabled: bool = False
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
    _thread_factory: Callable[..., threading.Thread] = threading.Thread
    _directory_selector: Callable[[str], str | None] | None = None

    def __post_init__(self):
        self.base_dir = Path(self.base_dir)
        self.output_dir = self.base_dir / "capture_output"
        self.ffmpeg_path = self._find_ffmpeg() or ""
        self.append_event("system", "System initialized.")
        self.last_monitor_payload = self.build_monitor_payload()

    def _find_ffmpeg(self) -> str | None:
        return find_ffmpeg()

    def validate_runtime_options(self, mode: str, quality_mode: str) -> None:
        if mode not in {"direct_frames", "video_then_frames"}:
            raise ValueError("Unsupported mode")
        if quality_mode not in {"copy", "q2"}:
            raise ValueError("Unsupported quality_mode")

    def set_directory_selector(self, selector: Callable[[str], str | None]) -> None:
        self._directory_selector = selector

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

    def load_config(self) -> RuntimeConfig:
        return RuntimeConfig(
            camera_name=self.camera_name,
            output_dir=str(self.output_dir),
            image_prefix=self.image_prefix,
            mode=self.mode,
            quality_mode=self.quality_mode,
            delete_video_after_extract=self.delete_video_after_extract,
            ffmpeg_path=self.ffmpeg_path or "",
            base_dir=str(self.base_dir),
            auto_stop=default_auto_stop_prefs(),
        )

    def control_config(self) -> dict:
        return asdict(self.load_config())

    def _to_ui_locks(self) -> RuntimeUiLocks:
        return RuntimeUiLocks(**runtime_ui_locks(self))

    def _to_events(self) -> list[RuntimeEvent]:
        return [RuntimeEvent(**event) for event in self.recent_events()]

    def _to_snapshot(self, payload: dict | None = None) -> RuntimeSnapshot:
        current = payload or snapshot_runtime_monitor(self)
        return RuntimeSnapshot(
            running=bool(current.get("running")),
            capture_phase=str(current.get("capture_phase", "idle")),
            runtime_seconds=int(current.get("runtime_seconds", 0)),
            fps=float(current.get("fps", 0.0)),
            cpu_percent=float(current.get("cpu_percent", 0.0)),
            processed_frames=int(current.get("processed_frames", 0)),
            acceleration=str(current.get("acceleration", "Idle")),
            bitrate_mbps=float(current.get("bitrate_mbps", 0.0)),
            resolution=str(current.get("resolution", f"{WIDTH}x{HEIGHT}")),
            status_text=str(current.get("status_text", "Stopped")),
            capture_last_error=current.get("capture_last_error"),
            capture_last_error_reason=current.get("capture_last_error_reason"),
            capture_last_error_code=current.get("capture_last_error_code"),
            capture_last_session_dir=current.get("capture_last_session_dir"),
            preview_enabled=bool(current.get("preview_enabled")),
            preview_active=bool(current.get("preview_active")),
            preview_status=str(current.get("preview_status", "Preview stopped.")),
            ui_locks=self._to_ui_locks(),
            events=self._to_events(),
            timestamp=str(current.get("timestamp", "")),
            config=self.load_config(),
        )

    def _snapshot_from_action_payload(self, payload: dict) -> RuntimeSnapshot:
        current = dict(self.last_monitor_payload or self.build_monitor_payload())
        for key in (
            "running",
            "capture_phase",
            "status_text",
            "capture_last_error",
            "capture_last_error_reason",
            "capture_last_error_code",
            "capture_last_session_dir",
        ):
            if key in payload:
                current[key] = payload[key]
        current["config"] = self.control_config()
        return self._to_snapshot(current)

    def update_control_settings(self, request: StartCaptureRequest):
        update_runtime_control_settings(self, request, find_ffmpeg_fn=lambda: self._find_ffmpeg() or "")

    def apply_config_update(self, request: RuntimeConfigPatch):
        apply_runtime_config_update(self, request, find_ffmpeg_fn=lambda: self._find_ffmpeg() or "")

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

    def ensure_preview_running(self):
        with self.preview_lock:
            if not self.preview_enabled:
                return
            current = self.preview_proc
            if current is not None and getattr(current, "poll", lambda: None)() is None:
                return
            ffmpeg = self._find_ffmpeg() or ""
            if not ffmpeg:
                raise RuntimeError("FFmpeg not found for preview")
            cmd = self.prepare_preview_cmd(ffmpeg)
            self.preview_proc = start_preview_process(ffmpeg, cmd)
            self.preview_worker = threading.Thread(target=self.preview_reader, daemon=True)
            self.preview_worker.start()

    def stop_preview_process(self, wait: bool = False):
        with self.preview_lock:
            proc = self.preview_proc
            if proc is None:
                return
            stop_preview_process(proc, wait=wait)
            self.preview_proc = None
            self.preview_worker = None

    def stop_preview(self, wait: bool = True) -> ActionResult:
        if self.capture_state.capture_running:
            raise RuntimeError("Cannot stop preview while capture is running")
        self.preview_enabled = False
        self.stop_preview_process(wait=wait)
        self.append_event("preview", "Preview stopped.")
        self.refresh_monitor_payload(status_override="Preview stopped.")
        return ActionResult(ok=True, message="Preview stopped.", config=self.load_config(), snapshot=self.snapshot())

    def start_preview(self) -> ActionResult:
        self.preview_enabled = True
        if not self.capture_state.capture_running:
            self.ensure_preview_running()
        self.append_event("preview", "Preview started.")
        self.refresh_monitor_payload(status_override="Preview started.")
        return ActionResult(ok=True, message="Preview started.", config=self.load_config(), snapshot=self.snapshot())

    def get_preview_frame(self) -> bytes | None:
        return self.latest_preview_frame

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

    def preview_status_text(self) -> str:
        return runtime_preview_status_text(self)

    def build_monitor_payload(self):
        self.last_monitor_payload = {
            "running": False,
            "capture_phase": self.capture_phase_payload(),
            "runtime_seconds": 0,
            "fps": 0.0,
            "cpu_percent": 0.0,
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
            "ui_locks": runtime_ui_locks(self),
            "events": self.recent_events(),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "config": self.load_config(),
        }
        return self.last_monitor_payload

    def snapshot(self) -> RuntimeSnapshot:
        return self._to_snapshot(snapshot_runtime_monitor(self))

    def update_config(self, patch: RuntimeConfigPatch) -> ActionResult:
        with self.control_lock:
            if self.capture_state.capture_running:
                raise RuntimeError("Cannot update config while capture is running")
            next_mode = patch.mode if patch.mode is not None else self.mode
            next_quality_mode = patch.quality_mode if patch.quality_mode is not None else self.quality_mode
            self.validate_runtime_options(next_mode, next_quality_mode)
            self.apply_config_update(patch)
            self.refresh_monitor_payload()
            return ActionResult(ok=True, message="Runtime config saved.", config=self.load_config(), snapshot=self.snapshot())

    def select_output_dir(self) -> ActionResult:
        if self.capture_state.capture_running:
            raise RuntimeError("Cannot select output dir while capture is running")
        if self._directory_selector is None:
            raise RuntimeError("Output directory selector is not configured")
        selected_dir = self._directory_selector(str(self.output_dir or self.base_dir))
        if not selected_dir:
            self.append_event("system", "Output directory selection cancelled.")
            return ActionResult(ok=False, message="Output directory selection cancelled.", config=self.load_config(), snapshot=self.snapshot())
        self.output_dir = Path(selected_dir)
        self.append_event("system", f"Output directory updated: {selected_dir}")
        self.refresh_monitor_payload(status_override="Output directory updated.")
        return ActionResult(
            ok=True,
            message="Output directory updated.",
            selected_dir=selected_dir,
            config=self.load_config(),
            snapshot=self.snapshot(),
        )

    def open_output_dir(self) -> ActionResult:
        target = self.output_dir or self.base_dir
        target.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            raise RuntimeError("open_output_dir currently only supports Windows")
        os.startfile(str(target))  # type: ignore[attr-defined]
        self.append_event("system", f"Opened output directory: {target}")
        return ActionResult(ok=True, message="Opened output directory.", selected_dir=str(target), config=self.load_config(), snapshot=self.snapshot())

    def load_camera_devices(self) -> ActionResult:
        ffmpeg = self.ffmpeg_path or self._find_ffmpeg() or ""
        self.ffmpeg_path = ffmpeg
        devices: list[str] = []
        if ffmpeg:
            try:
                cmd = [
                    ffmpeg,
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
                for line in text.splitlines():
                    if '"' not in line:
                        continue
                    quoted = line.split('"')
                    if len(quoted) < 2:
                        continue
                    name = quoted[1].strip()
                    if name and name not in devices and "Alternative name" not in line:
                        devices.append(name)
            except Exception:
                devices = []
        return ActionResult(ok=True, message="Camera devices loaded.", devices=devices, config=self.load_config(), snapshot=self.snapshot())

    def start_capture(self, request: StartCaptureRequest) -> ActionResult:
        self.validate_runtime_options(request.mode, request.quality_mode)
        payload = start_runtime_capture(self, request, thread_factory=self._thread_factory)
        return ActionResult(
            ok=bool(payload.get("ok")),
            message=str(payload.get("status_text", "")),
            config=self.load_config(),
            snapshot=self._snapshot_from_action_payload(payload),
        )

    def stop_capture(self) -> ActionResult:
        payload = stop_runtime_capture(self, request_stop_process_fn=request_stop_process)
        return ActionResult(
            ok=bool(payload.get("ok")),
            message=str(payload.get("status_text", "")),
            config=self.load_config(),
            snapshot=self._snapshot_from_action_payload(payload),
        )


class DummyStatusSetter:
    def __init__(self, runtime: RuntimeController):
        self.runtime = runtime

    def set(self, value: str):
        self.runtime.refresh_monitor_payload(status_override=value)
