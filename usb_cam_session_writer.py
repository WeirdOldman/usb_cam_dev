from __future__ import annotations

from datetime import datetime
from pathlib import Path


FPS = 25
WIDTH = 3840
HEIGHT = 2160


def now_str(clock) -> str:
    return clock().strftime("%Y%m%d_%H%M%S")


def make_session(output_dir: str, prefix: str, *, clock=datetime.now):
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    safe_prefix = prefix.strip() or "manual_4k25"
    session = root / f"{safe_prefix}_{now_str(clock)}"
    frames = session / "frames"
    video = session / "video"
    frames.mkdir(parents=True, exist_ok=True)
    video.mkdir(parents=True, exist_ok=True)
    return session, frames, video


def count_frame_files(frames_dir: Path):
    return sorted(frames_dir.glob("*.jpg")) if frames_dir.exists() else []


def write_frames_csv(session: Path, frames_dir: Path):
    import csv

    files = count_frame_files(frames_dir)
    csv_path = session / "frames.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "filename", "approx_time_s", "file_size_bytes"])
        for i, path in enumerate(files, 1):
            approx_t = (i - 1) / FPS
            size = path.stat().st_size if path.exists() else 0
            writer.writerow([i, path.name, f"{approx_t:.3f}", size])
    return csv_path, files


def write_metadata(session: Path, meta: dict):
    import json

    path = session / "metadata.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return path


def write_summary(session: Path, meta: dict):
    path = session / "summary.txt"
    lines = [
        "USB Camera 4K25 Capture Summary",
        "=" * 40,
        f"App: {meta.get('app')}",
        f"Created at: {meta.get('created_at')}",
        f"Camera: {meta.get('camera_name')}",
        f"Mode: {meta.get('mode')}",
        f"Quality mode: {meta.get('quality_mode')}",
        f"Input: {WIDTH}x{HEIGHT} @ {FPS}fps MJPEG",
        f"Frame count: {meta.get('frame_count', 0)}",
        f"Capture duration by frames: {meta.get('capture_duration_by_frames_s', 0):.3f} s",
        f"Total process duration: {meta.get('total_process_duration_s', 0):.3f} s",
        f"Effective FPS by frames: {meta.get('effective_fps_by_frames', 0):.3f}",
        f"Total frame size: {meta.get('total_frame_size_mb', 0):.2f} MB",
        f"Average frame size: {meta.get('average_frame_size_mb', 0):.3f} MB",
        f"Estimated frame output per minute: {meta.get('estimated_frames_size_per_min_mb', 0):.2f} MB",
        f"Session total size: {meta.get('session_total_size_mb', 0):.2f} MB",
        f"Delete video after extract: {meta.get('delete_video_after_extract', False)}",
        f"Video path: {meta.get('video_path')}",
        f"Frames dir: {meta.get('frames_dir')}",
        f"Run log: {meta.get('run_log_path')}",
        f"Capture result: {meta.get('capture_result', 'unknown')}",
        f"Capture phase: {meta.get('capture_phase', 'unknown')}",
        f"Capture failure reason: {meta.get('capture_failure_reason')}",
        f"Capture failure detail: {meta.get('capture_failure_message')}",
        f"Capture failure code: {meta.get('capture_failure_code')}",
        "",
        "Notes:",
        "- DPI metadata does not change the actual 3840x2160 pixel content.",
        "- This workflow preserves original 4K frames without scaling or forced 300 DPI metadata.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
