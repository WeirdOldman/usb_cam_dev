from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CaptureState:
    capture_running: bool = False
    start_time: float = 0.0
    last_ffmpeg_frame: int = 0
    last_display_frame_count: int = 0
    last_scan_time: float = 0.0
    last_session_size_scan_time: float = 0.0
    cached_frame_count: int = 0
    cached_frame_total_size: int = 0
    cached_session_size: int = 0
    last_fps_sample_time: float = 0.0
    last_fps_sample_count: int = 0
    instant_fps: float = 0.0

    def reset_for_capture(self) -> None:
        self.last_ffmpeg_frame = 0
        self.last_display_frame_count = 0
        self.last_scan_time = 0.0
        self.last_session_size_scan_time = 0.0
        self.cached_frame_count = 0
        self.cached_frame_total_size = 0
        self.cached_session_size = 0
        self.last_fps_sample_time = self.start_time
        self.last_fps_sample_count = 0
        self.instant_fps = 0.0

    def snapshot_for_metrics(self, *, current_frames_dir: Path | None, current_session: Path | None) -> dict:
        return {
            'start_time': self.start_time,
            'last_scan_time': self.last_scan_time,
            'current_frames_dir': current_frames_dir,
            'cached_frame_count': self.cached_frame_count,
            'cached_frame_total_size': self.cached_frame_total_size,
            'last_ffmpeg_frame': self.last_ffmpeg_frame,
            'last_display_frame_count': self.last_display_frame_count,
            'last_session_size_scan_time': self.last_session_size_scan_time,
            'current_session': current_session,
            'cached_session_size': self.cached_session_size,
            'last_fps_sample_time': self.last_fps_sample_time,
            'last_fps_sample_count': self.last_fps_sample_count,
            'instant_fps': self.instant_fps,
        }

    def apply_metrics_snapshot(self, snapshot: dict) -> None:
        self.last_scan_time = snapshot['last_scan_time']
        self.cached_frame_count = snapshot['cached_frame_count']
        self.cached_frame_total_size = snapshot['cached_frame_total_size']
        self.last_display_frame_count = snapshot['last_display_frame_count']
        self.last_session_size_scan_time = snapshot['last_session_size_scan_time']
        self.cached_session_size = snapshot['cached_session_size']
        self.last_fps_sample_time = snapshot['last_fps_sample_time']
        self.last_fps_sample_count = snapshot['last_fps_sample_count']
        self.instant_fps = snapshot['instant_fps']

    def queue_snapshot(self) -> dict:
        return {
            'last_ffmpeg_frame': self.last_ffmpeg_frame,
            'capture_running': self.capture_running,
        }

    def apply_queue_snapshot(self, snapshot: dict) -> None:
        self.last_ffmpeg_frame = snapshot['last_ffmpeg_frame']
        self.capture_running = snapshot['capture_running']

    def apply_finalize_result(self, finalized: dict) -> None:
        if finalized['cached_frame_count'] is not None:
            self.cached_frame_count = finalized['cached_frame_count']
            self.cached_frame_total_size = finalized['cached_frame_total_size']
        if finalized['cached_session_size'] is not None:
            self.cached_session_size = finalized['cached_session_size']
