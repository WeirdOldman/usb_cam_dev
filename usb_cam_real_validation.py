from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
from pathlib import Path

from usb_cam_capture import build_direct_cmd, build_extract_cmd, build_record_cmd
from usb_cam_preview import build_preview_cmd, read_preview_frames, start_preview_process, stop_preview_process
from usb_cam_process import parse_ffmpeg_progress_line, request_stop_process, run_ffmpeg_process
from usb_cam_session_finalize import finalize_session
from usb_cam_session_writer import count_frame_files, make_session


WIDTH = 3840
HEIGHT = 2160
FPS = 25
DEFAULT_CAMERA_NAME = "imx678' UVC "
DEFAULT_IMAGE_PREFIX = "img"


def collect_session_artifacts(session: Path, frames_dir: Path) -> dict:
    frame_files = count_frame_files(frames_dir)
    video_dir = session / "video"
    video_files = sorted(p.name for p in video_dir.glob("*") if p.is_file()) if video_dir.exists() else []
    return {
        "session_dir": str(session),
        "frame_count": len(frame_files),
        "frame_names": [p.name for p in frame_files],
        "total_frame_size_bytes": sum(p.stat().st_size for p in frame_files if p.exists()),
        "frames_csv_exists": (session / "frames.csv").exists(),
        "summary_exists": (session / "summary.txt").exists(),
        "metadata_exists": (session / "metadata.json").exists(),
        "video_files": video_files,
    }


def preview_smoke(*, ffmpeg: str, camera_name: str, seconds: float) -> dict:
    cmd = build_preview_cmd(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
        preview_fps=5,
        preview_width=640,
    )
    proc = start_preview_process(ffmpeg, cmd)
    start = time.time()
    frame_counter = {"count": 0}

    def emit(_frame: bytes) -> None:
        frame_counter["count"] += 1
        if time.time() - start >= seconds:
            stop_preview_process(proc)

    try:
        if proc.stdout is None:
            raise RuntimeError("preview stdout unavailable")
        read_preview_frames(proc.stdout, emit)
        if proc.poll() is None:
            stop_preview_process(proc, wait=True)
    finally:
        if proc.poll() is None:
            stop_preview_process(proc, wait=True)

    return {
        "ok": frame_counter["count"] > 0,
        "preview_frames": frame_counter["count"],
        "return_code": proc.returncode,
    }


def _base_meta(*, ffmpeg: str, camera_name: str, mode: str, frames_dir: Path, session_dir: Path, video_path: str | None) -> dict:
    created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "app": "usb_cam_real_validation",
        "created_at": created_at,
        "camera_name": camera_name,
        "mode": mode,
        "quality_mode": "copy",
        "input": {"width": WIDTH, "height": HEIGHT, "fps": FPS, "codec": "mjpeg"},
        "output": {
            "original_size_only": True,
            "scale": "none",
            "dpi_metadata_modified": False,
            "image_prefix": DEFAULT_IMAGE_PREFIX,
        },
        "ffmpeg": ffmpeg,
        "session_dir": str(session_dir),
        "frames_dir": str(frames_dir),
        "video_path": video_path,
        "run_log_path": str(session_dir / "run_log.txt"),
        "run_log_max_bytes": 10 * 1024 * 1024,
        "commands": [],
        "exit_codes": [],
        "delete_video_after_extract": False,
        "manual_start_time": created_at,
    }


def run_ffmpeg_process_for_duration(cmd: list[str], *, fps: int, seconds: float) -> tuple[subprocess.Popen, int]:
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def stop_later() -> None:
        time.sleep(seconds)
        request_stop_process(proc)

    stopper = threading.Thread(target=stop_later, daemon=True)
    stopper.start()

    assert proc.stdout is not None
    for line in proc.stdout:
        parse_ffmpeg_progress_line(line, fps)

    code = proc.wait()
    stopper.join(timeout=1)
    return proc, code


def validate_direct_capture(*, ffmpeg: str, camera_name: str, output_root: Path, seconds: float) -> dict:
    session, frames_dir, _video_dir = make_session(str(output_root), "direct_frames_validation")
    cmd = build_direct_cmd(ffmpeg, frames_dir, DEFAULT_IMAGE_PREFIX, WIDTH, HEIGHT, FPS, camera_name, "copy")
    start = time.time()
    _proc, code = run_ffmpeg_process_for_duration(cmd, fps=FPS, seconds=seconds)
    meta = _base_meta(ffmpeg=ffmpeg, camera_name=camera_name, mode="direct_frames", frames_dir=frames_dir, session_dir=session, video_path=None)
    meta["commands"].append({"direct_frames": cmd})
    meta["exit_codes"].append({"direct_frames": code})
    finalize_session(current_session=session, current_frames_dir=frames_dir, current_meta=meta, start_time=start)
    artifacts = collect_session_artifacts(session, frames_dir)
    artifacts.update({"ok": artifacts["frame_count"] > 0, "exit_codes": meta["exit_codes"]})
    return artifacts


def validate_video_then_frames(*, ffmpeg: str, camera_name: str, output_root: Path, seconds: float) -> dict:
    session, frames_dir, video_dir = make_session(str(output_root), "video_then_frames_validation")
    video_path = video_dir / "capture_4k25_mjpeg.avi"
    record_cmd = build_record_cmd(ffmpeg, video_path, WIDTH, HEIGHT, FPS, camera_name)
    start = time.time()
    _proc, code1 = run_ffmpeg_process_for_duration(record_cmd, fps=FPS, seconds=seconds)
    meta = _base_meta(ffmpeg=ffmpeg, camera_name=camera_name, mode="video_then_frames", frames_dir=frames_dir, session_dir=session, video_path=str(video_path))
    meta["commands"].append({"record_video": record_cmd})
    meta["exit_codes"].append({"record_video": code1})

    if video_path.exists() and video_path.stat().st_size > 0:
        extract_cmd = build_extract_cmd(ffmpeg, video_path, frames_dir, DEFAULT_IMAGE_PREFIX, fallback_q2=False)
        _proc2, code2 = run_ffmpeg_process(extract_cmd, fps=FPS)
        meta["commands"].append({"extract_frames_copy": extract_cmd})
        meta["exit_codes"].append({"extract_frames_copy": code2})

    finalize_session(current_session=session, current_frames_dir=frames_dir, current_meta=meta, start_time=start)
    artifacts = collect_session_artifacts(session, frames_dir)
    artifacts.update({"ok": artifacts["frame_count"] > 0 and len(artifacts["video_files"]) > 0, "exit_codes": meta["exit_codes"]})
    return artifacts


def run_validation(*, ffmpeg: str, camera_name: str, output_root: Path, capture_seconds: float, preview_seconds: float) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    preview = preview_smoke(ffmpeg=ffmpeg, camera_name=camera_name, seconds=preview_seconds)
    direct = validate_direct_capture(ffmpeg=ffmpeg, camera_name=camera_name, output_root=output_root, seconds=capture_seconds)
    video_then_frames = validate_video_then_frames(ffmpeg=ffmpeg, camera_name=camera_name, output_root=output_root, seconds=capture_seconds)
    return {
        "preview": preview,
        "direct_frames": direct,
        "video_then_frames": video_then_frames,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Headless real-camera validation for usb_cam_dev")
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--camera-name", default=DEFAULT_CAMERA_NAME)
    parser.add_argument("--output-root", default=str(Path("_validation") / "real_runs"))
    parser.add_argument("--capture-seconds", type=float, default=2.0)
    parser.add_argument("--preview-seconds", type=float, default=2.0)
    args = parser.parse_args()

    result = run_validation(
        ffmpeg=args.ffmpeg,
        camera_name=args.camera_name,
        output_root=Path(args.output_root),
        capture_seconds=args.capture_seconds,
        preview_seconds=args.preview_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(section.get("ok") for section in result.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
