import copy
import json
import os
import shutil
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
    assert result['frames_csv_path'] == str(session / 'frames.csv')
    assert result['summary_exists'] is True
    assert result['summary_path'] == str(session / 'summary.txt')
    assert result['metadata_exists'] is True
    assert result['metadata_path'] == str(session / 'metadata.json')
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


@pytest.mark.skipif(sys.platform != "win32", reason="build.bat smoke test is Windows-only")
def test_build_bat_detects_python_and_builds_minimal_script(tmp_path: Path):
    workspace = tmp_path / 'pkg'
    workspace.mkdir()

    src_build = Path(__file__).with_name('build.bat')
    src_build_webview = Path(__file__).with_name('build_webview.bat')
    shutil.copy2(src_build, workspace / 'build.bat')
    shutil.copy2(src_build_webview, workspace / 'build_webview.bat')
    backend_dir = workspace / 'backend'
    backend_dir.mkdir()
    (backend_dir / 'main.py').write_text(
        "print('ok from minimal build script')\n",
        encoding='utf-8',
    )
    ui_dir = workspace / 'ui'
    ui_dir.mkdir(exist_ok=True)
    ui_src = ui_dir / 'src'
    ui_src.mkdir(parents=True, exist_ok=True)
    (ui_src / 'main.tsx').write_text("console.log('ok');\n", encoding='utf-8')
    ui_dist = ui_dir / 'dist'
    ui_dist.mkdir(parents=True, exist_ok=True)
    (ui_dist / 'index.html').write_text('<!doctype html><title>ok</title>', encoding='utf-8')
    (ui_dir / 'package.json').write_text('{"name":"ui","private":true,"scripts":{"build":"echo ok"}}', encoding='utf-8')

    result = subprocess.run(
        ['cmd', '/c', 'build.bat'],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert (workspace / 'dist' / 'USB_Cam_4K25' / 'USB_Cam_4K25.exe').exists()


def test_packaged_runtime_smoke_reports_success(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")

    class FakeProc:
        pid = 4242

    monkeypatch.setattr("usb_cam_real_validation.detect_capture_process_conflicts", lambda: [])
    monkeypatch.setattr("usb_cam_real_validation.subprocess.Popen", lambda *args, **kwargs: FakeProc())
    monkeypatch.setattr("usb_cam_real_validation.time.sleep", lambda _seconds: None)
    monkeypatch.setattr("usb_cam_real_validation.psutil.pid_exists", lambda pid: pid == 4242)
    monkeypatch.setattr("usb_cam_real_validation.read_packaged_window_title", lambda pid: "USB Cam 4K25")
    monkeypatch.setattr(
        "usb_cam_real_validation.requests.get",
        lambda url, timeout: type(
            "Resp",
            (),
            {
                "ok": True,
                "json": lambda self: (
                    {"status": "ok"}
                    if url.endswith("/")
                    else {"ffmpeg_found": True, "ffmpeg_path": "tools/ffmpeg.exe"}
                    if url.endswith("/api/system/ffmpeg-status")
                    else {"devices": ["imx678' UVC "], "selected_device": "imx678' UVC "}
                ),
            },
        )(),
    )

    result = packaged_runtime_smoke(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
    )

    assert result["ok"] is True
    assert result["root_ok"] is True
    assert result["pid"] == 4242
    assert result["window_title"] == "USB Cam 4K25"
    assert result["camera_devices"] == ["imx678' UVC "]
    assert result["ffmpeg_found"] is True
    assert result["root_ready_attempts"] == 1


def test_run_packaged_runtime_smoke_validation_wraps_result(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_runtime_smoke",
        lambda **kwargs: {"ok": True, "pid": 4242, "root_ok": True},
    )

    result = run_packaged_runtime_smoke_validation(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
    )

    assert result["exe_path"] == str(exe_path)
    assert result["api_base_url"] == "http://127.0.0.1:8000"
    assert result["packaged_runtime_smoke"]["ok"] is True


def test_run_packaged_runtime_smoke_validation_writes_report(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    written = {}

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_runtime_smoke",
        lambda **kwargs: {"ok": True, "pid": 4242, "root_ok": True},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.write_validation_report",
        lambda path, payload: written.update({"path": path, "payload": copy.deepcopy(payload)}),
    )

    report_path = tmp_path / "report.json"
    result = run_packaged_runtime_smoke_validation(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        report_path=report_path,
    )

    assert result["report_path"] == str(report_path)
    assert written["path"] == report_path
    assert written["payload"]["packaged_runtime_smoke"]["ok"] is True


def test_packaged_runtime_smoke_requests_process_cleanup(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    stopped = {"called": False}

    class FakeProc:
        pid = 4242

    monkeypatch.setattr("usb_cam_real_validation.detect_capture_process_conflicts", lambda: [])
    monkeypatch.setattr("usb_cam_real_validation.subprocess.Popen", lambda *args, **kwargs: FakeProc())
    monkeypatch.setattr("usb_cam_real_validation.time.sleep", lambda _seconds: None)
    monkeypatch.setattr("usb_cam_real_validation.psutil.pid_exists", lambda pid: pid == 4242)
    monkeypatch.setattr(
        "usb_cam_real_validation.requests.get",
        lambda url, timeout: type("Resp", (), {"ok": True, "json": lambda self: {"status": "ok"}})(),
    )
    monkeypatch.setattr("usb_cam_real_validation.terminate_packaged_runtime", lambda pid: stopped.__setitem__("called", pid == 4242))

    result = packaged_runtime_smoke(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
    )

    assert result["ok"] is True
    assert stopped["called"] is True


def test_packaged_runtime_smoke_waits_for_cleanup_conflicts_to_clear(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    detect_calls = {"count": 0}
    sleep_calls: list[float] = []
    now_values = iter([100.0, 100.1, 100.2, 100.3, 100.4, 100.5, 100.6])

    class FakeProc:
        pid = 4242

    def fake_detect():
        detect_calls["count"] += 1
        if detect_calls["count"] == 1:
            return []
        if detect_calls["count"] == 2:
            return [{"pid": 9001, "name": "ffmpeg.exe", "cmdline": ["ffmpeg.exe"]}]
        return []

    monkeypatch.setattr("usb_cam_real_validation.detect_capture_process_conflicts", fake_detect)
    monkeypatch.setattr("usb_cam_real_validation.subprocess.Popen", lambda *args, **kwargs: FakeProc())
    monkeypatch.setattr("usb_cam_real_validation.time.sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr("usb_cam_real_validation.time.time", lambda: next(now_values))
    monkeypatch.setattr("usb_cam_real_validation.psutil.pid_exists", lambda pid: pid == 4242)
    monkeypatch.setattr("usb_cam_real_validation.read_packaged_window_title", lambda pid: "USB Cam 4K25")
    monkeypatch.setattr(
        "usb_cam_real_validation.requests.get",
        lambda url, timeout: type("Resp", (), {"ok": True, "json": lambda self: {"status": "ok", "devices": []}})(),
    )
    monkeypatch.setattr("usb_cam_real_validation.terminate_packaged_runtime", lambda pid: None)

    result = packaged_runtime_smoke(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        startup_seconds=0.0,
    )

    assert result["ok"] is True
    assert detect_calls["count"] >= 3
    assert 0.25 in sleep_calls


def test_packaged_runtime_smoke_retries_root_until_ready(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    request_calls = {"root": 0}
    sleep_calls: list[float] = []
    clock = {"now": 100.0}

    class FakeProc:
        pid = 4242

    def fake_time():
        clock["now"] += 0.1
        return clock["now"]

    def fake_get(url, timeout):
        if url.endswith("/"):
            request_calls["root"] += 1
            if request_calls["root"] < 3:
                raise requests.exceptions.ConnectionError("not ready")
            return type("Resp", (), {"ok": True, "json": lambda self: {"status": "ok"}})()
        if url.endswith("/api/system/ffmpeg-status"):
            return type("Resp", (), {"ok": True, "json": lambda self: {"ffmpeg_found": True, "ffmpeg_path": "tools/ffmpeg.exe"}})()
        return type("Resp", (), {"ok": True, "json": lambda self: {"devices": ["imx678' UVC "], "selected_device": "imx678' UVC "}})()

    monkeypatch.setattr("usb_cam_real_validation.detect_capture_process_conflicts", lambda: [])
    monkeypatch.setattr("usb_cam_real_validation.subprocess.Popen", lambda *args, **kwargs: FakeProc())
    monkeypatch.setattr("usb_cam_real_validation.time.sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr("usb_cam_real_validation.time.time", fake_time)
    monkeypatch.setattr("usb_cam_real_validation.psutil.pid_exists", lambda pid: pid == 4242)
    monkeypatch.setattr("usb_cam_real_validation.read_packaged_window_title", lambda pid: "USB Cam 4K25")
    monkeypatch.setattr("usb_cam_real_validation.requests.get", fake_get)
    monkeypatch.setattr("usb_cam_real_validation.terminate_packaged_runtime", lambda pid: None)
    monkeypatch.setattr("usb_cam_real_validation.wait_for_capture_process_conflicts_to_clear", lambda **kwargs: [])

    result = packaged_runtime_smoke(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        startup_seconds=1.5,
    )

    assert result["ok"] is True
    assert result["root_ready_attempts"] == 3
    assert result["root_ready_seconds"] > 0
    assert 0.5 in sleep_calls


def test_terminate_packaged_runtime_kills_child_processes(monkeypatch):
    events = []

    class FakeChild:
        def terminate(self):
            events.append("child-terminate")

        def wait(self, timeout=None):
            events.append(("child-wait", timeout))

        def kill(self):
            events.append("child-kill")

    class FakeParent:
        def children(self, recursive=False):
            events.append(("children", recursive))
            return [FakeChild()]

        def terminate(self):
            events.append("parent-terminate")

        def wait(self, timeout=None):
            events.append(("parent-wait", timeout))

        def kill(self):
            events.append("parent-kill")

    monkeypatch.setattr("usb_cam_real_validation.psutil.Process", lambda pid: FakeParent())
    monkeypatch.setattr("usb_cam_real_validation.psutil.TimeoutExpired", RuntimeError)

    from usb_cam_real_validation import terminate_packaged_runtime

    terminate_packaged_runtime(4242)

    assert ("children", True) in events
    assert "child-terminate" in events
    assert ("child-wait", 5) in events
    assert "parent-terminate" in events
    assert ("parent-wait", 5) in events


def test_run_packaged_runtime_smoke_validation_uses_default_report_path(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    written = {}

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_runtime_smoke",
        lambda **kwargs: {"ok": True, "pid": 4242, "root_ok": True},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.write_validation_report",
        lambda path, payload: written.update({"path": path, "payload": copy.deepcopy(payload)}),
    )

    result = run_packaged_runtime_smoke_validation(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
    )

    assert result["report_path"].endswith("packaged_runtime_smoke_report.json")
    assert written["path"].name == "packaged_runtime_smoke_report.json"
    assert written["path"].parent.parent.name == "packaged_runtime"


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
    assert "- Camera devices: `[\"imx678' UVC \"]`" in content or "- Camera devices: `['imx678' UVC ']`" in content
    assert "- Capture session: `outputs/session_001`" in content
    assert "- Capture frame count: `1`" in content
    assert "- Frames CSV: `outputs/session_001/frames.csv`" in content
    assert "- Session summary: `outputs/session_001/summary.txt`" in content
    assert "- Session metadata: `outputs/session_001/metadata.json`" in content
    assert "smoke.json" in content


def test_packaged_release_validation_reports_success(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    output_root = tmp_path / "packaged_release"
    runtime_state = {"alive": False}

    class FakeProc:
        pid = 5151

    monkeypatch.setattr("usb_cam_real_validation.detect_capture_process_conflicts", lambda: [])
    monkeypatch.setattr("usb_cam_real_validation.subprocess.Popen", lambda *args, **kwargs: FakeProc())
    monkeypatch.setattr("usb_cam_real_validation.time.sleep", lambda _seconds: None)
    monkeypatch.setattr("usb_cam_real_validation.psutil.pid_exists", lambda pid: pid == 5151)
    monkeypatch.setattr("usb_cam_real_validation.read_packaged_window_title", lambda pid: "USB Cam 4K25")

    responses = {
        "http://127.0.0.1:8000/": {"status": "ok"},
        "http://127.0.0.1:8000/api/config": {"mode": "direct_frames"},
        "http://127.0.0.1:8000/api/devices/cameras": {"devices": ["imx678' UVC "], "selected_device": "imx678' UVC "},
        "http://127.0.0.1:8000/api/system/ffmpeg-status": {"ffmpeg_found": True, "ffmpeg_path": "tools/ffmpeg.exe"},
        "http://127.0.0.1:8000/api/monitor": {"status_text": "Capture completed: 1 frames."},
        "http://127.0.0.1:8000/api/preview/start": {"ok": True},
        "http://127.0.0.1:8000/api/preview/stop": {"ok": True},
        "http://127.0.0.1:8000/api/control/start": {"ok": True, "running": True},
        "http://127.0.0.1:8000/api/control/stop": {"ok": True, "running": True},
    }

    def fake_get(url, timeout):
        assert runtime_state["alive"] is True
        payload = responses[url]
        return type("Resp", (), {"ok": True, "json": lambda self, payload=payload: payload})()

    def fake_post(url, timeout=None, headers=None, data=None):
        assert runtime_state["alive"] is True
        payload = responses[url]
        return type("Resp", (), {"ok": True, "json": lambda self, payload=payload: payload})()

    monkeypatch.setattr("usb_cam_real_validation.requests.get", fake_get)
    monkeypatch.setattr("usb_cam_real_validation.requests.post", fake_post)
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
    monkeypatch.setattr("usb_cam_real_validation.find_latest_session_dir", lambda root: root / "session_001")
    monkeypatch.setattr(
        "usb_cam_real_validation.launch_packaged_runtime",
        lambda **kwargs: runtime_state.__setitem__("alive", True) or {"ok": True, "pid": 5151, "alive": True, "window_title": "USB Cam 4K25"},
    )
    monkeypatch.setattr("usb_cam_real_validation.terminate_packaged_runtime", lambda pid: runtime_state.__setitem__("alive", False))

    result = packaged_release_validation(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        output_root=output_root,
        camera_name="imx678' UVC ",
    )

    assert result["ok"] is True
    assert result["window_title"] == "USB Cam 4K25"
    assert result["camera_devices"] == ["imx678' UVC "]
    assert result["capture_artifacts"]["frame_count"] == 1


def test_packaged_release_validation_waits_for_finalized_artifacts(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    output_root = tmp_path / "packaged_release"
    runtime_state = {"alive": False}
    artifact_calls = {"count": 0}

    responses = {
        "http://127.0.0.1:8000/": {"status": "ok"},
        "http://127.0.0.1:8000/api/config": {"mode": "direct_frames"},
        "http://127.0.0.1:8000/api/devices/cameras": {"devices": ["imx678' UVC "], "selected_device": "imx678' UVC "},
        "http://127.0.0.1:8000/api/system/ffmpeg-status": {"ffmpeg_found": True, "ffmpeg_path": "tools/ffmpeg.exe"},
        "http://127.0.0.1:8000/api/monitor": {"status_text": "Capture completed: 60 frames."},
        "http://127.0.0.1:8000/api/preview/start": {"ok": True},
        "http://127.0.0.1:8000/api/preview/stop": {"ok": True},
        "http://127.0.0.1:8000/api/control/start": {"ok": True, "running": True},
        "http://127.0.0.1:8000/api/control/stop": {"ok": True, "running": True},
    }

    def fake_get(url, timeout):
        assert runtime_state["alive"] is True
        payload = responses[url]
        return type("Resp", (), {"ok": True, "json": lambda self, payload=payload: payload})()

    def fake_post(url, timeout=None, headers=None, data=None):
        assert runtime_state["alive"] is True
        payload = responses[url]
        return type("Resp", (), {"ok": True, "json": lambda self, payload=payload: payload})()

    def fake_collect(session, frames_dir):
        artifact_calls["count"] += 1
        if artifact_calls["count"] == 1:
            return {
                "session_dir": str(output_root),
                "frame_count": 60,
                "summary_exists": False,
                "metadata_exists": False,
                "frames_csv_exists": False,
                "video_files": [],
            }
        return {
            "session_dir": str(output_root),
            "frame_count": 60,
            "summary_exists": True,
            "metadata_exists": True,
            "frames_csv_exists": True,
            "video_files": [],
        }

    monkeypatch.setattr("usb_cam_real_validation.requests.get", fake_get)
    monkeypatch.setattr("usb_cam_real_validation.requests.post", fake_post)
    monkeypatch.setattr("usb_cam_real_validation.find_latest_session_dir", lambda root: root / "session_001")
    monkeypatch.setattr("usb_cam_real_validation.collect_session_artifacts", fake_collect)
    monkeypatch.setattr(
        "usb_cam_real_validation.launch_packaged_runtime",
        lambda **kwargs: runtime_state.__setitem__("alive", True) or {"ok": True, "pid": 5151, "alive": True, "window_title": "USB Cam 4K25"},
    )
    monkeypatch.setattr("usb_cam_real_validation.terminate_packaged_runtime", lambda pid: runtime_state.__setitem__("alive", False))
    monkeypatch.setattr("usb_cam_real_validation.time.sleep", lambda _seconds: None)

    result = packaged_release_validation(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        output_root=output_root,
        camera_name="imx678' UVC ",
    )

    assert artifact_calls["count"] >= 2
    assert result["ok"] is True
    assert result["capture_artifacts"]["summary_exists"] is True
    assert result["capture_artifacts"]["metadata_exists"] is True


def test_packaged_release_validation_waits_for_terminal_monitor_state(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    output_root = tmp_path / "packaged_release"
    runtime_state = {"alive": False, "monitor_reads": 0}

    responses = {
        "http://127.0.0.1:8000/": {"status": "ok"},
        "http://127.0.0.1:8000/api/config": {"mode": "direct_frames"},
        "http://127.0.0.1:8000/api/devices/cameras": {"devices": ["imx678' UVC "], "selected_device": "imx678' UVC "},
        "http://127.0.0.1:8000/api/system/ffmpeg-status": {"ffmpeg_found": True, "ffmpeg_path": "tools/ffmpeg.exe"},
        "http://127.0.0.1:8000/api/preview/start": {"ok": True},
        "http://127.0.0.1:8000/api/preview/stop": {"ok": True},
        "http://127.0.0.1:8000/api/control/start": {"ok": True, "running": True},
        "http://127.0.0.1:8000/api/control/stop": {"ok": True, "running": True},
    }

    def fake_get(url, timeout):
        assert runtime_state["alive"] is True
        if url == "http://127.0.0.1:8000/api/monitor":
            runtime_state["monitor_reads"] += 1
            payload = (
                {"running": True, "capture_phase": "stopping", "status_text": "Stopping capture..."}
                if runtime_state["monitor_reads"] == 1
                else {"running": False, "capture_phase": "idle", "status_text": "Stopped"}
            )
            return type("Resp", (), {"ok": True, "json": lambda self, payload=payload: payload})()
        payload = responses[url]
        return type("Resp", (), {"ok": True, "json": lambda self, payload=payload: payload})()

    def fake_post(url, timeout=None, headers=None, data=None):
        assert runtime_state["alive"] is True
        payload = responses[url]
        return type("Resp", (), {"ok": True, "json": lambda self, payload=payload: payload})()

    monkeypatch.setattr("usb_cam_real_validation.requests.get", fake_get)
    monkeypatch.setattr("usb_cam_real_validation.requests.post", fake_post)
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
    monkeypatch.setattr(
        "usb_cam_real_validation.launch_packaged_runtime",
        lambda **kwargs: runtime_state.__setitem__("alive", True) or {"ok": True, "pid": 5151, "alive": True, "window_title": "USB Cam 4K25"},
    )
    monkeypatch.setattr("usb_cam_real_validation.terminate_packaged_runtime", lambda pid: runtime_state.__setitem__("alive", False))
    monkeypatch.setattr("usb_cam_real_validation.time.sleep", lambda _seconds: None)

    result = packaged_release_validation(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        output_root=output_root,
        camera_name="imx678' UVC ",
    )

    assert runtime_state["monitor_reads"] >= 2
    assert result["monitor"]["running"] is False
    assert result["monitor"]["status_text"] == "Stopped"


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
        api_base_url="http://127.0.0.1:8000",
        output_root=tmp_path / "packaged_release",
    )

    assert result["report_path"].endswith("packaged_release_validation_report.json")
    assert written["path"].name == "packaged_release_validation_report.json"
    assert written["path"].parent.parent.name == "packaged_runtime"
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
        api_base_url="http://127.0.0.1:8000",
        output_root=output_root,
        camera_name="USB Camera",
    )

    assert result["ok"] is True
    assert result["packaged_runtime_smoke"]["ok"] is True
    assert result["packaged_release_validation"]["ok"] is True


def test_run_packaged_validation_summary_writes_default_report(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    written = {}
    paths_root = tmp_path / "packaged_runtime" / "2026-05-25_123456"

    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_runtime_smoke_validation",
        lambda **kwargs: {"packaged_runtime_smoke": {"ok": True}},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_release_validation",
        lambda **kwargs: {"packaged_release_validation": {"ok": True}},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_report_paths",
        lambda base_dir=Path("outputs") / "packaged_runtime": {
            "root": paths_root,
            "smoke": paths_root / "packaged_runtime_smoke_report.json",
            "release": paths_root / "packaged_release_validation_report.json",
            "summary": paths_root / "packaged_validation_summary_report.json",
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.write_validation_report",
        lambda path, payload: written.update({"path": path, "payload": payload}),
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.write_validation_markdown_report",
        lambda path, payload: written.update({"md_path": path, "md_payload": payload}),
    )

    result = run_packaged_validation_summary(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        output_root=tmp_path / "packaged_release",
    )

    assert result["report_path"].endswith("packaged_validation_summary_report.json")
    assert result["markdown_report_path"].endswith("packaged_validation_summary_report.md")
    assert result["manifest_path"].endswith("packaged_validation_manifest.json")
    assert result["latest_index_path"].endswith("latest_packaged_validation.json")
    assert result["history_index_path"].endswith("packaged_validation_history.json")
    assert written["path"].name == "packaged_validation_summary_report.json"
    assert written["md_path"].name == "packaged_validation_summary_report.md"
    assert written["payload"]["report_path"].endswith("packaged_validation_summary_report.json")
    assert written["payload"]["markdown_report_path"].endswith("packaged_validation_summary_report.md")
    assert written["payload"]["manifest_path"].endswith("packaged_validation_manifest.json")
    assert written["payload"]["latest_index_path"].endswith("latest_packaged_validation.json")
    assert written["payload"]["history_index_path"].endswith("packaged_validation_history.json")
    assert written["payload"]["packaged_validation_summary"]["ok"] is True


def test_run_packaged_validation_summary_includes_related_report_paths(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    written = {}
    paths_root = tmp_path / "packaged_runtime" / "2026-05-25_123456"

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_report_paths",
        lambda base_dir=Path("outputs") / "packaged_runtime": {
            "root": paths_root,
            "smoke": paths_root / "packaged_runtime_smoke_report.json",
            "release": paths_root / "packaged_release_validation_report.json",
            "summary": paths_root / "packaged_validation_summary_report.json",
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_runtime_smoke_validation",
        lambda **kwargs: {"packaged_runtime_smoke": {"ok": True}},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_release_validation",
        lambda **kwargs: {"packaged_release_validation": {"ok": True}},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.write_validation_report",
        lambda path, payload: written.update({"path": path, "payload": payload}),
    )

    result = run_packaged_validation_summary(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        output_root=tmp_path / "packaged_release",
    )

    assert result["related_reports"]["smoke"].endswith("packaged_runtime_smoke_report.json")
    assert result["related_reports"]["release"].endswith("packaged_release_validation_report.json")
    assert written["payload"]["related_reports"]["summary"].endswith("packaged_validation_summary_report.json")


def test_run_packaged_validation_summary_generates_child_reports(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    calls = {"smoke": None, "release": None, "summary": None}
    paths_root = tmp_path / "packaged_runtime" / "2026-05-25_123456"

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_report_paths",
        lambda base_dir=Path("outputs") / "packaged_runtime": {
            "root": paths_root,
            "smoke": paths_root / "packaged_runtime_smoke_report.json",
            "release": paths_root / "packaged_release_validation_report.json",
            "summary": paths_root / "packaged_validation_summary_report.json",
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_runtime_smoke_validation",
        lambda **kwargs: calls.__setitem__("smoke", kwargs) or {"packaged_runtime_smoke": {"ok": True}},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_release_validation",
        lambda **kwargs: calls.__setitem__("release", kwargs) or {"packaged_release_validation": {"ok": True}},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.write_validation_report",
        lambda path, payload: calls.__setitem__("summary", {"path": path, "payload": payload}),
    )

    result = run_packaged_validation_summary(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        output_root=tmp_path / "packaged_release",
    )

    assert calls["smoke"]["report_path"].name == "packaged_runtime_smoke_report.json"
    assert calls["release"]["report_path"].name == "packaged_release_validation_report.json"
    assert calls["summary"]["path"].name == "packaged_validation_summary_report.json"
    assert result["packaged_validation_summary"]["ok"] is True


def test_run_packaged_validation_summary_aligns_child_reports_with_explicit_report_path(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    calls = {"smoke": None, "release": None}
    report_path = tmp_path / "custom_run" / "packaged_validation_summary_report.json"
    paths_root = tmp_path / "packaged_runtime" / "2026-05-25_123456"

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_report_paths",
        lambda base_dir=Path("outputs") / "packaged_runtime": {
            "root": paths_root,
            "smoke": paths_root / "packaged_runtime_smoke_report.json",
            "release": paths_root / "packaged_release_validation_report.json",
            "summary": paths_root / "packaged_validation_summary_report.json",
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_runtime_smoke_validation",
        lambda **kwargs: calls.__setitem__("smoke", kwargs) or {"packaged_runtime_smoke": {"ok": True}},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_release_validation",
        lambda **kwargs: calls.__setitem__("release", kwargs) or {"packaged_release_validation": {"ok": True}},
    )
    monkeypatch.setattr("usb_cam_real_validation.write_validation_report", lambda path, payload: None)
    monkeypatch.setattr("usb_cam_real_validation.write_validation_markdown_report", lambda path, payload: None)
    monkeypatch.setattr("usb_cam_real_validation.write_validation_manifest", lambda path, payload: calls.__setitem__("manifest", {"path": path, "payload": payload}))

    result = run_packaged_validation_summary(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        output_root=tmp_path / "packaged_release",
        report_path=report_path,
    )

    assert calls["smoke"]["report_path"] == report_path.with_name("packaged_runtime_smoke_report.json")
    assert calls["release"]["report_path"] == report_path.with_name("packaged_release_validation_report.json")
    assert result["related_reports"]["smoke"] == str(report_path.with_name("packaged_runtime_smoke_report.json"))
    assert result["related_reports"]["release"] == str(report_path.with_name("packaged_release_validation_report.json"))
    assert result["report_path"] == str(report_path)
    assert result["manifest_path"] == str(report_path.with_name("packaged_validation_manifest.json"))
    assert calls["manifest"]["path"] == report_path.with_name("packaged_validation_manifest.json")


def test_write_validation_manifest_persists_index(tmp_path: Path):
    manifest_path = tmp_path / "packaged_validation_manifest.json"
    payload = {
        "run_id": "2026-05-25_123456",
        "run_dir": str(tmp_path),
        "summary_report": "summary.json",
        "summary_markdown": "summary.md",
        "smoke_report": "smoke.json",
        "release_report": "release.json",
        "capture_session_dir": "session_dir",
    }

    from usb_cam_real_validation import write_validation_manifest

    write_validation_manifest(manifest_path, payload)

    assert json.loads(manifest_path.read_text(encoding="utf-8")) == payload


def test_write_latest_packaged_validation_index_persists_json(tmp_path: Path):
    latest_path = tmp_path / "latest_packaged_validation.json"
    payload = {
        "run_id": "2026-05-25_123456",
        "run_dir": str(tmp_path / "2026-05-25_123456"),
        "summary_report": "summary.json",
        "manifest_path": "manifest.json",
        "checklist_path": "checklist.md",
    }

    from usb_cam_real_validation import write_latest_packaged_validation_index

    write_latest_packaged_validation_index(latest_path, payload)

    assert json.loads(latest_path.read_text(encoding="utf-8")) == payload


def test_write_packaged_validation_history_persists_recent_runs(tmp_path: Path):
    history_path = tmp_path / "packaged_validation_history.json"
    summary_a = tmp_path / "summary_120000.json"
    summary_b = tmp_path / "summary_121000.json"
    summary_a.write_text("{}", encoding="utf-8")
    summary_b.write_text("{}", encoding="utf-8")
    entries = [
        {
            "run_id": "2026-05-25_120000",
            "summary_report": str(summary_a),
            "release_gate": "ready",
            "root_ready_seconds": 0.5,
            "frame_count": 60,
            "total_frame_size_bytes": 1234,
        },
        {
            "run_id": "2026-05-25_121000",
            "summary_report": str(summary_b),
            "release_gate": "warning",
            "root_ready_seconds": 3.5,
            "frame_count": 42,
            "total_frame_size_bytes": 999,
        },
    ]

    from usb_cam_real_validation import write_packaged_validation_history

    write_packaged_validation_history(history_path, entries)

    assert json.loads(history_path.read_text(encoding="utf-8")) == {"runs": entries}


def test_run_packaged_validation_summary_history_includes_comparison_metrics(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    output_root = tmp_path / "packaged_release"

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_report_paths",
        lambda base_dir=Path("outputs") / "packaged_runtime": {
            "root": tmp_path / "packaged_runtime" / "2026-05-25_123456",
            "smoke": tmp_path / "packaged_runtime" / "2026-05-25_123456" / "packaged_runtime_smoke_report.json",
            "release": tmp_path / "packaged_runtime" / "2026-05-25_123456" / "packaged_release_validation_report.json",
            "summary": tmp_path / "packaged_runtime" / "2026-05-25_123456" / "packaged_validation_summary_report.json",
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_runtime_smoke_validation",
        lambda **kwargs: {
            "packaged_runtime_smoke": {
                "ok": True,
                "window_title": "USB_Cam_4K25.exe",
                "root_ok": True,
                "root_ready_attempts": 2,
                "root_ready_seconds": 0.75,
                "ffmpeg_path": "tools/ffmpeg.exe",
                "camera_devices": ["imx678' UVC"],
            }
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_release_validation",
        lambda **kwargs: {
            "packaged_release_validation": {
                "ok": True,
                "capture_artifacts": {
                    "session_dir": str(output_root / "session_001"),
                    "frame_count": 60,
                    "total_frame_size_bytes": 1234,
                    "frames_csv_path": str(output_root / "session_001" / "frames.csv"),
                    "summary_path": str(output_root / "session_001" / "summary.txt"),
                    "metadata_path": str(output_root / "session_001" / "metadata.json"),
                }
            }
        },
    )

    result = run_packaged_validation_summary(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        output_root=output_root,
    )

    history = json.loads(Path(result["history_index_path"]).read_text(encoding="utf-8"))
    latest = history["runs"][0]

    assert latest["root_ready_attempts"] == 2
    assert latest["root_ready_seconds"] == 0.75
    assert latest["frame_count"] == 60
    assert latest["total_frame_size_bytes"] == 1234


def test_write_packaged_validation_history_persists_deltas(tmp_path: Path):
    history_path = tmp_path / "packaged_validation_history.json"
    summary_path = tmp_path / "summary_121000.json"
    summary_path.write_text("{}", encoding="utf-8")
    entries = [
        {
            "run_id": "2026-05-25_121000",
            "summary_report": str(summary_path),
            "release_gate": "warning",
            "root_ready_seconds": 3.5,
            "frame_count": 42,
            "total_frame_size_bytes": 999,
            "delta": {
                "root_ready_seconds": -2.75,
                "frame_count": 18,
                "total_frame_size_bytes": 235,
            },
        }
    ]

    from usb_cam_real_validation import write_packaged_validation_history

    write_packaged_validation_history(history_path, entries)

    payload = json.loads(history_path.read_text(encoding="utf-8"))
    assert payload["runs"][0]["delta"]["root_ready_seconds"] == -2.75
    assert payload["runs"][0]["delta"]["frame_count"] == 18


def test_run_packaged_validation_summary_history_includes_delta_against_previous_run(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    output_root = tmp_path / "packaged_release"
    history_dir = tmp_path / "packaged_runtime"
    history_dir.mkdir(exist_ok=True)
    (history_dir / "packaged_validation_history.json").write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "2026-05-25_120000",
                        "release_gate": "ready",
                        "root_ready_attempts": 1,
                        "root_ready_seconds": 1.25,
                        "frame_count": 55,
                        "total_frame_size_bytes": 1000,
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_report_paths",
        lambda base_dir=Path("outputs") / "packaged_runtime": {
            "root": history_dir / "2026-05-25_123456",
            "smoke": history_dir / "2026-05-25_123456" / "packaged_runtime_smoke_report.json",
            "release": history_dir / "2026-05-25_123456" / "packaged_release_validation_report.json",
            "summary": history_dir / "2026-05-25_123456" / "packaged_validation_summary_report.json",
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_runtime_smoke_validation",
        lambda **kwargs: {
            "packaged_runtime_smoke": {
                "ok": True,
                "window_title": "USB_Cam_4K25.exe",
                "root_ok": True,
                "root_ready_attempts": 2,
                "root_ready_seconds": 0.75,
                "ffmpeg_path": "tools/ffmpeg.exe",
                "camera_devices": ["imx678' UVC"],
            }
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_release_validation",
        lambda **kwargs: {
            "packaged_release_validation": {
                "ok": True,
                "capture_artifacts": {
                    "session_dir": str(output_root / "session_001"),
                    "frame_count": 60,
                    "total_frame_size_bytes": 1234,
                    "frames_csv_path": str(output_root / "session_001" / "frames.csv"),
                    "summary_path": str(output_root / "session_001" / "summary.txt"),
                    "metadata_path": str(output_root / "session_001" / "metadata.json"),
                }
            }
        },
    )

    result = run_packaged_validation_summary(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        output_root=output_root,
    )

    history = json.loads(Path(result["history_index_path"]).read_text(encoding="utf-8"))
    latest = history["runs"][0]

    assert latest["delta"]["root_ready_attempts"] == 1
    assert latest["delta"]["root_ready_seconds"] == -0.5
    assert latest["delta"]["frame_count"] == 5
    assert latest["delta"]["total_frame_size_bytes"] == 234

    latest_index = json.loads((history_dir / "latest_packaged_validation.json").read_text(encoding="utf-8"))
    assert latest_index["delta"]["root_ready_attempts"] == 1
    assert latest_index["delta"]["root_ready_seconds"] == -0.5
    assert latest_index["delta"]["frame_count"] == 5

    summary_markdown = Path(result["markdown_report_path"]).read_text(encoding="utf-8")
    assert "## Run Delta" in summary_markdown
    assert "- Delta root ready seconds vs previous run: `-0.5`" in summary_markdown
    assert "- Delta frame count vs previous run: `5`" in summary_markdown
    assert "## Comparison Baseline" in summary_markdown
    assert "- Comparison baseline run: `2026-05-25_120000`" in summary_markdown
    assert "- Skipped runs before baseline: `[]`" in summary_markdown

    checklist_markdown = Path(result["checklist_path"]).read_text(encoding="utf-8")
    assert "## Run Delta" in checklist_markdown
    assert "- Root ready seconds vs previous run: `-0.5`" in checklist_markdown
    assert "- Frame count vs previous run: `5`" in checklist_markdown
    assert "## Comparison Baseline" in checklist_markdown
    assert "- Selected run: `2026-05-25_120000`" in checklist_markdown
    assert "- Skipped runs: `[]`" in checklist_markdown


def test_run_packaged_validation_summary_history_skips_non_comparable_previous_run(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    output_root = tmp_path / "packaged_release"
    history_dir = tmp_path / "packaged_runtime"
    history_dir.mkdir(exist_ok=True)
    invalid_dir = history_dir / "2026-05-25_120500"
    valid_dir = history_dir / "2026-05-25_120000"
    valid_dir.mkdir(parents=True, exist_ok=True)
    (valid_dir / "packaged_validation_summary_report.json").write_text("{}", encoding="utf-8")
    (history_dir / "packaged_validation_history.json").write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "2026-05-25_120500",
                        "run_dir": str(invalid_dir),
                        "summary_report": str(invalid_dir / "packaged_validation_summary_report.json"),
                        "release_gate": "ready",
                        "root_ready_attempts": None,
                        "root_ready_seconds": None,
                        "frame_count": None,
                        "total_frame_size_bytes": None,
                    },
                    {
                        "run_id": "2026-05-25_120000",
                        "run_dir": str(valid_dir),
                        "summary_report": str(valid_dir / "packaged_validation_summary_report.json"),
                        "release_gate": "ready",
                        "root_ready_attempts": 1,
                        "root_ready_seconds": 1.25,
                        "frame_count": 55,
                        "total_frame_size_bytes": 1000,
                    },
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_report_paths",
        lambda base_dir=Path("outputs") / "packaged_runtime": {
            "root": history_dir / "2026-05-25_123456",
            "smoke": history_dir / "2026-05-25_123456" / "packaged_runtime_smoke_report.json",
            "release": history_dir / "2026-05-25_123456" / "packaged_release_validation_report.json",
            "summary": history_dir / "2026-05-25_123456" / "packaged_validation_summary_report.json",
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_runtime_smoke_validation",
        lambda **kwargs: {
            "packaged_runtime_smoke": {
                "ok": True,
                "window_title": "USB_Cam_4K25.exe",
                "root_ok": True,
                "root_ready_attempts": 2,
                "root_ready_seconds": 0.75,
                "ffmpeg_path": "tools/ffmpeg.exe",
                "camera_devices": ["imx678' UVC"],
            }
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_release_validation",
        lambda **kwargs: {
            "packaged_release_validation": {
                "ok": True,
                "capture_artifacts": {
                    "session_dir": str(output_root / "session_001"),
                    "frame_count": 60,
                    "total_frame_size_bytes": 1234,
                    "frames_csv_path": str(output_root / "session_001" / "frames.csv"),
                    "summary_path": str(output_root / "session_001" / "summary.txt"),
                    "metadata_path": str(output_root / "session_001" / "metadata.json"),
                }
            }
        },
    )

    result = run_packaged_validation_summary(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        output_root=output_root,
    )

    latest = json.loads(Path(result["history_index_path"]).read_text(encoding="utf-8"))["runs"][0]

    assert latest["delta"]["root_ready_attempts"] == 1
    assert latest["delta"]["root_ready_seconds"] == -0.5
    assert latest["delta"]["frame_count"] == 5
    assert latest["delta"]["total_frame_size_bytes"] == 234
    assert latest["comparison_baseline"]["selected_run_id"] == "2026-05-25_120000"
    assert latest["comparison_baseline"]["skipped_run_ids"] == ["2026-05-25_120500"]


def test_write_packaged_validation_history_drops_entries_without_summary_paths(tmp_path: Path):
    history_path = tmp_path / "packaged_validation_history.json"
    valid_dir = tmp_path / "2026-05-25_120000"
    valid_dir.mkdir(parents=True, exist_ok=True)
    valid_summary = valid_dir / "packaged_validation_summary_report.json"
    valid_summary.write_text("{}", encoding="utf-8")
    entries = [
        {
            "run_id": "2026-05-25_120500",
            "run_dir": "outputs\\packaged_runtime\\2026-05-25_120500",
            "summary_report": "outputs\\packaged_runtime\\2026-05-25_120500\\packaged_validation_summary_report.json",
            "root_ready_attempts": None,
            "root_ready_seconds": None,
            "frame_count": None,
            "total_frame_size_bytes": None,
        },
        {
            "run_id": "2026-05-25_120000",
            "run_dir": str(valid_dir),
            "summary_report": str(valid_summary),
            "manifest_path": str(valid_dir / "packaged_validation_manifest.json"),
            "checklist_path": str(valid_dir / "packaged_release_checklist.md"),
            "root_ready_attempts": 1,
            "root_ready_seconds": 1.25,
            "frame_count": 55,
            "total_frame_size_bytes": 1000,
        },
    ]

    from usb_cam_real_validation import write_packaged_validation_history

    write_packaged_validation_history(history_path, entries)

    payload = json.loads(history_path.read_text(encoding="utf-8"))
    assert [run["run_id"] for run in payload["runs"]] == ["2026-05-25_120000"]


def test_run_packaged_validation_summary_manifest_includes_key_metrics(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    output_root = tmp_path / "packaged_release"

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_report_paths",
        lambda base_dir=Path("outputs") / "packaged_runtime": {
            "root": tmp_path / "packaged_runtime" / "2026-05-25_123456",
            "smoke": tmp_path / "packaged_runtime" / "2026-05-25_123456" / "packaged_runtime_smoke_report.json",
            "release": tmp_path / "packaged_runtime" / "2026-05-25_123456" / "packaged_release_validation_report.json",
            "summary": tmp_path / "packaged_runtime" / "2026-05-25_123456" / "packaged_validation_summary_report.json",
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_runtime_smoke_validation",
        lambda **kwargs: {
            "packaged_runtime_smoke": {
                "ok": True,
                "window_title": "USB_Cam_4K25.exe",
                "root_ok": True,
                "root_ready_attempts": 2,
                "root_ready_seconds": 0.75,
                "ffmpeg_path": "tools/ffmpeg.exe",
                "camera_devices": ["imx678' UVC"],
            }
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_release_validation",
        lambda **kwargs: {
            "packaged_release_validation": {
                "ok": True,
                "capture_artifacts": {
                    "session_dir": str(output_root / "session_001"),
                    "frame_count": 60,
                    "total_frame_size_bytes": 1234,
                    "frames_csv_path": str(output_root / "session_001" / "frames.csv"),
                    "summary_path": str(output_root / "session_001" / "summary.txt"),
                    "metadata_path": str(output_root / "session_001" / "metadata.json"),
                }
            }
        },
    )

    result = run_packaged_validation_summary(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        output_root=output_root,
    )

    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["run_id"] == "2026-05-25_123456"
    assert manifest["overall_ok"] is True
    assert manifest["release_gate"] == "ready"
    assert manifest["gate_policy"]["warning_root_ready_attempts"] == 4
    assert manifest["gate_policy"]["warning_root_ready_seconds"] == 3.0
    assert manifest["release_checklist"].endswith("packaged_release_checklist.md")
    assert manifest["exe_path"] == str(exe_path)
    assert manifest["window_title"] == "USB_Cam_4K25.exe"
    assert manifest["root_ready_attempts"] == 2
    assert manifest["root_ready_seconds"] == 0.75
    assert manifest["frame_count"] == 60
    assert manifest["total_frame_size_bytes"] == 1234
    assert manifest["summary_report"].endswith("packaged_validation_summary_report.json")
    assert manifest["summary_markdown"].endswith("packaged_validation_summary_report.md")
    assert manifest["smoke_report"].endswith("packaged_runtime_smoke_report.json")
    assert manifest["release_report"].endswith("packaged_release_validation_report.json")
    assert manifest["report_sizes"]["summary_report_bytes"] is not None


def test_write_validation_markdown_report_includes_gate_context(tmp_path: Path):
    report_path = tmp_path / "report.md"
    payload = {
        "packaged_validation_summary": {
            "ok": True,
            "packaged_runtime_smoke": {
                "window_title": "USB Cam 4K25",
                "root_ok": True,
                "root_ready_attempts": 1,
                "root_ready_seconds": 0.5,
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
        "release_gate": "ready",
        "release_gate_reasons": [],
        "checklist_path": "checklist.md",
        "gate_policy": {
            "warning_root_ready_attempts": 4,
            "warning_root_ready_seconds": 3.0,
        },
        "latest_index_path": "latest.json",
        "history_index_path": "history.json",
        "latest_run_delta": {
            "root_ready_seconds": -0.5,
            "frame_count": 5,
        },
        "comparison_baseline": {
            "selected_run_id": "2026-05-25_120000",
            "skipped_run_ids": ["2026-05-25_120500"],
        },
    }

    write_validation_markdown_report(report_path, payload)

    content = report_path.read_text(encoding="utf-8")
    assert "- Release gate: `ready`" in content
    assert "- Checklist: `checklist.md`" in content
    assert "- Gate warning threshold: `attempts >= 4 or seconds >= 3.0`" in content
    assert "- Latest index: `latest.json`" in content
    assert "- History index: `history.json`" in content
    assert "- Delta root ready seconds vs previous run: `-0.5`" in content
    assert "- Delta frame count vs previous run: `5`" in content
    assert "- Comparison baseline run: `2026-05-25_120000`" in content
    assert "- Skipped runs before baseline: `['2026-05-25_120500']`" in content


def test_release_gate_marks_warning_when_ready_but_slow(tmp_path: Path):
    checklist_path = tmp_path / "packaged_release_checklist.md"
    payload = {
        "packaged_validation_summary": {
            "ok": True,
            "packaged_runtime_smoke": {
                "root_ok": True,
                "root_ready_attempts": 4,
                "root_ready_seconds": 3.5,
            },
            "packaged_release_validation": {
                "ok": True,
                "ffmpeg_status": {"ffmpeg_found": True},
                "preview_start": {"ok": True},
                "preview_stop": {"ok": True},
                "capture_start": {"ok": True},
                "capture_stop": {"ok": True},
                "capture_artifacts": {
                    "frame_count": 60,
                    "frames_csv_exists": True,
                    "summary_exists": True,
                    "metadata_exists": True,
                },
            },
        },
        "release_gate": "warning",
    }

    from usb_cam_real_validation import write_release_checklist

    write_release_checklist(checklist_path, payload)

    content = checklist_path.read_text(encoding="utf-8")
    assert "## Release Gate" in content
    assert "- Gate: `warning`" in content
    assert "- Root readiness was slower than the preferred threshold." in content


def test_release_gate_reason_mentions_delta_regression():
    payload = {
        "packaged_validation_summary": {
            "ok": True,
            "packaged_runtime_smoke": {
                "root_ok": True,
                "root_ready_attempts": 2,
                "root_ready_seconds": 0.9,
            },
        },
        "latest_run_delta": {
            "root_ready_seconds": 1.4,
            "frame_count": -12,
        },
    }

    from usb_cam_real_validation import derive_release_gate

    gate, reasons = derive_release_gate(payload)

    assert gate == "warning"
    assert "Root readiness regressed versus the previous run by 1.4 seconds." in reasons
    assert "Frame production regressed versus the previous run by 12 frames." in reasons


def test_release_gate_reason_mentions_missing_frames_on_fail():
    payload = {
        "packaged_validation_summary": {
            "ok": False,
            "packaged_runtime_smoke": {
                "root_ok": True,
            },
            "packaged_release_validation": {
                "ok": False,
                "capture_artifacts": {
                    "frame_count": 0,
                    "summary_exists": True,
                    "metadata_exists": True,
                },
            },
        },
    }

    from usb_cam_real_validation import derive_release_gate

    gate, reasons = derive_release_gate(payload)

    assert gate == "fail"
    assert "Capture frames were not produced in the packaged release validation." in reasons


def test_release_gate_reason_prefers_backend_capture_error_detail():
    payload = {
        "packaged_validation_summary": {
            "ok": False,
            "packaged_runtime_smoke": {
                "ok": True,
                "root_ok": True,
            },
            "packaged_release_validation": {
                "ok": False,
                "monitor": {
                    "capture_last_error": "Selected camera could not be opened: INVALID_CAMERA.",
                    "capture_last_error_reason": "camera_invalid",
                },
                "capture_start": {
                    "ok": False,
                    "capture_last_error": "Starting pipeline...",
                },
                "capture_artifacts": {
                    "frame_count": 0,
                    "summary_exists": True,
                    "metadata_exists": True,
                },
            },
        }
    }

    from usb_cam_real_validation import derive_release_gate

    gate, reasons = derive_release_gate(payload)

    assert gate == "fail"
    assert "Selected camera could not be opened: INVALID_CAMERA." in reasons


def test_run_packaged_validation_summary_applies_fail_gate_reason_for_missing_frames(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    output_root = tmp_path / "packaged_release"
    history_dir = tmp_path / "packaged_runtime"
    history_dir.mkdir(exist_ok=True)
    valid_dir = history_dir / "2026-05-25_120000"
    valid_dir.mkdir(parents=True, exist_ok=True)
    (valid_dir / "packaged_validation_summary_report.json").write_text("{}", encoding="utf-8")
    (history_dir / "packaged_validation_history.json").write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "2026-05-25_120000",
                        "run_dir": str(valid_dir),
                        "summary_report": str(valid_dir / "packaged_validation_summary_report.json"),
                        "root_ready_attempts": 1,
                        "root_ready_seconds": 1.0,
                        "frame_count": 70,
                        "total_frame_size_bytes": 1000,
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_report_paths",
        lambda base_dir=Path("outputs") / "packaged_runtime": {
            "root": history_dir / "2026-05-25_123456",
            "smoke": history_dir / "2026-05-25_123456" / "packaged_runtime_smoke_report.json",
            "release": history_dir / "2026-05-25_123456" / "packaged_release_validation_report.json",
            "summary": history_dir / "2026-05-25_123456" / "packaged_validation_summary_report.json",
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_runtime_smoke_validation",
        lambda **kwargs: {
            "packaged_runtime_smoke": {
                "ok": True,
                "window_title": "USB_Cam_4K25.exe",
                "root_ok": True,
                "root_ready_attempts": 1,
                "root_ready_seconds": 0.9,
                "ffmpeg_path": "tools/ffmpeg.exe",
                "camera_devices": ["imx678' UVC"],
            }
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_release_validation",
        lambda **kwargs: {
            "packaged_release_validation": {
                "ok": False,
                "capture_artifacts": {
                    "session_dir": str(output_root / "session_001"),
                    "frame_count": 0,
                    "total_frame_size_bytes": 0,
                    "frames_csv_exists": True,
                    "summary_exists": True,
                    "metadata_exists": True,
                    "frames_csv_path": str(output_root / "session_001" / "frames.csv"),
                    "summary_path": str(output_root / "session_001" / "summary.txt"),
                    "metadata_path": str(output_root / "session_001" / "metadata.json"),
                }
            }
        },
    )

    result = run_packaged_validation_summary(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        output_root=output_root,
    )

    assert result["release_gate"] == "fail"
    assert "Capture frames were not produced in the packaged release validation." in result["release_gate_reasons"]


def test_run_packaged_validation_summary_prefers_backend_failure_reason_from_capture_start(monkeypatch, tmp_path: Path):
    history_dir = tmp_path / "packaged_runtime"
    history_dir.mkdir(exist_ok=True)
    valid_dir = history_dir / "2026-05-25_120000"
    valid_dir.mkdir(parents=True)
    (valid_dir / "packaged_validation_summary_report.json").write_text("{}", encoding="utf-8")
    (history_dir / "packaged_validation_history.json").write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "2026-05-25_120000",
                        "root_ready_attempts": 1,
                        "root_ready_seconds": 0.5,
                        "frame_count": 10,
                        "summary_report": str(valid_dir / "packaged_validation_summary_report.json"),
                        "release_gate": "ready",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_report_paths",
        lambda: {
            "root": history_dir / "2026-05-25_123456",
            "smoke": history_dir / "2026-05-25_123456" / "packaged_runtime_smoke_report.json",
            "release": history_dir / "2026-05-25_123456" / "packaged_release_validation_report.json",
            "summary": history_dir / "2026-05-25_123456" / "packaged_validation_summary_report.json",
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_runtime_smoke_validation",
        lambda **kwargs: {
            "packaged_runtime_smoke": {
                "ok": True,
                "root_ok": True,
                "window_title": "USB Cam 4K25",
                "root_ready_attempts": 1,
                "root_ready_seconds": 0.4,
            }
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_release_validation",
        lambda **kwargs: {
            "packaged_release_validation": {
                "ok": False,
                "ffmpeg_status": {"ffmpeg_found": True},
                "preview_start": {"ok": True},
                "preview_stop": {"ok": True},
                "monitor": {
                    "capture_last_error": "Selected camera could not be opened: INVALID_CAMERA.",
                    "capture_last_error_reason": "camera_invalid",
                },
                "capture_start": {
                    "ok": False,
                    "status_text": "Starting pipeline...",
                    "capture_last_error": None,
                    "capture_last_error_reason": None,
                },
                "capture_stop": {"ok": False, "status_text": "Selected camera could not be opened: INVALID_CAMERA."},
                "capture_artifacts": {
                    "frame_count": 0,
                    "summary_exists": True,
                    "metadata_exists": True,
                    "session_dir": str(tmp_path / "release" / "session_001"),
                },
            }
        },
    )

    result = run_packaged_validation_summary(
        exe_path=tmp_path / "USB_Cam_4K25.exe",
        api_base_url="http://127.0.0.1:8000",
        output_root=tmp_path / "release",
    )

    assert result["release_gate"] == "fail"
    assert "Selected camera could not be opened: INVALID_CAMERA." in result["release_gate_reasons"]


def test_run_packaged_validation_summary_applies_delta_driven_gate_reason(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    output_root = tmp_path / "packaged_release"
    history_dir = tmp_path / "packaged_runtime"
    history_dir.mkdir(exist_ok=True)
    (history_dir / "packaged_validation_history.json").write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "2026-05-25_120000",
                        "release_gate": "ready",
                        "root_ready_attempts": 1,
                        "root_ready_seconds": 1.0,
                        "frame_count": 70,
                        "total_frame_size_bytes": 1000,
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_report_paths",
        lambda base_dir=Path("outputs") / "packaged_runtime": {
            "root": history_dir / "2026-05-25_123456",
            "smoke": history_dir / "2026-05-25_123456" / "packaged_runtime_smoke_report.json",
            "release": history_dir / "2026-05-25_123456" / "packaged_release_validation_report.json",
            "summary": history_dir / "2026-05-25_123456" / "packaged_validation_summary_report.json",
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_runtime_smoke_validation",
        lambda **kwargs: {
            "packaged_runtime_smoke": {
                "ok": True,
                "window_title": "USB_Cam_4K25.exe",
                "root_ok": True,
                "root_ready_attempts": 2,
                "root_ready_seconds": 2.4,
                "ffmpeg_path": "tools/ffmpeg.exe",
                "camera_devices": ["imx678' UVC"],
            }
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_release_validation",
        lambda **kwargs: {
            "packaged_release_validation": {
                "ok": True,
                "capture_artifacts": {
                    "session_dir": str(output_root / "session_001"),
                    "frame_count": 60,
                    "total_frame_size_bytes": 1234,
                    "frames_csv_path": str(output_root / "session_001" / "frames.csv"),
                    "summary_path": str(output_root / "session_001" / "summary.txt"),
                    "metadata_path": str(output_root / "session_001" / "metadata.json"),
                }
            }
        },
    )

    result = run_packaged_validation_summary(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        output_root=output_root,
    )

    assert result["release_gate"] == "warning"
    assert "Root readiness regressed versus the previous run by 1.4 seconds." in result["release_gate_reasons"]
    assert "Frame production regressed versus the previous run by 10 frames." in result["release_gate_reasons"]


def test_run_packaged_validation_summary_writes_release_checklist(monkeypatch, tmp_path: Path):
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    output_root = tmp_path / "packaged_release"

    monkeypatch.setattr(
        "usb_cam_real_validation.packaged_report_paths",
        lambda base_dir=Path("outputs") / "packaged_runtime": {
            "root": tmp_path / "packaged_runtime" / "2026-05-25_123456",
            "smoke": tmp_path / "packaged_runtime" / "2026-05-25_123456" / "packaged_runtime_smoke_report.json",
            "release": tmp_path / "packaged_runtime" / "2026-05-25_123456" / "packaged_release_validation_report.json",
            "summary": tmp_path / "packaged_runtime" / "2026-05-25_123456" / "packaged_validation_summary_report.json",
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_runtime_smoke_validation",
        lambda **kwargs: {
            "packaged_runtime_smoke": {
                "ok": True,
                "window_title": "USB_Cam_4K25.exe",
                "root_ok": True,
                "root_ready_attempts": 1,
                "root_ready_seconds": 0.1,
                "ffmpeg_path": "tools/ffmpeg.exe",
                "camera_devices": ["imx678' UVC"],
            }
        },
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_release_validation",
        lambda **kwargs: {
            "packaged_release_validation": {
                "ok": True,
                "preview_start": {"ok": True},
                "preview_stop": {"ok": True},
                "capture_start": {"ok": True},
                "capture_stop": {"ok": True},
                "ffmpeg_status": {"ok": True, "ffmpeg_found": True},
                "capture_artifacts": {
                    "session_dir": str(output_root / "session_001"),
                    "frame_count": 60,
                    "frames_csv_exists": True,
                    "summary_exists": True,
                    "metadata_exists": True,
                    "frames_csv_path": str(output_root / "session_001" / "frames.csv"),
                    "summary_path": str(output_root / "session_001" / "summary.txt"),
                    "metadata_path": str(output_root / "session_001" / "metadata.json"),
                },
            }
        },
    )

    result = run_packaged_validation_summary(
        exe_path=exe_path,
        api_base_url="http://127.0.0.1:8000",
        output_root=output_root,
    )

    checklist_path = Path(result["checklist_path"])
    checklist = checklist_path.read_text(encoding="utf-8")

    assert checklist_path.name == "packaged_release_checklist.md"
    assert "- [x] Root endpoint reachable" in checklist
    assert "- [x] FFmpeg detected" in checklist
    assert "- [x] Preview start succeeded" in checklist
    assert "- [x] Preview stop succeeded" in checklist
    assert "- [x] Capture start succeeded" in checklist
    assert "- [x] Capture stop succeeded" in checklist
    assert "- [x] Capture frames were produced" in checklist
    assert "- [x] frames.csv exists" in checklist
    assert "- [x] summary.txt exists" in checklist
    assert "- [x] metadata.json exists" in checklist


def test_release_checklist_includes_failure_summary_and_actions(tmp_path: Path):
    checklist_path = tmp_path / "packaged_release_checklist.md"
    payload = {
        "packaged_validation_summary": {
            "ok": False,
            "packaged_runtime_smoke": {
                "root_ok": False,
                "failure_detail": "cleanup_conflicts_remaining=[{'pid': 1}]",
            },
            "packaged_release_validation": {
                "ok": False,
                "ffmpeg_status": {"ffmpeg_found": False},
                "preview_start": {"ok": False},
                "preview_stop": {"ok": True},
                "capture_start": {"ok": False},
                "capture_stop": {"ok": True},
                "capture_artifacts": {
                    "frame_count": 0,
                    "frames_csv_exists": False,
                    "summary_exists": False,
                    "metadata_exists": False,
                },
            },
        }
    }

    from usb_cam_real_validation import write_release_checklist

    write_release_checklist(checklist_path, payload)

    content = checklist_path.read_text(encoding="utf-8")
    assert "## Failure Summary" in content
    assert "- Smoke failure detail: `cleanup_conflicts_remaining=[{'pid': 1}]`" in content
    assert "## Suggested Actions" in content
    assert "- Check whether packaged runtime child processes are still running and retry after cleanup." in content
    assert "- Verify FFmpeg is bundled and reachable from the packaged tools directory." in content
    assert "- Inspect capture session artifacts and backend logs before accepting the build." in content


def test_release_checklist_includes_delta_summary_when_available(tmp_path: Path):
    checklist_path = tmp_path / "packaged_release_checklist.md"
    payload = {
        "packaged_validation_summary": {
            "ok": True,
            "packaged_runtime_smoke": {
                "root_ok": True,
                "root_ready_attempts": 1,
                "root_ready_seconds": 0.5,
            },
            "packaged_release_validation": {
                "ok": True,
                "ffmpeg_status": {"ffmpeg_found": True},
                "preview_start": {"ok": True},
                "preview_stop": {"ok": True},
                "capture_start": {"ok": True},
                "capture_stop": {"ok": True},
                "capture_artifacts": {
                    "frame_count": 60,
                    "frames_csv_exists": True,
                    "summary_exists": True,
                    "metadata_exists": True,
                },
            },
        },
        "release_gate": "ready",
        "latest_run_delta": {
            "root_ready_seconds": -0.5,
            "frame_count": 5,
        },
        "comparison_baseline": {
            "selected_run_id": "2026-05-25_120000",
            "skipped_run_ids": ["2026-05-25_120500"],
        },
    }

    from usb_cam_real_validation import write_release_checklist

    write_release_checklist(checklist_path, payload)

    content = checklist_path.read_text(encoding="utf-8")
    assert "## Run Delta" in content
    assert "- Root ready seconds vs previous run: `-0.5`" in content
    assert "- Frame count vs previous run: `5`" in content
    assert "## Comparison Baseline" in content
    assert "- Selected run: `2026-05-25_120000`" in content
    assert "- Skipped runs: `['2026-05-25_120500']`" in content


def test_packaged_validation_report_paths_share_timestamped_run_dir(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("usb_cam_real_validation.time.strftime", lambda fmt: "2026-05-25_010203")

    from usb_cam_real_validation import packaged_report_paths

    paths = packaged_report_paths()

    assert paths["root"].name == "2026-05-25_010203"
    assert paths["smoke"].name == "packaged_runtime_smoke_report.json"
    assert paths["release"].name == "packaged_release_validation_report.json"
    assert paths["summary"].name == "packaged_validation_summary_report.json"
    assert paths["smoke"].parent == paths["release"].parent == paths["summary"].parent == paths["root"]


def test_main_routes_packaged_release_validation(monkeypatch, tmp_path: Path):
    called = {}
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    output_root = tmp_path / "packaged_release"

    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_release_validation",
        lambda **kwargs: called.update(kwargs) or {"packaged_release_validation": {"ok": True}},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.validation_success",
        lambda result: True,
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.argparse.ArgumentParser.parse_args",
        lambda self: type(
            "Args",
            (),
            {
                "ffmpeg": "ffmpeg.exe",
                "camera_name": "USB Camera",
                "output_root": str(output_root),
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
                "exe_path": str(exe_path),
                "api_base_url": "http://127.0.0.1:8000",
                "report_path": None,
            },
        )(),
    )

    from usb_cam_real_validation import main

    assert main() == 0
    assert called["exe_path"] == exe_path
    assert called["output_root"] == output_root


def test_main_routes_packaged_validation_summary_without_ffmpeg(monkeypatch, tmp_path: Path):
    called = {}
    exe_path = tmp_path / "USB_Cam_4K25.exe"
    exe_path.write_text("stub", encoding="utf-8")
    output_root = tmp_path / "packaged_release"

    monkeypatch.setattr(
        "usb_cam_real_validation.run_packaged_validation_summary",
        lambda **kwargs: called.update(kwargs) or {"packaged_validation_summary": {"ok": True}},
    )
    monkeypatch.setattr(
        "usb_cam_real_validation.validation_success",
        lambda result: True,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "usb_cam_real_validation.py",
            "--packaged-validation-summary-only",
            "--exe-path",
            str(exe_path),
            "--output-root",
            str(output_root),
        ],
    )

    from usb_cam_real_validation import main

    assert main() == 0
    assert called["exe_path"] == exe_path
    assert called["output_root"] == output_root


def test_main_requires_ffmpeg_for_non_packaged_validation(monkeypatch, tmp_path: Path):
    called = {"run_validation": False}

    monkeypatch.setattr(
        "usb_cam_real_validation.run_validation",
        lambda **kwargs: called.__setitem__("run_validation", True),
    )
    monkeypatch.setattr(sys, "argv", ["usb_cam_real_validation.py"])

    from usb_cam_real_validation import main

    with pytest.raises(SystemExit, match="--ffmpeg is required"):
        main()

    assert called["run_validation"] is False


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


def test_validation_success_ignores_metadata_dicts_without_ok():
    assert validation_success({
        "packaged_validation_summary": {"ok": True},
        "related_reports": {
            "smoke": "smoke.json",
            "release": "release.json",
            "summary": "summary.json",
        },
    }) is True


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
