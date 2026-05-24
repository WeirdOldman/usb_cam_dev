from __future__ import annotations

from pathlib import Path

from usb_cam_ffmpeg import quote_cmd
from usb_cam_process import run_ffmpeg_process
from usb_cam_runtime import build_capture_meta, run_capture_pipeline


def reset_capture_display(frame_count_var, elapsed_var, used_size_var, estimate_var, capture_fps_var):
    frame_count_var.set("0")
    elapsed_var.set("00:00:00")
    used_size_var.set("0 MB")
    estimate_var.set("约 0 MB/分钟")
    capture_fps_var.set("-- fps")


def prepare_capture_session(*, output_dir: str, mode_prefix: str, image_prefix: str, delete_video_after_extract: bool, app_name: str, created_at: str, camera_name: str, mode: str, quality: str, ffmpeg: str, make_session, limited_log_writer_cls, capture_context, max_log_bytes: int):
    current_session, current_frames_dir, current_video_dir = make_session(output_dir, mode_prefix)
    capture_context.assign_session_paths(current_session, current_frames_dir, current_video_dir)
    log_path = current_session / "run_log.txt"
    capture_context.set_log_writer(limited_log_writer_cls(log_path, max_log_bytes))
    capture_context.set_meta(build_capture_meta(
        app_name=app_name,
        created_at=created_at,
        camera_name=camera_name,
        mode=mode,
        quality_mode=quality,
        width=3840,
        height=2160,
        fps=25,
        image_prefix=image_prefix,
        ffmpeg=ffmpeg,
        session_dir=current_session,
        frames_dir=current_frames_dir,
        run_log_path=log_path,
        run_log_max_bytes=max_log_bytes,
        delete_video_after_extract=delete_video_after_extract,
        manual_start_time=created_at,
    ))
    return log_path


def begin_capture_run(*, now: float, capture_state, reset_capture_display_fn, set_capture_running, status_var, log_path: Path, thread_factory, worker_capture, after_update_timer):
    capture_state.start_time = now
    capture_state.reset_for_capture()
    reset_capture_display_fn()
    set_capture_running(True)
    status_var.set(f"采集中：日志写入 {log_path}")
    worker = thread_factory(target=worker_capture, daemon=True)
    worker.start()
    after_update_timer()
    return worker


def execute_capture_pipeline(*, mode: str, ffmpeg: str, current_video_dir, current_frames_dir, delete_video_after_extract: bool, current_meta: dict, run_process, build_direct_cmd, build_record_cmd, build_extract_cmd):
    run_capture_pipeline(
        mode=mode,
        ffmpeg=ffmpeg,
        current_video_dir=current_video_dir,
        current_frames_dir=current_frames_dir,
        delete_video_after_extract=delete_video_after_extract,
        current_meta=current_meta,
        run_process=run_process,
        build_direct_cmd=build_direct_cmd,
        build_record_cmd=build_record_cmd,
        build_extract_cmd=build_extract_cmd,
    )


def handle_capture_exception(log_writer, status_var, exc: Exception):
    if log_writer:
        log_writer.write(f"\n运行异常：{exc}\n")
    status_var.set(f"运行异常：{exc}")


def close_capture_resources(log_writer, clear_log_writer, ui_queue):
    if log_writer:
        log_writer.close()
        clear_log_writer()
    ui_queue.put(("capture_done", None, None))


def log_capture_command(current_meta: dict, log_writer, cmd: list[str], label: str):
    current_meta["commands"].append({label: cmd})
    if log_writer:
        log_writer.write(f"\n[{label}] COMMAND:\n{quote_cmd(cmd)}\n\n")


def make_ffmpeg_frame_callback(ui_queue):
    return lambda frame: ui_queue.put(("ffmpeg_frame", frame, None))


def execute_ffmpeg_command(cmd: list[str], log_writer, ui_queue, fps: int, started_callback=None):
    return run_ffmpeg_process(
        cmd,
        fps=fps,
        log_write=log_writer.write if log_writer else None,
        frame_callback=make_ffmpeg_frame_callback(ui_queue),
        started_callback=started_callback,
    )


def log_capture_exit_code(log_writer, label: str, code: int):
    if log_writer:
        log_writer.write(f"\n[{label}] EXIT_CODE={code}\n")


def finalize_capture_summary(capture_context, result: dict):
    capture_context.update_meta(result['current_meta'])
    if capture_context.log_writer:
        capture_context.log_writer.write(
            f"\n完成。图片数：{result['frame_count']}\n"
            f"metadata: {result['meta_path']}\n"
            f"summary: {result['summary_path']}\n"
            f"frames_csv: {result['csv_path']}\n"
        )


def apply_capture_metrics(elapsed_var, frame_count_var, used_size_var, estimate_var, capture_fps_var, metrics: dict):
    elapsed_var.set(metrics['elapsed_text'])
    frame_count_var.set(str(metrics['display_count']))
    used_size_var.set(metrics['used_size_text'])
    estimate_var.set(metrics['estimate_text'])
    capture_fps_var.set(metrics['capture_fps_text'])


def update_capture_timer_tick(*, capture_state, capture_context, now: float, fps: int, update_capture_metrics_fn, log_writer=None):
    snapshot = capture_state.snapshot_for_metrics(
        current_frames_dir=capture_context.current_frames_dir,
        current_session=capture_context.current_session,
    )
    metrics = update_capture_metrics_fn(snapshot, now=now, fps=fps)
    capture_state.apply_metrics_snapshot(snapshot)
    if (
        metrics.get('disk_low_space')
        and metrics.get('disk_free_warning_text')
        and not capture_state.disk_warning_logged
    ):
        if log_writer:
            log_writer.write(f"\n[warning] {metrics['disk_free_warning_text']}\n")
        capture_state.disk_warning_logged = True
    return metrics


def finalize_capture_done(*, capture_context, finalize_capture_done_state_fn):
    return finalize_capture_done_state_fn(
        capture_context.current_frames_dir,
        capture_context.current_session,
    )
