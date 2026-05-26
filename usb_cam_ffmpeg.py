from __future__ import annotations

def quote_cmd(cmd: list[str]) -> str:
    return " ".join(f'"{x}"' if " " in x else x for x in cmd)


def preview_cmd(ffmpeg: str, camera_name: str, width: int, height: int, fps: int, preview_fps: int, preview_width: int) -> list[str]:
    return [
        ffmpeg, "-hide_banner", "-loglevel", "error",
        "-f", "dshow",
        "-video_size", f"{width}x{height}",
        "-framerate", str(fps),
        "-vcodec", "mjpeg",
        "-i", f"video={camera_name}",
        "-vf", f"fps={preview_fps},scale={preview_width}:-1",
        "-f", "image2pipe",
        "-vcodec", "png",
        "pipe:1",
    ]


def record_direct_frames_cmd(ffmpeg: str, camera_name: str, width: int, height: int, fps: int, output_pattern: str) -> list[str]:
    return [
        ffmpeg, "-hide_banner", "-loglevel", "error",
        "-f", "dshow",
        "-video_size", f"{width}x{height}",
        "-framerate", str(fps),
        "-vcodec", "mjpeg",
        "-i", f"video={camera_name}",
        "-q:v", "2",
        output_pattern,
    ]


def record_video_cmd(ffmpeg: str, camera_name: str, width: int, height: int, fps: int, output_video: str) -> list[str]:
    return [
        ffmpeg, "-hide_banner", "-loglevel", "error",
        "-f", "dshow",
        "-video_size", f"{width}x{height}",
        "-framerate", str(fps),
        "-vcodec", "mjpeg",
        "-i", f"video={camera_name}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        output_video,
    ]
