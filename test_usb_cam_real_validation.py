import os
import shutil
import subprocess
from pathlib import Path

import pytest

from usb_cam_real_validation import (
    _base_meta,
    classify_capture_failure,
    collect_session_artifacts,
    detect_capture_process_conflicts,
    run_fps_ratio_autostop_validation,
    run_max_duration_autostop_validation,
    run_ffmpeg_process_for_duration,
    run_video_then_frames_disk_floor_autostop_validation,
    validation_success,
    run_validation,
    run_disk_floor_autostop_validation,
    validate_direct_capture_disk_floor_autostop,
    validate_direct_capture_fps_ratio_autostop,
    validate_direct_capture_max_duration_autostop,
    validate_video_then_frames_disk_floor_autostop,
    validation_disk_floor_env,
)


def test_collect_session_artifacts_reports_expected_files(tmp_path: Path):
    session = tmp_path / 'session'
    frames = session / 'frames'
    video = session / 'video'
    frames.mkdir(parents=True)
    video.mkdir()

    (frames / 'img_000001.jpg').write_bytes(b'a')
    (frames / 'img_000002.jpg').write_bytes(b'bb')
    (session / 'frames.csv').write_text('header\n', encoding='utf-8')
    (session / 'summary.txt').write_text('ok\n', encoding='utf-8')
    (session / 'metadata.json').write_text('{}\n', encoding='utf-8')
    (video / 'capture.avi').write_bytes(b'1234')

    result = collect_session_artifacts(session, frames)

    assert result['frame_count'] == 2
    assert result['frame_names'] == ['img_000001.jpg', 'img_000002.jpg']
    assert result['frames_csv_exists'] is True
    assert result['summary_exists'] is True
    assert result['metadata_exists'] is True
    assert result['video_files'] == ['capture.avi']
    assert result['total_frame_size_bytes'] == 3


def test_real_validation_base_meta_includes_stop_fields(tmp_path: Path):
    result = _base_meta(
        ffmpeg='ffmpeg.exe',
        camera_name='USB Camera',
        mode='direct_frames',
        frames_dir=tmp_path / 'frames',
        session_dir=tmp_path / 'session',
        video_path=None,
    )

    assert result['auto_stopped'] is False
    assert result['stop_reason'] is None
    assert result['stop_reason_detail'] is None


def test_classify_capture_failure_detects_camera_in_use():
    result = classify_capture_failure(
        output_text="[in#0 @ x] Could not run graph (sometimes caused by a device already in use by other application)\nError opening input file video=cam.\n",
        return_code=4294967291,
    )

    assert result["failure_reason"] == "camera_in_use"
    assert "device already in use" in result["failure_detail"]


def test_detect_capture_process_conflicts_filters_ffmpeg_and_app(monkeypatch):
    class FakeProc:
        def __init__(self, pid, name, cmdline):
            self.info = {"pid": pid, "name": name, "cmdline": cmdline}

    fake_list = [
        FakeProc(100, "ffmpeg.exe", ["ffmpeg.exe", "-i", "x"]),
        FakeProc(101, "USB_Cam_4K25.exe", ["USB_Cam_4K25.exe"]),
        FakeProc(102, "notepad.exe", ["notepad.exe"]),
    ]

    monkeypatch.setattr("usb_cam_real_validation.os.getpid", lambda: 999)
    monkeypatch.setattr("usb_cam_real_validation.psutil.process_iter", lambda attrs: fake_list)

    result = detect_capture_process_conflicts()

    assert len(result) == 2
    assert result[0]["name"] == "ffmpeg.exe"
    assert result[1]["name"] == "USB_Cam_4K25.exe"


def test_run_ffmpeg_process_for_duration_requests_stop(monkeypatch):
    events = {"stopped": False}

    class FakeStdout:
        def __iter__(self):
            import time

            yield "frame=1\n"
            time.sleep(0.03)
            yield "frame=2\n"

    class FakeProc:
        def __init__(self):
            self.stdout = FakeStdout()
            self.stdin = object()

        def wait(self):
            return 0

    fake_proc = FakeProc()

    def fake_popen(*args, **kwargs):
        return fake_proc

    def fake_request_stop_process(proc):
        assert proc is fake_proc
        events["stopped"] = True

    monkeypatch.setattr("usb_cam_real_validation.subprocess.Popen", fake_popen)
    monkeypatch.setattr("usb_cam_real_validation.request_stop_process", fake_request_stop_process)

    proc, code = run_ffmpeg_process_for_duration(["fake"], fps=25, seconds=0.01)

    assert proc is fake_proc
    assert code == 0
    assert events["stopped"] is True


def test_build_bat_detects_python_and_builds_minimal_script(tmp_path: Path):
    workspace = tmp_path / 'pkg'
    workspace.mkdir()

    src_build = Path(__file__).with_name('build.bat')
    shutil.copy2(src_build, workspace / 'build.bat')
    (workspace / 'usb_burst_cam_4k25_manual_v1_6_3.py').write_text(
        "print('ok from minimal build script')\n",
        encoding='utf-8',
    )

    result = subprocess.run(
        ['cmd', '/c', 'build.bat'],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert (workspace / 'dist' / 'USB_Cam_4K25' / 'USB_Cam_4K25.exe').exists()


def test_validation_disk_floor_env_sets_override(monkeypatch):
    monkeypatch.delenv('USB_CAM_AUTOSTOP_DISK_MB', raising=False)

    previous = validation_disk_floor_env(128.0)
    try:
        assert previous is None
        assert os.environ['USB_CAM_AUTOSTOP_DISK_MB'] == '128.0'
    finally:
        if previous is None:
            os.environ.pop('USB_CAM_AUTOSTOP_DISK_MB', None)
        else:
            os.environ['USB_CAM_AUTOSTOP_DISK_MB'] = previous


def test_validation_disk_floor_env_restores_existing_value(monkeypatch):
    monkeypatch.setenv('USB_CAM_AUTOSTOP_DISK_MB', '256')

    previous = validation_disk_floor_env(128.0)
    assert previous == '256'
    assert os.environ['USB_CAM_AUTOSTOP_DISK_MB'] == '128.0'


def test_run_validation_reports_disk_floor_override(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("usb_cam_real_validation.preview_smoke", lambda **kwargs: {"ok": True})
    monkeypatch.setattr("usb_cam_real_validation.validate_direct_capture", lambda **kwargs: {"ok": True})
    monkeypatch.setattr("usb_cam_real_validation.validate_video_then_frames", lambda **kwargs: {"ok": True})

    result = run_validation(
        ffmpeg='ffmpeg.exe',
        camera_name='USB Camera',
        output_root=tmp_path,
        capture_seconds=1.0,
        preview_seconds=1.0,
        disk_floor_override_mb=128.0,
    )

    assert result['disk_floor_override_mb'] == 128.0


def test_validation_success_ignores_non_dict_top_level_fields():
    assert validation_success({
        "disk_floor_override_mb": 128.0,
        "disk_floor_autostop": {"ok": True},
    }) is True
    assert validation_success({
        "disk_floor_override_mb": 128.0,
        "disk_floor_autostop": {"ok": False},
    }) is False


def test_run_disk_floor_autostop_validation_reports_ok(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "usb_cam_real_validation.validate_direct_capture_disk_floor_autostop",
        lambda **kwargs: {
            "ok": True,
            "auto_stopped": True,
            "stop_reason": "disk_low_space",
            "stop_reason_detail": "free_mb=64.0 threshold=128.0",
        },
    )

    result = run_disk_floor_autostop_validation(
        ffmpeg="ffmpeg.exe",
        camera_name="USB Camera",
        output_root=tmp_path,
        disk_floor_override_mb=128.0,
    )

    assert result["disk_floor_override_mb"] == 128.0
    assert result["disk_floor_autostop"]["ok"] is True


def test_run_max_duration_autostop_validation_reports_ok(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "usb_cam_real_validation.validate_direct_capture_max_duration_autostop",
        lambda **kwargs: {
            "ok": True,
            "auto_stopped": True,
            "stop_reason": "max_duration",
            "stop_reason_detail": "elapsed=3.0s limit=3.0s",
        },
    )

    result = run_max_duration_autostop_validation(
        ffmpeg="ffmpeg.exe",
        camera_name="USB Camera",
        output_root=tmp_path,
        max_duration_s=3.0,
    )

    assert result["max_duration_s"] == 3.0
    assert result["max_duration_autostop"]["ok"] is True


def test_run_fps_ratio_autostop_validation_reports_ok(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "usb_cam_real_validation.validate_direct_capture_fps_ratio_autostop",
        lambda **kwargs: {
            "ok": True,
            "auto_stopped": True,
            "stop_reason": "fps_below_threshold",
            "stop_reason_detail": "fps=5.00 threshold=17.50",
        },
    )

    result = run_fps_ratio_autostop_validation(
        ffmpeg="ffmpeg.exe",
        camera_name="USB Camera",
        output_root=tmp_path,
        min_effective_fps_ratio=0.7,
    )

    assert result["min_effective_fps_ratio"] == 0.7
    assert result["fps_ratio_autostop"]["ok"] is True


def test_run_max_duration_autostop_validation_returns_preflight_failure(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "usb_cam_real_validation.detect_capture_process_conflicts",
        lambda: [{"pid": 100, "name": "ffmpeg.exe", "cmdline": ["ffmpeg.exe"]}],
    )
    called = {"validate": False}
    monkeypatch.setattr(
        "usb_cam_real_validation.validate_direct_capture_max_duration_autostop",
        lambda **kwargs: called.__setitem__("validate", True),
    )

    result = run_max_duration_autostop_validation(
        ffmpeg="ffmpeg.exe",
        camera_name="USB Camera",
        output_root=tmp_path,
        max_duration_s=3.0,
    )

    assert result["max_duration_autostop"]["ok"] is False
    assert result["max_duration_autostop"]["failure_reason"] == "camera_in_use"
    assert result["max_duration_autostop"]["preflight_failed"] is True
    assert called["validate"] is False


def test_run_fps_ratio_autostop_validation_returns_preflight_failure(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "usb_cam_real_validation.detect_capture_process_conflicts",
        lambda: [{"pid": 100, "name": "ffmpeg.exe", "cmdline": ["ffmpeg.exe"]}],
    )
    called = {"validate": False}
    monkeypatch.setattr(
        "usb_cam_real_validation.validate_direct_capture_fps_ratio_autostop",
        lambda **kwargs: called.__setitem__("validate", True),
    )

    result = run_fps_ratio_autostop_validation(
        ffmpeg="ffmpeg.exe",
        camera_name="USB Camera",
        output_root=tmp_path,
        min_effective_fps_ratio=0.7,
    )

    assert result["fps_ratio_autostop"]["ok"] is False
    assert result["fps_ratio_autostop"]["failure_reason"] == "camera_in_use"
    assert result["fps_ratio_autostop"]["preflight_failed"] is True
    assert called["validate"] is False


def test_run_disk_floor_autostop_validation_returns_preflight_failure(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "usb_cam_real_validation.detect_capture_process_conflicts",
        lambda: [{"pid": 100, "name": "ffmpeg.exe", "cmdline": ["ffmpeg.exe"]}],
    )
    called = {"validate": False}
    monkeypatch.setattr(
        "usb_cam_real_validation.validate_direct_capture_disk_floor_autostop",
        lambda **kwargs: called.__setitem__("validate", True),
    )

    result = run_disk_floor_autostop_validation(
        ffmpeg="ffmpeg.exe",
        camera_name="USB Camera",
        output_root=tmp_path,
        disk_floor_override_mb=128.0,
    )

    assert result["disk_floor_autostop"]["ok"] is False
    assert result["disk_floor_autostop"]["failure_reason"] == "camera_in_use"
    assert result["disk_floor_autostop"]["preflight_failed"] is True
    assert called["validate"] is False


def test_run_video_then_frames_disk_floor_autostop_validation_reports_ok(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "usb_cam_real_validation.validate_video_then_frames_disk_floor_autostop",
        lambda **kwargs: {
            "ok": True,
            "auto_stopped": True,
            "stop_reason": "disk_low_space",
            "stop_reason_detail": "free_mb=64.0 threshold=128.0",
        },
    )

    result = run_video_then_frames_disk_floor_autostop_validation(
        ffmpeg="ffmpeg.exe",
        camera_name="USB Camera",
        output_root=tmp_path,
        disk_floor_override_mb=128.0,
    )

    assert result["disk_floor_override_mb"] == 128.0
    assert result["video_then_frames_disk_floor_autostop"]["ok"] is True


def test_run_video_then_frames_disk_floor_autostop_validation_returns_preflight_failure(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "usb_cam_real_validation.detect_capture_process_conflicts",
        lambda: [{"pid": 100, "name": "USB_Cam_4K25.exe", "cmdline": ["USB_Cam_4K25.exe"]}],
    )
    called = {"validate": False}
    monkeypatch.setattr(
        "usb_cam_real_validation.validate_video_then_frames_disk_floor_autostop",
        lambda **kwargs: called.__setitem__("validate", True),
    )

    result = run_video_then_frames_disk_floor_autostop_validation(
        ffmpeg="ffmpeg.exe",
        camera_name="USB Camera",
        output_root=tmp_path,
        disk_floor_override_mb=128.0,
    )

    assert result["video_then_frames_disk_floor_autostop"]["ok"] is False
    assert result["video_then_frames_disk_floor_autostop"]["failure_reason"] == "camera_in_use"
    assert result["video_then_frames_disk_floor_autostop"]["preflight_failed"] is True
    assert called["validate"] is False


def test_validate_direct_capture_disk_floor_autostop_sets_stop_reason(monkeypatch, tmp_path: Path):
    events = {"stop_called": False}

    class FakeStdout:
        def __iter__(self):
            yield "frame=1\n"
            yield "frame=2\n"

    class FakeProc:
        def __init__(self):
            self.stdout = FakeStdout()
            self.stdin = object()

        def poll(self):
            return None

        def wait(self):
            return 0

    monkeypatch.setattr("usb_cam_real_validation.build_direct_cmd", lambda *args, **kwargs: ["ffmpeg.exe"])
    monkeypatch.setattr("usb_cam_real_validation.subprocess.Popen", lambda *args, **kwargs: FakeProc())
    monkeypatch.setattr("usb_cam_real_validation.request_stop_process", lambda proc: events.__setitem__("stop_called", True))
    monkeypatch.setattr("usb_cam_real_validation.parse_ffmpeg_progress_line", lambda line, fps: 1 if "frame=1" in line else 2)
    monkeypatch.setattr("usb_cam_real_validation.shutil.disk_usage", lambda path: type("U", (), {"free": 64 * 1024 * 1024})())
    monkeypatch.setattr("usb_cam_real_validation.finalize_session", lambda **kwargs: {"current_meta": kwargs["current_meta"]})
    monkeypatch.setattr("usb_cam_real_validation.collect_session_artifacts", lambda session, frames_dir: {"frame_count": 0})

    result = validate_direct_capture_disk_floor_autostop(
        ffmpeg="ffmpeg.exe",
        camera_name="USB Camera",
        output_root=tmp_path,
        disk_floor_override_mb=128.0,
    )

    assert events["stop_called"] is True
    assert result["auto_stopped"] is True
    assert result["stop_reason"] == "disk_low_space"
    assert "threshold=128.0" in result["stop_reason_detail"]


def test_validate_direct_capture_max_duration_autostop_sets_stop_reason(monkeypatch, tmp_path: Path):
    events = {"stop_called": False}

    class FakeStdout:
        def __iter__(self):
            yield "frame=1\n"
            yield "frame=2\n"

    class FakeProc:
        def __init__(self):
            self.stdout = FakeStdout()
            self.stdin = object()

        def poll(self):
            return None

        def wait(self):
            return 0

    times = iter([100.0, 103.0])

    monkeypatch.setattr("usb_cam_real_validation.build_direct_cmd", lambda *args, **kwargs: ["ffmpeg.exe"])
    monkeypatch.setattr("usb_cam_real_validation.subprocess.Popen", lambda *args, **kwargs: FakeProc())
    monkeypatch.setattr("usb_cam_real_validation.request_stop_process", lambda proc: events.__setitem__("stop_called", True))
    monkeypatch.setattr("usb_cam_real_validation.parse_ffmpeg_progress_line", lambda line, fps: 1 if "frame=1" in line else 2)
    monkeypatch.setattr("usb_cam_real_validation.time.time", lambda: next(times))
    monkeypatch.setattr("usb_cam_real_validation.finalize_session", lambda **kwargs: {"current_meta": kwargs["current_meta"]})
    monkeypatch.setattr("usb_cam_real_validation.collect_session_artifacts", lambda session, frames_dir: {"frame_count": 0})

    result = validate_direct_capture_max_duration_autostop(
        ffmpeg="ffmpeg.exe",
        camera_name="USB Camera",
        output_root=tmp_path,
        max_duration_s=3.0,
    )

    assert events["stop_called"] is True
    assert result["auto_stopped"] is True
    assert result["stop_reason"] == "max_duration"
    assert "limit=3.0s" in result["stop_reason_detail"]


def test_validate_direct_capture_fps_ratio_autostop_sets_stop_reason(monkeypatch, tmp_path: Path):
    events = {"stop_called": False}

    class FakeStdout:
        def __iter__(self):
            yield "frame=1\n"
            yield "frame=2\n"

    class FakeProc:
        def __init__(self):
            self.stdout = FakeStdout()
            self.stdin = object()

        def poll(self):
            return None

        def wait(self):
            return 0

    monkeypatch.setattr("usb_cam_real_validation.build_direct_cmd", lambda *args, **kwargs: ["ffmpeg.exe"])
    monkeypatch.setattr("usb_cam_real_validation.subprocess.Popen", lambda *args, **kwargs: FakeProc())
    monkeypatch.setattr("usb_cam_real_validation.request_stop_process", lambda proc: events.__setitem__("stop_called", True))
    monkeypatch.setattr("usb_cam_real_validation.parse_ffmpeg_progress_line", lambda line, fps: 1 if "frame=1" in line else 2)
    monkeypatch.setattr("usb_cam_real_validation.finalize_session", lambda **kwargs: {"current_meta": kwargs["current_meta"]})
    monkeypatch.setattr("usb_cam_real_validation.collect_session_artifacts", lambda session, frames_dir: {"frame_count": 0})

    result = validate_direct_capture_fps_ratio_autostop(
        ffmpeg="ffmpeg.exe",
        camera_name="USB Camera",
        output_root=tmp_path,
        min_effective_fps_ratio=0.7,
    )

    assert events["stop_called"] is True
    assert result["auto_stopped"] is True
    assert result["stop_reason"] == "fps_below_threshold"
    assert "threshold=17.50" in result["stop_reason_detail"]


def test_validate_video_then_frames_disk_floor_autostop_sets_stop_reason(monkeypatch, tmp_path: Path):
    events = {"stop_called": False}

    class FakeStdout:
        def __iter__(self):
            yield "frame=1\n"
            yield "frame=2\n"

    class FakeProc:
        def __init__(self):
            self.stdout = FakeStdout()
            self.stdin = object()

        def poll(self):
            return None

        def wait(self):
            return 0

    monkeypatch.setattr("usb_cam_real_validation.build_record_cmd", lambda *args, **kwargs: ["ffmpeg.exe"])
    monkeypatch.setattr("usb_cam_real_validation.subprocess.Popen", lambda *args, **kwargs: FakeProc())
    monkeypatch.setattr("usb_cam_real_validation.request_stop_process", lambda proc: events.__setitem__("stop_called", True))
    monkeypatch.setattr("usb_cam_real_validation.parse_ffmpeg_progress_line", lambda line, fps: 1 if "frame=1" in line else 2)
    monkeypatch.setattr("usb_cam_real_validation.shutil.disk_usage", lambda path: type("U", (), {"free": 64 * 1024 * 1024})())
    monkeypatch.setattr("usb_cam_real_validation.finalize_session", lambda **kwargs: {"current_meta": kwargs["current_meta"]})
    monkeypatch.setattr("usb_cam_real_validation.collect_session_artifacts", lambda session, frames_dir: {"frame_count": 0, "video_files": []})

    result = validate_video_then_frames_disk_floor_autostop(
        ffmpeg="ffmpeg.exe",
        camera_name="USB Camera",
        output_root=tmp_path,
        disk_floor_override_mb=128.0,
    )

    assert events["stop_called"] is True
    assert result["auto_stopped"] is True
    assert result["stop_reason"] == "disk_low_space"
    assert "threshold=128.0" in result["stop_reason_detail"]
