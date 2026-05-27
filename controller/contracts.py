from __future__ import annotations

from dataclasses import dataclass, field


CaptureMode = str
QualityMode = str


@dataclass(slots=True)
class StartCaptureRequest:
    mode: CaptureMode = "direct_frames"
    output_dir: str | None = None
    image_prefix: str = "img"
    quality_mode: QualityMode = "copy"
    delete_video_after_extract: bool = False
    camera_name: str = "imx678' UVC "


@dataclass(slots=True)
class RuntimeConfigPatch:
    camera_name: str | None = None
    output_dir: str | None = None
    image_prefix: str | None = None
    mode: CaptureMode | None = None
    quality_mode: QualityMode | None = None
    delete_video_after_extract: bool | None = None


@dataclass(slots=True)
class RuntimeConfig:
    camera_name: str
    output_dir: str
    image_prefix: str
    mode: CaptureMode
    quality_mode: QualityMode
    delete_video_after_extract: bool
    ffmpeg_path: str
    base_dir: str
    auto_stop: dict


@dataclass(slots=True)
class RuntimeEvent:
    kind: str
    message: str
    timestamp: str


@dataclass(slots=True)
class RuntimeUiLocks:
    capture_start_disabled: bool
    capture_start_reason: str
    capture_stop_disabled: bool
    capture_stop_reason: str
    preview_toggle_disabled: bool
    preview_toggle_reason: str
    path_edit_disabled: bool
    path_edit_reason: str
    config_save_disabled: bool
    config_save_reason: str
    camera_select_disabled: bool
    camera_select_reason: str


@dataclass(slots=True)
class RuntimeSnapshot:
    running: bool
    capture_phase: str
    runtime_seconds: int
    fps: float
    cpu_percent: float
    processed_frames: int
    acceleration: str
    bitrate_mbps: float
    resolution: str
    status_text: str
    capture_last_error: str | None
    capture_last_error_reason: str | None
    capture_last_error_code: int | None
    capture_last_session_dir: str | None
    preview_enabled: bool
    preview_active: bool
    preview_status: str
    ui_locks: RuntimeUiLocks
    events: list[RuntimeEvent] = field(default_factory=list)
    timestamp: str = ""
    config: RuntimeConfig | None = None


@dataclass(slots=True)
class ActionResult:
    ok: bool
    message: str
    config: RuntimeConfig | None = None
    snapshot: RuntimeSnapshot | None = None
    selected_dir: str | None = None
    devices: list[str] = field(default_factory=list)
