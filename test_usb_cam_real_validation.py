import shutil
import subprocess
from pathlib import Path

import pytest

from usb_cam_real_validation import collect_session_artifacts, run_ffmpeg_process_for_duration


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
