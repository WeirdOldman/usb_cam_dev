from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CaptureContext:
    current_session: Path | None = None
    current_frames_dir: Path | None = None
    current_video_dir: Path | None = None
    current_meta: dict = field(default_factory=dict)
    log_writer: object | None = None

    def assign_session_paths(self, current_session: Path, current_frames_dir: Path, current_video_dir: Path) -> None:
        self.current_session = current_session
        self.current_frames_dir = current_frames_dir
        self.current_video_dir = current_video_dir

    def set_meta(self, meta: dict) -> None:
        self.current_meta = meta

    def set_log_writer(self, log_writer) -> None:
        self.log_writer = log_writer

    def clear_log_writer(self) -> None:
        self.log_writer = None

    def update_meta(self, meta: dict) -> None:
        self.current_meta = meta
