from __future__ import annotations

from datetime import datetime
from pathlib import Path

from usb_cam_session_writer import count_frame_files


def build_capture_meta(
    *,
    app_name: str,
    created_at: str,
    camera_name: str,
    mode: str,
    quality_mode: str,
    width: int,
    height: int,
    fps: int,
    image_prefix: str,
    ffmpeg: str,
    session_dir: Path,
    frames_dir: Path,
    run_log_path: Path,
    run_log_max_bytes: int,
    delete_video_after_extract: bool,
    manual_start_time: str,
) -> dict:
    return {
        "app": app_name,
        "created_at": created_at,
        "camera_name": camera_name,
        "mode": mode,
        "quality_mode": quality_mode,
        "input": {"width": width, "height": height, "fps": fps, "codec": "mjpeg"},
        "output": {
            "original_size_only": True,
            "scale": "none",
            "dpi_metadata_modified": False,
            "image_prefix": image_prefix,
        },
        "ffmpeg": ffmpeg,
        "session_dir": str(session_dir),
        "frames_dir": str(frames_dir),
        "video_path": None,
        "run_log_path": str(run_log_path),
        "run_log_max_bytes": run_log_max_bytes,
        "commands": [],
        "exit_codes": [],
        "delete_video_after_extract": bool(delete_video_after_extract),
        "manual_start_time": manual_start_time,
    }


def run_capture_pipeline(
    *,
    mode: str,
    ffmpeg: str,
    current_video_dir: Path | None,
    current_frames_dir: Path | None,
    delete_video_after_extract: bool,
    current_meta: dict,
    run_process,
    build_direct_cmd,
    build_record_cmd,
    build_extract_cmd,
) -> None:
    if mode == "direct_frames":
        code = run_process(build_direct_cmd(ffmpeg), "direct_frames")
        current_meta["exit_codes"].append({"direct_frames": code})
        return

    assert current_video_dir is not None
    video_path = current_video_dir / "capture_4k25_mjpeg.avi"
    current_meta["video_path"] = str(video_path)
    code1 = run_process(build_record_cmd(ffmpeg, video_path), "record_video")
    current_meta["exit_codes"].append({"record_video": code1})
    if video_path.exists() and video_path.stat().st_size > 0:
        code2 = run_process(build_extract_cmd(ffmpeg, video_path), "extract_frames_copy", allow_manual_stop=False)
        current_meta["exit_codes"].append({"extract_frames_copy": code2})
        if current_frames_dir and len(count_frame_files(current_frames_dir)) == 0:
            code3 = run_process(build_extract_cmd(ffmpeg, video_path, fallback_q2=True), "extract_frames_q2", allow_manual_stop=False)
            current_meta["exit_codes"].append({"extract_frames_q2": code3})
        if delete_video_after_extract and current_frames_dir and len(count_frame_files(current_frames_dir)) > 0:
            try:
                video_path.unlink()
                current_meta["video_deleted_after_extract"] = True
            except Exception as e:
                current_meta["video_delete_error"] = str(e)
