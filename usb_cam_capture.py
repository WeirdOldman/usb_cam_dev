from __future__ import annotations

from pathlib import Path

def base_input_args(width: int, height: int, fps: int, camera_name: str) -> list[str]:
    return [
        "-f", "dshow",
        "-video_size", f"{width}x{height}",
        "-framerate", str(fps),
        "-vcodec", "mjpeg",
        "-i", f"video={camera_name}",
        "-map", "0:v:0",
    ]


def image_output_args(quality_mode: str) -> list[str]:
    if quality_mode == "copy":
        return ["-c:v", "copy", "-f", "image2"]
    return ["-q:v", "2"]


def ffmpeg_progress_args(ffmpeg: str) -> list[str]:
    return [ffmpeg, "-y", "-hide_banner", "-stats_period", "0.5", "-progress", "pipe:1"]


def build_direct_cmd(ffmpeg: str, output_dir: Path, image_prefix: str, width: int, height: int, fps: int, camera_name: str, quality_mode: str) -> list[str]:
    return ffmpeg_progress_args(ffmpeg) + base_input_args(width, height, fps, camera_name) + image_output_args(quality_mode) + [str(output_dir / f"{image_prefix}_%06d.jpg")]


def build_record_cmd(ffmpeg: str, video_path: Path, width: int, height: int, fps: int, camera_name: str) -> list[str]:
    return ffmpeg_progress_args(ffmpeg) + base_input_args(width, height, fps, camera_name) + ["-c:v", "copy", str(video_path)]


def build_extract_cmd(ffmpeg: str, video_path: Path, output_dir: Path, image_prefix: str, fallback_q2: bool = False) -> list[str]:
    out = output_dir / f"{image_prefix}_%06d.jpg"
    if fallback_q2:
        return ffmpeg_progress_args(ffmpeg) + ["-i", str(video_path), "-map", "0:v:0", "-q:v", "2", str(out)]
    return ffmpeg_progress_args(ffmpeg) + ["-i", str(video_path), "-map", "0:v:0", "-c:v", "copy", "-f", "image2", str(out)]
