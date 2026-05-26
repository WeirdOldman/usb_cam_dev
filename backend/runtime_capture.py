from __future__ import annotations

import queue
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


def update_control_settings(
    runtime: Any,
    request: Any,
    *,
    find_ffmpeg_fn: Callable[[], str | None],
) -> None:
    runtime.camera_name = request.camera_name
    runtime.image_prefix = request.image_prefix or "img"
    runtime.mode = request.mode
    runtime.quality_mode = request.quality_mode
    runtime.delete_video_after_extract = bool(request.delete_video_after_extract)
    runtime.output_dir = Path(request.output_dir) if request.output_dir else runtime.base_dir / "capture_output"
    runtime.ffmpeg_path = find_ffmpeg_fn() or ""


def apply_config_update(
    runtime: Any,
    request: Any,
    *,
    find_ffmpeg_fn: Callable[[], str | None],
) -> None:
    if request.camera_name is not None:
        runtime.camera_name = request.camera_name
    if request.image_prefix is not None:
        runtime.image_prefix = request.image_prefix or "img"
    if request.mode is not None:
        runtime.mode = request.mode
    if request.quality_mode is not None:
        runtime.quality_mode = request.quality_mode
    if request.delete_video_after_extract is not None:
        runtime.delete_video_after_extract = bool(request.delete_video_after_extract)
    if request.output_dir is not None:
        runtime.output_dir = Path(request.output_dir) if request.output_dir else runtime.base_dir / "capture_output"
    runtime.ffmpeg_path = find_ffmpeg_fn() or ""


def prepare_capture_session(
    runtime: Any,
    *,
    make_session_fn: Callable[..., tuple[Path, Path, Path | None]],
    limited_log_writer_cls: type,
    build_capture_meta_fn: Callable[..., dict],
    safe_image_prefix_fn: Callable[[str], str],
    app_name: str,
    width: int,
    height: int,
    fps: int,
    max_log_bytes: int,
) -> Path:
    assert runtime.output_dir is not None
    current_session, current_frames_dir, current_video_dir = make_session_fn(
        str(runtime.output_dir),
        "direct_frames_mjpeg_4k" if runtime.mode == "direct_frames" else "video_then_frames_mjpeg_4k",
    )
    runtime.capture_context.assign_session_paths(current_session, current_frames_dir, current_video_dir)
    log_path = current_session / "run_log.txt"
    runtime.capture_context.set_log_writer(limited_log_writer_cls(log_path, max_log_bytes))
    runtime.capture_context.set_meta(
        build_capture_meta_fn(
            app_name=app_name,
            created_at=datetime.now().isoformat(timespec="seconds"),
            camera_name=runtime.camera_name,
            mode=runtime.mode,
            quality_mode=runtime.quality_mode,
            width=width,
            height=height,
            fps=fps,
            image_prefix=safe_image_prefix_fn(runtime.image_prefix),
            ffmpeg=runtime.ffmpeg_path or "",
            session_dir=current_session,
            frames_dir=current_frames_dir,
            run_log_path=log_path,
            run_log_max_bytes=max_log_bytes,
            delete_video_after_extract=runtime.delete_video_after_extract,
            manual_start_time=datetime.now().isoformat(timespec="seconds"),
        )
    )
    runtime.capture_state.start_time = time.time()
    runtime.capture_state.reset_for_capture()
    runtime.capture_last_session_dir = str(current_session)
    return log_path


def classify_capture_failure(runtime: Any, *, result: dict | None = None, exc: Exception | None = None) -> tuple[str, str, int | None]:
    if not runtime.ffmpeg_path:
        return "ffmpeg_missing", "FFmpeg not found.", None

    if exc is not None:
        return "runtime_exception", f"Capture runtime exception: {exc}", None

    meta = result.get("current_meta", {}) if result else runtime.capture_context.current_meta
    session_dir = runtime.capture_context.current_session
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
        camera_name = meta.get("camera_name") or runtime.camera_name
        return "camera_invalid", f"Selected camera input could not be opened: {camera_name}.", last_code

    frame_count = None
    if result is not None:
        frame_count = result.get("frame_count")
    if frame_count == 0:
        return "capture_no_frames", "Capture completed without producing frames.", last_code
    return "capture_failed", f"Capture process exited unexpectedly with code {last_code}.", last_code


def worker_capture(
    runtime: Any,
    *,
    execute_capture_pipeline_fn: Callable[..., None],
    finalize_capture_summary_fn: Callable[..., None],
    handle_capture_exception_fn: Callable[..., None],
    close_capture_resources_fn: Callable[..., None],
    status_setter_factory: Callable[[Any], Any],
    queue_factory: Callable[[], queue.Queue],
) -> None:
    ffmpeg = runtime.capture_context.current_meta["ffmpeg"]
    status_override = "Capture completed."
    try:
        execute_capture_pipeline_fn(
            mode=runtime.mode,
            ffmpeg=ffmpeg,
            current_video_dir=runtime.capture_context.current_video_dir,
            current_frames_dir=runtime.capture_context.current_frames_dir,
            delete_video_after_extract=runtime.delete_video_after_extract,
            current_meta=runtime.capture_context.current_meta,
            run_process=runtime.run_process,
            build_direct_cmd=runtime.build_direct_cmd,
            build_record_cmd=runtime.build_record_cmd,
            build_extract_cmd=runtime.build_extract_cmd,
        )
        result = runtime.finish_session()
        if (result.get("frame_count") or 0) <= 0:
            reason, message, code = runtime.classify_capture_failure(result=result)
            runtime.record_capture_error(
                reason=reason,
                message=message,
                code=code,
                session_dir=str(runtime.capture_context.current_session) if runtime.capture_context.current_session else None,
            )
            status_override = message
        else:
            status_override = runtime.mark_capture_completed(
                frame_count=result["frame_count"],
                session_dir=str(runtime.capture_context.current_session) if runtime.capture_context.current_session else None,
            )
    except Exception as exc:
        handle_capture_exception_fn(runtime.capture_context.log_writer, status_setter_factory(runtime), exc)
        if runtime.capture_context.current_session is not None and runtime.capture_context.current_frames_dir is not None:
            try:
                runtime.finish_session()
            except Exception as finalize_exc:
                if runtime.capture_context.log_writer:
                    runtime.capture_context.log_writer.write(f"\n[finalize after exception failed] {finalize_exc}\n")
        reason, message, code = runtime.classify_capture_failure(exc=exc)
        runtime.record_capture_error(
            reason=reason,
            message=message,
            code=code,
            session_dir=str(runtime.capture_context.current_session) if runtime.capture_context.current_session else None,
        )
        status_override = message
    finally:
        close_capture_resources_fn(
            runtime.capture_context.log_writer,
            runtime.capture_context.clear_log_writer,
            queue_factory(),
        )
        runtime.capture_state.capture_running = False
        runtime.proc = None
        if runtime.capture_phase != "failed":
            runtime.capture_phase = "idle"
        runtime.refresh_monitor_payload(status_override=status_override)


def start_capture(runtime: Any, request: Any, *, thread_factory: Callable[..., Any]) -> dict:
    with runtime.control_lock:
        if runtime.capture_state.capture_running:
            return {"ok": False, "running": True, "status_text": "Capture already running."}

        runtime.update_control_settings(request)
        if not runtime.ffmpeg_path:
            runtime.record_capture_error(reason="ffmpeg_missing", message="FFmpeg not found.")
            runtime.refresh_monitor_payload(status_override="FFmpeg not found.")
            return {
                "ok": False,
                "running": False,
                "status_text": "FFmpeg not found.",
                "capture_last_error": runtime.capture_last_error,
                "capture_last_error_reason": runtime.capture_last_error_reason,
                "capture_last_error_code": runtime.capture_last_error_code,
                "capture_last_session_dir": runtime.capture_last_session_dir,
            }
        if runtime.preview_proc is not None:
            runtime.stop_preview(wait=True)

        runtime.clear_capture_error()
        runtime.prepare_capture_session()
        runtime.capture_state.capture_running = True
        runtime.capture_phase = "starting"
        runtime.worker = thread_factory(target=runtime.worker_capture, daemon=True)
        runtime.worker.start()
        runtime.append_event("capture", "Starting pipeline...")
        runtime.refresh_monitor_payload(status_override="Starting pipeline...")
        return {
            "ok": True,
            "running": True,
            "capture_phase": runtime.capture_phase_payload(),
            "capture_last_error": runtime.capture_last_error,
            "capture_last_error_reason": runtime.capture_last_error_reason,
            "capture_last_error_code": runtime.capture_last_error_code,
            "capture_last_session_dir": runtime.capture_last_session_dir,
            "status_text": "Starting pipeline...",
            "config": runtime.control_config(),
        }


def stop_capture(runtime: Any, *, request_stop_process_fn: Callable[[Any], None]) -> dict:
    with runtime.control_lock:
        if not runtime.capture_state.capture_running:
            runtime.refresh_monitor_payload()
            return {
                "ok": False,
                "running": False,
                "capture_phase": runtime.capture_phase_payload(),
                "capture_last_error": runtime.capture_last_error,
                "capture_last_error_reason": runtime.capture_last_error_reason,
                "capture_last_error_code": runtime.capture_last_error_code,
                "capture_last_session_dir": runtime.capture_last_session_dir,
                "status_text": runtime.idle_status_text(),
            }
        if runtime.proc is not None:
            request_stop_process_fn(runtime.proc)
        runtime.capture_phase = "stopping"
        runtime.append_event("capture", "Stopping capture...")
        runtime.refresh_monitor_payload(status_override="Stopping capture...")
        return {
            "ok": True,
            "running": runtime.capture_state.capture_running,
            "capture_phase": runtime.capture_phase_payload(),
            "capture_last_error": runtime.capture_last_error,
            "capture_last_error_reason": runtime.capture_last_error_reason,
            "capture_last_error_code": runtime.capture_last_error_code,
            "capture_last_session_dir": runtime.capture_last_session_dir,
            "status_text": "Stopping capture...",
        }
