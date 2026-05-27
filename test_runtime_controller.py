from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest

from controller.contracts import RuntimeConfigPatch, StartCaptureRequest
from controller.runtime_controller import RuntimeController


REPO_ROOT = Path(__file__).resolve().parent
FFMPEG_PATH = str(REPO_ROOT / "tools" / "ffmpeg.exe")


def make_controller(tmp_path: Path) -> RuntimeController:
    return RuntimeController(base_dir=tmp_path)


def test_load_config_returns_desktop_runtime_defaults(tmp_path: Path):
    controller = make_controller(tmp_path)

    config = controller.load_config()
    snapshot = controller.snapshot()

    assert config.camera_name == "imx678' UVC "
    assert config.mode == "direct_frames"
    assert config.quality_mode == "copy"
    assert config.output_dir == str(tmp_path / "capture_output")
    assert config.ffmpeg_path == (controller.ffmpeg_path or "")
    assert snapshot.preview_enabled is False
    assert snapshot.preview_status == "Preview stopped."
    assert snapshot.status_text == "Stopped"


def test_update_config_persists_runtime_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    controller = make_controller(tmp_path)
    monkeypatch.setattr(controller, "_find_ffmpeg", lambda: FFMPEG_PATH)

    result = controller.update_config(
        RuntimeConfigPatch(
            camera_name="Rewired Camera",
            output_dir=str(tmp_path / "custom_out"),
            image_prefix="frame",
            mode="video_then_frames",
            quality_mode="q2",
            delete_video_after_extract=True,
        )
    )

    assert result.ok is True
    assert result.config is not None
    assert result.config.camera_name == "Rewired Camera"
    assert result.config.output_dir == str(tmp_path / "custom_out")
    assert result.config.image_prefix == "frame"
    assert result.config.mode == "video_then_frames"
    assert result.config.quality_mode == "q2"
    assert result.config.delete_video_after_extract is True
    assert result.snapshot is not None
    assert result.snapshot.config.camera_name == "Rewired Camera"


def test_start_capture_accepts_parameterized_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    controller = make_controller(tmp_path)
    monkeypatch.setattr(controller, "_find_ffmpeg", lambda: FFMPEG_PATH)
    monkeypatch.setattr(controller, "prepare_capture_session", lambda: tmp_path / "session" / "run_log.txt")

    class DummyWorker:
        def __init__(self, target=None, daemon=None):
            self.target = target
            self.daemon = daemon

        def start(self):
            return None

    monkeypatch.setattr(controller, "_thread_factory", DummyWorker)
    monkeypatch.setattr(controller, "refresh_monitor_payload", lambda status_override=None: None)

    result = controller.start_capture(
        StartCaptureRequest(
            mode="video_then_frames",
            output_dir=str(tmp_path / "captures"),
            image_prefix="demo",
            quality_mode="q2",
            delete_video_after_extract=True,
            camera_name="USB Camera",
        )
    )

    assert result.ok is True
    assert result.snapshot is not None
    assert result.snapshot.running is True
    assert result.config is not None
    assert result.config.mode == "video_then_frames"
    assert result.config.image_prefix == "demo"
    assert result.config.quality_mode == "q2"
    assert result.config.delete_video_after_extract is True


def test_start_preview_and_stop_preview_toggle_preview_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    controller = make_controller(tmp_path)
    monkeypatch.setattr(controller, "ensure_preview_running", lambda: None)
    stop_calls: list[bool] = []
    monkeypatch.setattr(controller, "stop_preview_process", lambda wait=False: stop_calls.append(wait))

    started = controller.start_preview()
    stopped = controller.stop_preview()

    assert started.ok is True
    assert started.snapshot is not None
    assert started.snapshot.preview_enabled is True
    assert stopped.ok is True
    assert stopped.snapshot is not None
    assert stopped.snapshot.preview_enabled is False
    assert stop_calls == [True]


def test_snapshot_is_dataclass_serializable(tmp_path: Path):
    controller = make_controller(tmp_path)

    payload = asdict(controller.snapshot())

    assert payload["capture_phase"] == "idle"
    assert payload["config"]["mode"] == "direct_frames"
    assert payload["ui_locks"]["capture_stop_disabled"] is True
