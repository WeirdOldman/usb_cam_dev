from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


def append_runtime_event(runtime: Any, kind: str, message: str) -> None:
    event = {
        "kind": kind,
        "message": message,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    with runtime.event_lock:
        runtime.event_log.append(event)
        if len(runtime.event_log) > 60:
            runtime.event_log = runtime.event_log[-60:]


def capture_phase_payload(runtime: Any) -> str:
    if runtime.capture_state.capture_running:
        if runtime.capture_phase in {"starting", "stopping"}:
            return runtime.capture_phase
        return "running"
    if runtime.capture_last_error_reason:
        return "failed"
    return "idle"


def recent_runtime_events(runtime: Any) -> list[dict]:
    with runtime.event_lock:
        return list(runtime.event_log)


def idle_status_text(runtime: Any, status_override: str | None = None) -> str:
    if runtime.capture_last_error:
        return runtime.capture_last_error
    if status_override:
        return status_override
    return "Stopped"


def preview_status_text(runtime: Any) -> str:
    if runtime.capture_state.capture_running:
        return "Preview sourced from capture pipeline."
    if not runtime.preview_enabled:
        return "Preview stopped."
    if runtime.preview_proc is not None:
        return "Preview running."
    return "Preview ready."


def ui_locks(runtime: Any) -> dict:
    ffmpeg_missing = not bool(runtime.ffmpeg_path)
    capture_running = bool(runtime.capture_state.capture_running)
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


def build_monitor_payload(
    runtime: Any,
    *,
    width: int,
    height: int,
) -> dict:
    return {
        "running": False,
        "capture_phase": capture_phase_payload(runtime),
        "runtime_seconds": 0,
        "fps": 0.0,
        "cpu_percent": 0.0,
        "processed_frames": 0,
        "acceleration": "Idle",
        "bitrate_mbps": 0.0,
        "resolution": f"{width}x{height}",
        "status_text": idle_status_text(runtime),
        "capture_last_error": runtime.capture_last_error,
        "capture_last_error_reason": runtime.capture_last_error_reason,
        "capture_last_error_code": runtime.capture_last_error_code,
        "capture_last_session_dir": runtime.capture_last_session_dir,
        "preview_enabled": runtime.preview_enabled,
        "preview_active": runtime.preview_proc is not None and getattr(runtime.preview_proc, "poll", lambda: None)() is None,
        "preview_status": preview_status_text(runtime),
        "ui_locks": ui_locks(runtime),
        "events": recent_runtime_events(runtime),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "config": runtime.control_config(),
    }


def refresh_monitor_payload(
    runtime: Any,
    *,
    status_override: str | None,
    now_value: float,
    fps: int,
    width: int,
    height: int,
    unknown_acceleration: str,
    update_capture_timer_tick_fn: Callable[..., dict],
    update_capture_metrics_fn: Callable[..., dict],
    auto_stop_prefs_fn: Callable[[], dict],
    cpu_percent_fn: Callable[..., float],
) -> None:
    if runtime.capture_state.capture_running and runtime.capture_context.current_session is not None:
        metrics = update_capture_timer_tick_fn(
            capture_state=runtime.capture_state,
            capture_context=runtime.capture_context,
            now=now_value,
            fps=fps,
            update_capture_metrics_fn=update_capture_metrics_fn,
            log_writer=runtime.capture_context.log_writer,
            auto_stop_prefs=auto_stop_prefs_fn(),
        )
        capture_fps_text = metrics.get("capture_fps_text", "-- fps")
        fps_value = float(capture_fps_text.split()[0]) if capture_fps_text not in {"-- fps", None} else 0.0
        status_text = status_override or metrics.get("capture_health_reason", "Running")
        payload = {
            "running": True,
            "capture_phase": capture_phase_payload(runtime),
            "runtime_seconds": int(max(0, now_value - runtime.capture_state.start_time)),
            "fps": fps_value,
            "cpu_percent": round(float(cpu_percent_fn(interval=None)), 1),
            "processed_frames": int(metrics.get("display_count", 0)),
            "acceleration": unknown_acceleration,
            "bitrate_mbps": round(float(metrics.get("write_rate_mb_s", 0.0)) * 8, 1),
            "resolution": f"{width}x{height}",
            "status_text": status_text,
            "capture_last_error": runtime.capture_last_error,
            "capture_last_error_reason": runtime.capture_last_error_reason,
            "capture_last_error_code": runtime.capture_last_error_code,
            "capture_last_session_dir": runtime.capture_last_session_dir,
            "preview_enabled": runtime.preview_enabled,
            "preview_active": True,
            "preview_status": preview_status_text(runtime),
            "ui_locks": ui_locks(runtime),
            "events": recent_runtime_events(runtime),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "config": runtime.control_config(),
        }
    else:
        payload = runtime.build_monitor_payload()
        payload["status_text"] = idle_status_text(runtime, status_override)

    with runtime.monitor_lock:
        runtime.last_monitor_payload = payload


def snapshot(runtime: Any) -> dict:
    if runtime.capture_state.capture_running:
        runtime.refresh_monitor_payload()
    elif (
        runtime.last_monitor_payload is None
        or runtime.capture_last_error_reason
        or bool((runtime.last_monitor_payload or {}).get("running"))
    ):
        runtime.refresh_monitor_payload()
    with runtime.monitor_lock:
        return dict(runtime.last_monitor_payload or runtime.build_monitor_payload())
