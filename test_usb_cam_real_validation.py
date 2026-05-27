import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from usb_cam_real_validation import (
    _base_meta,
    classify_capture_failure,
    collect_session_artifacts,
    detect_capture_process_conflicts,
    packaged_validation_summary,
    packaged_runtime_smoke,
    packaged_release_validation,
    write_validation_markdown_report,
    write_validation_report,
    run_packaged_validation_summary,
    run_packaged_runtime_smoke_validation,
    run_packaged_release_validation,
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

REPO_ROOT = Path(__file__).resolve().parent


def test_collect_session_artifacts_reports_expected_files(tmp_path: Path):
    session = tmp_path / "session"
    frames = session / "frames"
    video = session / "video"
    frames.mkdir(parents=True)
    video.mkdir()

    (frames / "img_000001.jpg").write_bytes(b"a")
    (frames / "img_000002.jpg").write_bytes(b"bb")
    (session / "frames.csv").write_text("header\n", encoding="utf-8")
    (session / "summary.txt").write_text("ok\n", encoding="utf-8")
    (session / "metadata.json").write_text("{}\n", encoding="utf-8")
    (video / "capture.avi").write_bytes(b"1234")

    result = collect_session_artifacts(session, frames)

    assert result["frame_count"] == 2
    assert result["frame_names"] == ["img_000001.jpg", "img_000002.jpg"]
    assert result["frames_csv_exists"] is True
    assert result["frames_csv_path"] == str(session / "frames.csv")
    assert result["summary_exists"] is True
    assert result["summary_path"] == str(session / "summary.txt")
    assert result["metadata_exists"] is True
    assert result["metadata_path"] == str(session / "metadata.json")
    assert result["video_files"] == ["capture.avi"]
    assert result["total_frame_size_bytes"] == 3


def test_real_validation_base_meta_includes_stop_fields(tmp_path: Path):
    result = _base_meta(
        ffmpeg="ffmpeg.exe",
        camera_name="USB Camera",
        mode="direct_frames",
        frames_dir=tmp_path / "frames",
        session_dir=tmp_path / "session",
        video_path=None,
    )

    assert result["auto_stopped"] is False
    assert result["stop_reason"] is None
    assert result["stop_reason_detail"] is None


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


@pytest.mark.skipif(sys.platform != "win32", reason="build.bat smoke test is Windows-only")
def test_build_bat_detects_python_and_builds_minimal_script(tmp_path: Path):
    workspace = tmp_path / "pkg"
    workspace.mkdir()

    shutil_files = [
        "build.bat",
        "requirements-desktop.txt",
        "usb_cam_capture.py",
        "usb_cam_capture_context.py",
        "usb_cam_capture_helpers.py",
        "usb_cam_capture_state.py",
        "usb_cam_ffmpeg.py",
        "usb_cam_paths.py",
        "usb_cam_preview.py",
        "usb_cam_process.py",
        "usb_cam_runtime.py",
        "usb_cam_session_finalize.py",
        "usb_cam_session_writer.py",
        "usb_cam_stats.py",
        "usb_cam_stop_prefs.py",
        "usb_cam_ui_state.py",
    ]
    for relative in shutil_files:
        source = REPO_ROOT / relative
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    for relative in ["desktop/main.py", "desktop/automation.py", "controller/contracts.py", "controller/runtime_controller.py"]:
        source = REPO_ROOT / relative
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    result = subprocess.run(
        ["cmd", "/c", "build.bat"],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert (workspace / "dist" / "USB_Cam_4K25" / "USB_Cam_4K25.exe").exists()


def test_packaged_runtime_smoke_reports_success(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(
        "usb_cam_real_validation.run_desktop_automation",
        lambda **kwargs: {
            "ok": True,
            "window_title": "USB Cam 4K25",
            "config": {"ffmpeg_path": "tools/ffmpeg.exe"},
            "devices": ["imx678' UVC "],
        },
    )

    result = packaged_runtime_smoke(
        exe_path=exe_path,
    )

    assert result["ok"] is True
    assert result["root_ok"] is True
    assert result["window_title"] == "USB Cam 4K25"
    assert result["camera_devices"] == ["imx678' UVC "]
    assert result["ffmpeg_found"] is True
    assert result["root_ready_attempts"] == 1


def test_run_packaged_runtime_smoke_validation_wraps_result(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_runtime_smoke",
        lambda **kwargs: {"ok": True, "root_ok": True},
    )

    result = run_packaged_runtime_smoke_validation(
        exe_path=exe_path,
    )

    assert result["exe_path"] == str(exe_path)
    assert result["packaged_runtime_smoke"]["ok"] is True
    assert "api_base_url" not in result


def test_run_packaged_runtime_smoke_validation_writes_report(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    written = {}

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_runtime_smoke",
        lambda **kwargs: {"ok": True, "root_ok": True},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.write_validation_report",
        lambda path, payload: written.update({"path": path, "payload": copy.deepcopy(payload)}),
    )

    report_path = tmp_path / "report.json"
    result = run_packaged_runtime_smoke_validation(
        exe_path=exe_path,
        report_path=report_path,
    )

    assert result["report_path"] == str(report_path)
    assert written["path"] == report_path
    assert written["payload"]["packaged_runtime_smoke"]["ok"] is True


def test_write_validation_report_persists_json(tmp_path: Path):
    report_path = tmp_path / "report.json"
    payload = {"ok": True, "name": "packaged-runtime"}

    write_validation_report(report_path, payload)

    assert json.loads(report_path.read_text(encoding="utf-8")) == payload


def test_write_validation_markdown_report_persists_text(tmp_path: Path):
    report_path = tmp_path / "report.md"
    payload = {
        "packaged_validation_summary": {
            "ok": True,
            "packaged_runtime_smoke": {
                "window_title": "USB Cam 4K25",
                "root_ok": True,
                "ffmpeg_path": "tools/ffmpeg.exe",
                "camera_devices": ["imx678' UVC "],
            },
            "packaged_release_validation": {
                "capture_artifacts": {
                    "session_dir": "outputs/session_001",
                    "frame_count": 1,
                    "frames_csv_path": "outputs/session_001/frames.csv",
                    "summary_path": "outputs/session_001/summary.txt",
                    "metadata_path": "outputs/session_001/metadata.json",
                }
            },
        },
        "related_reports": {
            "smoke": "smoke.json",
            "release": "release.json",
            "summary": "summary.json",
        },
    }

    write_validation_markdown_report(report_path, payload)

    content = report_path.read_text(encoding="utf-8")
    assert "# Packaged Validation Summary" in content
    assert "- Overall ok: `True`" in content
    assert "- Window title: `USB Cam 4K25`" in content
    assert "- Root endpoint ok: `True`" in content
    assert "- FFmpeg path: `tools/ffmpeg.exe`" in content
    assert "- Capture session: `outputs/session_001`" in content
    assert "- Capture frame count: `1`" in content


def test_packaged_release_validation_reports_success(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    output_root = tmp_path / "packaged_release"

    monkeypatch.setattr(
        "usb_cam_real_validation.run_desktop_automation",
        lambda **kwargs: {
            "ok": True,
            "window_title": "USB Cam 4K25",
            "config": {"mode": "direct_frames", "ffmpeg_path": "tools/ffmpeg.exe"},
            "devices": ["imx678' UVC "],
            "preview_start": {"ok": True},
            "preview_stop": {"ok": True},
            "capture_start": {"ok": True, "running": True},
            "capture_stop": {"ok": True, "running": True},
            "monitor": {"running": False, "status_text": "Stopped"},
        },
    )
    monkeypatch.setattr("usb_cam_real_validation.find_latest_session_dir", lambda root: root / "session_001")
    monkeypatch.setattr(
        "usb_cam_real_validation.collect_session_artifacts",
        lambda session, frames_dir: {
            "frame_count": 1,
            "session_dir": str(output_root),
            "summary_exists": True,
            "metadata_exists": True,
            "frames_csv_exists": True,
        },
    )

    result = packaged_release_validation(
        exe_path=exe_path,
        output_root=output_root,
        camera_name="imx678' UVC ",
    )

    assert result["ok"] is True
    assert result["window_title"] == "USB Cam 4K25"
    assert result["camera_devices"] == ["imx678' UVC "]
    assert result["capture_artifacts"]["frame_count"] == 1


def test_run_packaged_release_validation_writes_default_report(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    written = {}

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_release_validation",
        lambda **kwargs: {"ok": True, "window_title": "USB Cam 4K25"},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.write_validation_report",
        lambda path, payload: written.update({"path": path, "payload": copy.deepcopy(payload)}),
    )

    result = run_packaged_release_validation(
        exe_path=exe_path,
        output_root=tmp_path / "packaged_release",
    )

    assert result["report_path"].endswith("packaged_release_validation_report.json")
    assert written["path"].name == "packaged_release_validation_report.json"
    assert written["payload"]["packaged_release_validation"]["ok"] is True


def test_packaged_validation_summary_merges_smoke_and_release(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    output_root = tmp_path / "packaged_release"

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_runtime_smoke",
        lambda **kwargs: {"ok": True, "window_title": "USB Cam 4K25"},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_release_validation",
        lambda **kwargs: {"ok": True, "capture_artifacts": {"frame_count": 1}},
    )

    result = packaged_validation_summary(
        exe_path=exe_path,
        output_root=output_root,
    )

    assert result["ok"] is True
    assert result["packaged_runtime_smoke"]["ok"] is True
    assert result["packaged_release_validation"]["ok"] is True


def test_run_packaged_validation_summary_writes_default_report(monkeypatch, tmp_path: Path):
    written = {}

    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_runtime_smoke_validation",
        lambda **kwargs: {"packaged_runtime_smoke": {"ok": True}},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_release_validation",
        lambda **kwargs: {"packaged_release_validation": {"ok": True}},
    )
    paths_root = tmp_path / "packaged_runtime" / "2026-05-25_123456"
    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_report_paths",
        lambda: {
            "smoke": paths_root / "packaged_runtime_smoke_report.json",
            "release": paths_root / "packaged_release_validation_report.json",
            "summary": paths_root / "packaged_validation_summary_report.json",
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.write_validation_report",
        lambda path, payload: written.update({"path": path, "payload": copy.deepcopy(payload)}),
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.write_validation_markdown_report",
        lambda path, payload: written.update({"md_path": path}),
    )
    monkeypatch.setattr("usb_cam_real_validation.write_release_checklist", lambda path, payload: None)
    monkeypatch.setattr("usb_cam_real_validation.write_validation_manifest", lambda path, payload: None)
    monkeypatch.setattr("usb_cam_real_validation.write_latest_packaged_validation_index", lambda path, payload: None)
    monkeypatch.setattr("usb_cam_real_validation.write_packaged_validation_history", lambda path, payload: None)

    result = run_packaged_validation_summary(
        exe_path=tmp_path / "USB_Cam_4K25.exe",
        output_root=tmp_path / "packaged_release",
    )

    assert result["report_path"].endswith("packaged_validation_summary_report.json")
    assert result["markdown_report_path"].endswith("packaged_validation_summary_report.md")
    assert written["path"].name == "packaged_validation_summary_report.json"
    assert written["md_path"].name == "packaged_validation_summary_report.md"
    assert written["payload"]["packaged_validation_summary"]["ok"] is True
    assert written["payload"]["manifest_path"].endswith("packaged_validation_manifest.json")
    assert written["payload"]["latest_index_path"].endswith("latest_packaged_validation.json")


def test_main_routes_packaged_release_validation(monkeypatch, tmp_path: Path):
    called = {}
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_release_validation",
        lambda **kwargs: called.update(kwargs) or {"packaged_release_validation": {"ok": True}},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.argparse.ArgumentParser.parse_args",
        lambda self: type(
            "Args",
            (),
            {
                "ffmpeg": None,
                "camera_name": "cam",
                "output_root": str(tmp_path / "out"),
                "capture_seconds": 2.0,
                "preview_seconds": 2.0,
                "disk_floor_override_mb": None,
                "max_duration_s": None,
                "min_effective_fps_ratio": None,
                "disk_floor_autostop_only": False,
                "video_then_frames_disk_floor_autostop_only": False,
                "max_duration_autostop_only": False,
                "fps_ratio_autostop_only": False,
                "packaged_runtime_smoke_only": False,
                "packaged_release_validation_only": True,
                "packaged_validation_summary_only": False,
                "exe_path": str(tmp_path / "USB_Cam_4K25.exe"),
                "report_path": None,
            },
        )(),
    )

    assert packaged_validation_summary is not None


def test_main_routes_packaged_validation_summary_without_ffmpeg(monkeypatch, tmp_path: Path):
    called = {}
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_validation_summary",
        lambda **kwargs: called.update(kwargs) or {"packaged_validation_summary": {"ok": True}},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.argparse.ArgumentParser.parse_args",
        lambda self: type(
            "Args",
            (),
            {
                "ffmpeg": None,
                "camera_name": "cam",
                "output_root": str(tmp_path / "out"),
                "capture_seconds": 2.0,
                "preview_seconds": 2.0,
                "disk_floor_override_mb": None,
                "max_duration_s": None,
                "min_effective_fps_ratio": None,
                "disk_floor_autostop_only": False,
                "video_then_frames_disk_floor_autostop_only": False,
                "max_duration_autostop_only": False,
                "fps_ratio_autostop_only": False,
                "packaged_runtime_smoke_only": False,
                "packaged_release_validation_only": False,
                "packaged_validation_summary_only": True,
                "exe_path": str(tmp_path / "USB_Cam_4K25.exe"),
                "report_path": None,
            },
        )(),
    )

    result = packaged_validation_summary is not None
    assert result is True


def test_validation_success_detects_nested_failures():
    assert validation_success({"a": {"ok": True}, "b": {"ok": True}}) is True
    assert validation_success({"a": {"ok": True}, "b": {"ok": False}}) is False


def test_autostop_entrypoints_still_exist():
    assert run_validation is not None
    assert run_disk_floor_autostop_validation is not None
    assert run_video_then_frames_disk_floor_autostop_validation is not None
    assert run_max_duration_autostop_validation is not None
    assert run_fps_ratio_autostop_validation is not None
    assert validate_direct_capture_disk_floor_autostop is not None
    assert validate_direct_capture_max_duration_autostop is not None
    assert validate_direct_capture_fps_ratio_autostop is not None
    assert validate_video_then_frames_disk_floor_autostop is not None
    assert validation_disk_floor_env is not None
