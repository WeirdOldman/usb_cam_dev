from __future__ import annotations

from pathlib import Path

from usb_cam_paths import safe_image_prefix


FPS = 25
WIDTH = 3840
HEIGHT = 2160


def now_str(clock) -> str:
    return clock().strftime("%Y%m%d_%H%M%S")


def make_session(output_dir: str, prefix: str, *, clock=__import__('datetime').datetime.now):
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
        w = csv.writer(f)
        w.writerow(["index", "filename", "approx_time_s", "file_size_bytes"])
        for i, p in enumerate(files, 1):
            approx_t = (i - 1) / FPS
            size = p.stat().st_size if p.exists() else 0
            w.writerow([i, p.name, f"{approx_t:.3f}", size])
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
        "USB 摄像头 4K25 手动连拍摘要",
        "=" * 40,
        f"应用版本: {meta.get('app')}",
        f"创建时间: {meta.get('created_at')}",
        f"摄像头: {meta.get('camera_name')}",
        f"模式: {meta.get('mode')}",
        f"画质模式: {meta.get('quality_mode')}",
        f"输入: {WIDTH}x{HEIGHT} @ {FPS}fps MJPEG",
        f"图片数量: {meta.get('frame_count', 0)}",
        f"按帧估算有效时长: {meta.get('capture_duration_by_frames_s', 0):.3f} 秒",
        f"总流程耗时: {meta.get('total_process_duration_s', 0):.3f} 秒",
        f"按帧估算 FPS: {meta.get('effective_fps_by_frames', 0):.3f}",
        f"总图片大小: {meta.get('total_frame_size_mb', 0):.2f} MB",
        f"平均每张图片: {meta.get('average_frame_size_mb', 0):.3f} MB",
        f"按当前平均大小估算每分钟图片: {meta.get('estimated_frames_size_per_min_mb', 0):.2f} MB",
        f"本次目录总大小: {meta.get('session_total_size_mb', 0):.2f} MB",
        f"是否删除中间视频: {meta.get('delete_video_after_extract', False)}",
        f"视频路径: {meta.get('video_path')}",
        f"图片目录: {meta.get('frames_dir')}",
        f"日志文件: {meta.get('run_log_path')}",
        "",
        "说明:",
        "- DPI 只是打印/排版元数据，不影响 3840x2160 的实际画质。",
        "- 当前程序不缩放、不写 300DPI 元数据，默认保留原始 4K 细节。",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
