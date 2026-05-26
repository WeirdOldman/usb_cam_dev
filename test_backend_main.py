from pathlib import Path
import sys

from fastapi.testclient import TestClient

import backend.main as backend_main


def test_config_endpoint_returns_runtime_config(tmp_path: Path):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    response = client.get("/api/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["camera_name"] == backend_main.DEFAULT_CAMERA_NAME
    assert payload["mode"] == "direct_frames"
    assert payload["quality_mode"] == "copy"
    assert payload["mjpeg_url"] == f"http://{backend_main.API_HOST}:{backend_main.API_PORT}{backend_main.MJPEG_PATH}"
    assert payload["websocket_url"] == f"ws://{backend_main.API_HOST}:{backend_main.API_PORT}{backend_main.WS_PATH}"
    assert payload["auto_stop"]["min_disk_free_mb_hard"] == 5120.0


def test_start_endpoint_accepts_parameterized_request(tmp_path: Path, monkeypatch):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    monkeypatch.setattr(runtime, "prepare_capture_session", lambda: tmp_path / "session" / "run_log.txt")

    class DummyWorker:
        def __init__(self, target=None, daemon=None):
            self.target = target
            self.daemon = daemon

        def start(self):
            return None

    monkeypatch.setattr(backend_main.threading, "Thread", DummyWorker)
    monkeypatch.setattr(runtime, "refresh_monitor_payload", lambda status_override=None: None)
    monkeypatch.setattr(backend_main, "find_ffmpeg", lambda: r"E:\codex\usb_cam_dev\tools\ffmpeg.exe")

    response = client.post(
        "/api/control/start",
        json={
            "mode": "video_then_frames",
            "output_dir": str(tmp_path / "captures"),
            "image_prefix": "demo",
            "quality_mode": "q2",
            "delete_video_after_extract": True,
            "camera_name": "USB Camera",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["running"] is True
    assert payload["config"]["mode"] == "video_then_frames"
    assert payload["config"]["image_prefix"] == "demo"
    assert payload["config"]["quality_mode"] == "q2"
    assert payload["config"]["delete_video_after_extract"] is True


def test_update_config_endpoint_persists_runtime_settings(tmp_path: Path, monkeypatch):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    monkeypatch.setattr(backend_main, "find_ffmpeg", lambda: r"E:\codex\usb_cam_dev\tools\ffmpeg.exe")

    response = client.put(
        "/api/config",
        json={
            "camera_name": "Rewired Camera",
            "output_dir": str(tmp_path / "custom_out"),
            "image_prefix": "frame",
            "mode": "video_then_frames",
            "quality_mode": "q2",
            "delete_video_after_extract": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["camera_name"] == "Rewired Camera"
    assert payload["output_dir"] == str(tmp_path / "custom_out")
    assert payload["image_prefix"] == "frame"
    assert payload["mode"] == "video_then_frames"
    assert payload["quality_mode"] == "q2"
    assert payload["delete_video_after_extract"] is True


def test_mjpeg_endpoint_returns_streaming_multipart_response(tmp_path: Path, monkeypatch):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    monkeypatch.setattr(
        runtime,
        "iter_preview_mjpeg_chunks",
        lambda: iter([b"--frame\r\nContent-Type: image/jpeg\r\n\r\nfakejpeg\r\n"]),
    )

    response = client.get("/api/video/mjpeg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("multipart/x-mixed-replace; boundary=frame")
    assert response.content.startswith(b"--frame")


def test_monitor_websocket_pushes_runtime_snapshot(tmp_path: Path):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.last_monitor_payload = {
        "running": False,
        "capture_phase": "idle",
        "runtime_seconds": 7,
        "fps": 4.2,
        "cpu_percent": 11,
        "processed_frames": 123,
        "acceleration": "Idle",
        "bitrate_mbps": 0.0,
        "resolution": "3840x2160",
        "status_text": "Stopped",
        "capture_last_error": None,
        "capture_last_error_reason": None,
        "capture_last_error_code": None,
        "capture_last_session_dir": None,
        "preview_enabled": True,
        "preview_active": False,
        "preview_status": "Preview ready.",
        "ui_locks": runtime.ui_locks(),
        "events": [{"kind": "system", "message": "System initialized.", "timestamp": "2026-05-24T23:59:58"}],
        "timestamp": "2026-05-24T23:59:59",
        "config": runtime.control_config(),
    }
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    with client.websocket_connect("/ws/monitor") as websocket:
        payload = websocket.receive_json()
        websocket.send_text("ack")

    assert payload["runtime_seconds"] == 7
    assert payload["fps"] == 4.2
    assert payload["processed_frames"] == 123
    assert payload["events"][0]["message"] == "System initialized."
    assert payload["config"]["mode"] == "direct_frames"


def test_select_output_dir_endpoint_updates_runtime_config(tmp_path: Path, monkeypatch):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    selected_dir = tmp_path / "picked_output"
    monkeypatch.setattr(backend_main, "open_directory_dialog", lambda current_dir: str(selected_dir))

    response = client.post(
        "/api/dialog/select-output-dir",
        json={"current_dir": str(tmp_path / "capture_output")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["selected_dir"] == str(selected_dir)
    assert payload["config"]["output_dir"] == str(selected_dir)


def test_mjpeg_endpoint_uses_runtime_preview_stream(tmp_path: Path, monkeypatch):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    calls: list[str] = []
    def fake_stream():
        calls.append("ensure")
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\nrealjpeg\r\n"

    monkeypatch.setattr(runtime, "iter_preview_mjpeg_chunks", fake_stream)

    response = client.get("/api/video/mjpeg")

    assert response.status_code == 200
    assert calls == ["ensure"]
    assert response.content.startswith(b"--frame")


def test_start_endpoint_stops_preview_before_capture(tmp_path: Path, monkeypatch):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    runtime.preview_proc = object()
    stop_calls: list[tuple[bool]] = []
    monkeypatch.setattr(runtime, "stop_preview", lambda wait=False: stop_calls.append((wait,)))
    monkeypatch.setattr(runtime, "prepare_capture_session", lambda: tmp_path / "session" / "run_log.txt")
    monkeypatch.setattr(runtime, "refresh_monitor_payload", lambda status_override=None: None)
    monkeypatch.setattr(backend_main, "find_ffmpeg", lambda: r"E:\codex\usb_cam_dev\tools\ffmpeg.exe")

    class DummyWorker:
        def __init__(self, target=None, daemon=None):
            self.target = target
            self.daemon = daemon

        def start(self):
            return None

    monkeypatch.setattr(backend_main.threading, "Thread", DummyWorker)

    response = client.post("/api/control/start", json={})

    assert response.status_code == 200
    assert stop_calls == [(True,)]


def test_preview_stream_does_not_start_new_preview_process_while_capture_running(tmp_path: Path, monkeypatch):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.capture_state.capture_running = True
    runtime.latest_preview_frame = b"fakepngbytes"

    calls: list[str] = []
    monkeypatch.setattr(runtime, "ensure_preview_running", lambda: calls.append("ensure"))
    monkeypatch.setattr(runtime, "preview_frame_to_jpeg", lambda frame: b"converted-jpeg")

    stream = runtime.iter_preview_mjpeg_chunks()
    chunk = next(stream)

    assert calls == []
    assert b"converted-jpeg" in chunk


def test_build_direct_cmd_includes_preview_pipe_output(tmp_path: Path):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.capture_context.current_frames_dir = tmp_path / "frames"
    runtime.capture_context.current_frames_dir.mkdir()

    cmd = runtime.build_direct_cmd(r"E:\codex\usb_cam_dev\tools\ffmpeg.exe")

    assert "-progress" in cmd
    assert "pipe:2" in cmd
    assert "pipe:1" in cmd
    assert cmd.count("-map") >= 2
    assert "image2pipe" in cmd


def test_build_record_cmd_includes_preview_pipe_output(tmp_path: Path):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    video_path = tmp_path / "video" / "capture.avi"
    video_path.parent.mkdir()

    cmd = runtime.build_record_cmd(r"E:\codex\usb_cam_dev\tools\ffmpeg.exe", video_path)

    assert "-progress" in cmd
    assert "pipe:2" in cmd
    assert "pipe:1" in cmd
    assert cmd.count("-map") >= 2
    assert "image2pipe" in cmd


def test_window_minimize_endpoint_calls_webview_window(monkeypatch):
    class DummyWindow:
        def __init__(self):
            self.calls = []

        def minimize(self):
            self.calls.append("minimize")

    dummy_window = DummyWindow()
    backend_main.webview_window = dummy_window
    app = backend_main.create_app()
    client = TestClient(app)

    response = client.post("/api/window/minimize")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert dummy_window.calls == ["minimize"]


def test_window_close_endpoint_calls_webview_window(monkeypatch):
    class DummyWindow:
        def __init__(self):
            self.calls = []

        def destroy(self):
            self.calls.append("destroy")

    dummy_window = DummyWindow()
    backend_main.webview_window = dummy_window
    app = backend_main.create_app()
    client = TestClient(app)

    response = client.post("/api/window/close")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert dummy_window.calls == ["destroy"]


def test_window_toggle_maximize_endpoint_calls_matching_window_method():
    class DummyWindow:
        def __init__(self, state: str):
            self.state = state
            self.calls = []

        def maximize(self):
            self.calls.append("maximize")

        def restore(self):
            self.calls.append("restore")

    maximized_window = DummyWindow("maximized")
    backend_main.webview_window = maximized_window
    app = backend_main.create_app()
    client = TestClient(app)

    response = client.post("/api/window/toggle-maximize")

    assert response.status_code == 200
    assert maximized_window.calls == ["restore"]

    normal_window = DummyWindow("normal")
    backend_main.webview_window = normal_window
    app = backend_main.create_app()
    client = TestClient(app)

    response = client.post("/api/window/toggle-maximize")

    assert response.status_code == 200
    assert normal_window.calls == ["maximize"]


def test_open_output_dir_endpoint_uses_runtime_output_dir(tmp_path: Path, monkeypatch):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.output_dir = tmp_path / "capture_output"
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    calls: list[str] = []
    monkeypatch.setattr(backend_main, "open_system_path", lambda path: calls.append(path))

    response = client.post("/api/system/open-output-dir")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert calls == [str(runtime.output_dir)]


def test_ffmpeg_status_endpoint_reports_current_path(tmp_path: Path, monkeypatch):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    monkeypatch.setattr(backend_main, "find_ffmpeg", lambda: r"E:\codex\usb_cam_dev\tools\ffmpeg.exe")

    response = client.get("/api/system/ffmpeg-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["ffmpeg_found"] is True
    assert payload["ffmpeg_path"] == r"E:\codex\usb_cam_dev\tools\ffmpeg.exe"


def test_preview_start_endpoint_enables_preview_and_starts_idle_preview(tmp_path: Path, monkeypatch):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.preview_enabled = False
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    calls: list[str] = []
    monkeypatch.setattr(runtime, "ensure_preview_running", lambda: calls.append("ensure"))

    response = client.post("/api/preview/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["preview_enabled"] is True
    assert calls == ["ensure"]


def test_preview_stop_endpoint_disables_idle_preview_and_stops_process(tmp_path: Path, monkeypatch):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.preview_enabled = True
    runtime.preview_proc = object()
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    calls: list[bool] = []
    monkeypatch.setattr(runtime, "stop_preview", lambda wait=False: calls.append(wait))

    response = client.post("/api/preview/stop")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["preview_enabled"] is False
    assert calls == [True]


def test_preview_stop_endpoint_rejects_while_capture_running(tmp_path: Path):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.capture_state.capture_running = True
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    response = client.post("/api/preview/stop")

    assert response.status_code == 409


def test_snapshot_includes_preview_state_fields(tmp_path: Path):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.preview_enabled = False
    runtime.refresh_monitor_payload()

    payload = runtime.snapshot()

    assert payload["preview_enabled"] is False
    assert payload["preview_active"] is False
    assert "preview_status" in payload
    assert "events" in payload


def test_snapshot_includes_ui_lock_reasons_when_ffmpeg_missing(tmp_path: Path):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.ffmpeg_path = ""
    runtime.refresh_monitor_payload()

    payload = runtime.snapshot()

    assert payload["ui_locks"]["capture_start_disabled"] is True
    assert payload["ui_locks"]["capture_start_reason"] == "FFmpeg not found."
    assert payload["ui_locks"]["path_edit_disabled"] is False


def test_snapshot_marks_controls_locked_while_capture_running(tmp_path: Path):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.capture_state.capture_running = True
    runtime.refresh_monitor_payload()

    payload = runtime.snapshot()

    assert payload["ui_locks"]["preview_toggle_disabled"] is True
    assert payload["ui_locks"]["path_edit_disabled"] is True
    assert payload["ui_locks"]["config_save_disabled"] is True
    assert payload["ui_locks"]["camera_select_disabled"] is True


def test_events_endpoint_returns_recent_runtime_events(tmp_path: Path):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.append_event("preview", "Preview running.")
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    response = client.get("/api/events")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert len(payload["events"]) == 2
    assert payload["events"][0]["kind"] == "system"
    assert payload["events"][0]["message"] == "System initialized."
    assert payload["events"][1]["message"] == "Preview running."


def test_runtime_append_event_keeps_recent_window(tmp_path: Path):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)

    for i in range(80):
        runtime.append_event("system", f"event-{i}")

    assert len(runtime.event_log) == 60
    assert runtime.event_log[0]["message"] == "event-20"
    assert runtime.event_log[-1]["message"] == "event-79"


def test_camera_devices_endpoint_returns_detected_devices(tmp_path: Path, monkeypatch):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    monkeypatch.setattr(
        backend_main,
        "list_camera_devices",
        lambda ffmpeg_path: ["imx678' UVC ", "OBS Virtual Camera"],
    )

    response = client.get("/api/devices/cameras")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["devices"] == ["imx678' UVC ", "OBS Virtual Camera"]
    assert payload["selected_device"] == runtime.camera_name


def test_resolve_frontend_url_prefers_local_dist_index_when_present(tmp_path: Path):
    frontend_dir = tmp_path / "ui_dist"
    frontend_dir.mkdir()
    index_file = frontend_dir / "index.html"
    index_file.write_text("<!doctype html>", encoding="utf-8")

    resolved = backend_main.resolve_frontend_target(frontend_dir=frontend_dir, dev_url="http://localhost:5173")

    assert resolved == index_file.resolve().as_uri()


def test_resolve_frontend_url_falls_back_to_dev_server_when_dist_missing(tmp_path: Path):
    resolved = backend_main.resolve_frontend_target(
        frontend_dir=tmp_path / "missing_dist",
        dev_url="http://localhost:5173",
    )

    assert resolved == "http://localhost:5173"


def test_resolve_frontend_url_uses_project_ui_dist_by_default(monkeypatch, tmp_path: Path):
    frontend_dir = tmp_path / "ui_dist"
    frontend_dir.mkdir()
    index_file = frontend_dir / "index.html"
    index_file.write_text("<!doctype html>", encoding="utf-8")

    monkeypatch.setattr(backend_main, "FRONTEND_DIST_DIR", frontend_dir)

    resolved = backend_main.resolve_frontend_target(frontend_dir=backend_main.FRONTEND_DIST_DIR)

    assert resolved == index_file.resolve().as_uri()


def test_resolve_frontend_url_uses_internal_ui_dist_when_packaged_layout_matches_pyinstaller(tmp_path: Path):
    app_root = tmp_path / "USB_Cam_4K25"
    internal_ui = app_root / "_internal" / "ui_dist"
    internal_ui.mkdir(parents=True)
    index_file = internal_ui / "index.html"
    index_file.write_text("<!doctype html>", encoding="utf-8")

    resolved = backend_main.resolve_frontend_target(frontend_dir=app_root / "ui_dist", dev_url="http://localhost:5173")

    assert resolved == index_file.resolve().as_uri()


def test_append_runtime_log_writes_lines(tmp_path: Path):
    log_path = tmp_path / "webview_runtime.log"

    backend_main.append_runtime_log(log_path, "startup ok")
    backend_main.append_runtime_log(log_path, "uvicorn thread started")

    content = log_path.read_text(encoding="utf-8")

    assert "startup ok" in content
    assert "uvicorn thread started" in content


def test_backend_uses_preview_module_without_tkinter_helper():
    content = Path(r"E:\codex\usb_cam_dev\backend\main.py").read_text(encoding="utf-8")

    assert "from usb_cam_preview_helpers import prepare_preview_start" not in content
    assert "from usb_cam_preview import build_preview_cmd" in content


def test_start_capture_reports_ffmpeg_missing_structured_error(tmp_path: Path):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    backend_main.runtime_state = runtime
    backend_main.find_ffmpeg = lambda: ""

    result = runtime.start_capture(
        backend_main.StartCaptureRequest(
            mode="direct_frames",
            camera_name="USB Camera",
        )
    )

    assert result["ok"] is False
    assert result["capture_last_error_reason"] == "ffmpeg_missing"
    assert result["capture_last_error"] == "FFmpeg not found."

    payload = runtime.snapshot()
    assert payload["capture_last_error_reason"] == "ffmpeg_missing"
    assert payload["status_text"] == "FFmpeg not found."
    assert payload["capture_phase"] == "failed"


def test_worker_capture_sets_structured_error_when_no_frames(tmp_path: Path, monkeypatch):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.ffmpeg_path = r"E:\codex\usb_cam_dev\tools\ffmpeg.exe"
    session_dir = tmp_path / "session_001"
    frames_dir = session_dir / "frames"
    video_dir = session_dir / "video"
    frames_dir.mkdir(parents=True)
    video_dir.mkdir()
    runtime.capture_context.assign_session_paths(session_dir, frames_dir, video_dir)
    runtime.capture_context.set_meta(
        {
            "ffmpeg": r"E:\codex\usb_cam_dev\tools\ffmpeg.exe",
            "run_log_path": str(session_dir / "run_log.txt"),
            "exit_codes": [{"direct_frames": 4294967291}],
            "camera_name": "INVALID_CAMERA",
        }
    )
    (session_dir / "run_log.txt").write_text(
        "[in#0] Could not find video device with name [INVALID_CAMERA]\nError opening input file video=INVALID_CAMERA.\n",
        encoding="utf-8",
    )
    runtime.capture_state.capture_running = True
    runtime.capture_state.start_time = 100.0

    monkeypatch.setattr(backend_main, "execute_capture_pipeline", lambda **kwargs: None)
    monkeypatch.setattr(
        backend_main,
        "finalize_session",
        lambda **kwargs: {
            "frame_count": 0,
            "current_meta": kwargs["current_meta"],
            "summary_path": session_dir / "summary.txt",
            "csv_path": session_dir / "frames.csv",
            "meta_path": session_dir / "metadata.json",
        },
    )
    monkeypatch.setattr(backend_main, "finalize_capture_summary", lambda capture_context, result: None)

    runtime.worker_capture()

    payload = runtime.snapshot()
    assert runtime.capture_state.capture_running is False
    assert runtime.capture_last_error_reason == "camera_invalid"
    assert "INVALID_CAMERA" in (runtime.capture_last_error or "")
    assert payload["capture_last_error_reason"] == "camera_invalid"
    assert payload["capture_phase"] == "failed"
    assert "INVALID_CAMERA" in payload["status_text"]


def test_preview_stop_does_not_override_existing_capture_failure_status(tmp_path: Path):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.record_capture_error(
        reason="camera_invalid",
        message="Selected camera could not be opened: INVALID_CAMERA.",
        session_dir=str(tmp_path / "session_001"),
    )

    runtime.refresh_monitor_payload(status_override="Preview stopped.")

    payload = runtime.snapshot()
    assert payload["capture_last_error_reason"] == "camera_invalid"
    assert payload["status_text"] == "Selected camera could not be opened: INVALID_CAMERA."
    assert payload["preview_status"] == "Preview ready."


def test_monitor_endpoint_returns_structured_runtime_snapshot(tmp_path: Path):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.record_capture_error(
        reason="capture_no_frames",
        message="Capture completed without producing frames.",
        code=21,
        session_dir=str(tmp_path / "session_002"),
    )
    backend_main.runtime_state = runtime
    app = backend_main.create_app()
    client = TestClient(app)

    response = client.get("/api/monitor")

    assert response.status_code == 200
    payload = response.json()
    assert payload["capture_last_error_reason"] == "capture_no_frames"
    assert payload["capture_last_error_code"] == 21
    assert payload["capture_last_session_dir"] == str(tmp_path / "session_002")
    assert payload["status_text"] == "Capture completed without producing frames."


def test_worker_capture_sets_runtime_exception_status(tmp_path: Path, monkeypatch):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.ffmpeg_path = r"E:\codex\usb_cam_dev\tools\ffmpeg.exe"
    session_dir = tmp_path / "session_003"
    frames_dir = session_dir / "frames"
    video_dir = session_dir / "video"
    frames_dir.mkdir(parents=True)
    video_dir.mkdir()
    runtime.capture_context.assign_session_paths(session_dir, frames_dir, video_dir)
    runtime.capture_context.set_meta(
        {
            "ffmpeg": r"E:\codex\usb_cam_dev\tools\ffmpeg.exe",
            "run_log_path": str(session_dir / "run_log.txt"),
            "exit_codes": [],
            "camera_name": "USB Camera",
        }
    )
    runtime.capture_state.capture_running = True
    runtime.capture_state.start_time = 100.0

    def fail_pipeline(**kwargs):
        raise RuntimeError("simulated pipeline crash")

    monkeypatch.setattr(backend_main, "execute_capture_pipeline", fail_pipeline)

    runtime.worker_capture()

    payload = runtime.snapshot()
    assert runtime.capture_state.capture_running is False
    assert runtime.capture_last_error_reason == "runtime_exception"
    assert "simulated pipeline crash" in (runtime.capture_last_error or "")
    assert payload["capture_phase"] == "failed"
    assert "simulated pipeline crash" in payload["status_text"]


def test_stop_capture_returns_failure_snapshot_when_capture_already_failed(tmp_path: Path):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.record_capture_error(
        reason="camera_invalid",
        message="Selected camera could not be opened: INVALID_CAMERA.",
        code=21,
        session_dir=str(tmp_path / "session_004"),
    )

    result = runtime.stop_capture()

    assert result["ok"] is False
    assert result["running"] is False
    assert result["capture_phase"] == "failed"
    assert result["capture_last_error_reason"] == "camera_invalid"
    assert result["status_text"] == "Selected camera could not be opened: INVALID_CAMERA."


def test_snapshot_refreshes_stale_running_payload_after_capture_finishes(tmp_path: Path):
    runtime = backend_main.BackendRuntime(base_dir=tmp_path)
    runtime.capture_state.capture_running = False
    runtime.capture_phase = "idle"
    runtime.last_monitor_payload = {
        "running": True,
        "capture_phase": "stopping",
        "status_text": "Stopping capture...",
    }

    payload = runtime.snapshot()

    assert payload["running"] is False
    assert payload["capture_phase"] == "idle"
    assert payload["status_text"] == "Stopped"


def test_resolve_webview_debug_mode_disabled_by_default(monkeypatch):
    monkeypatch.delenv("USB_CAM_WEBVIEW_DEBUG", raising=False)

    assert backend_main.resolve_webview_debug_mode() is False


def test_resolve_webview_debug_mode_enabled_with_truthy_env(monkeypatch):
    monkeypatch.setenv("USB_CAM_WEBVIEW_DEBUG", "1")

    assert backend_main.resolve_webview_debug_mode() is True


def test_main_starts_webview_without_debug_by_default(monkeypatch):
    calls = {"debug": None, "target": None}

    class DummyThread:
        def __init__(self, target=None, args=None, daemon=None):
            self.target = target
            self.args = args or ()
            self.daemon = daemon

        def start(self):
            return None

    class DummyWebviewModule:
        def create_window(self, title, target, width=None, height=None, resizable=None):
            calls["target"] = target
            return {"title": title, "target": target}

        def start(self, debug=False):
            calls["debug"] = debug

    monkeypatch.delenv("USB_CAM_WEBVIEW_DEBUG", raising=False)
    monkeypatch.setattr(backend_main, "append_runtime_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(backend_main, "resolve_frontend_target", lambda: "file:///E:/codex/usb_cam_dev/ui_dist/index.html")
    monkeypatch.setattr(backend_main.threading, "Thread", DummyThread)
    monkeypatch.setitem(sys.modules, "webview", DummyWebviewModule())
    backend_main.webview_window = None

    backend_main.main()

    assert calls["target"] == "file:///E:/codex/usb_cam_dev/ui_dist/index.html"
    assert calls["debug"] is False
