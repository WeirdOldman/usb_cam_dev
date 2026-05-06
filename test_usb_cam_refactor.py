from __future__ import annotations

import importlib.util
from pathlib import Path

TARGET = Path(__file__).resolve().parent / 'usb_burst_cam_4k25_manual_v1_6_3.py'


def load_module():
    spec = importlib.util.spec_from_file_location('usb_cam_main', TARGET)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_sanitize_windows_filename_replaces_bad_chars_and_trims_tail():
    module = load_module()
    value = module.sanitize_windows_filename('  bad<>:"/\\|?*name.  ')
    assert value == 'bad_________name'


def test_sanitize_windows_filename_falls_back_to_default_for_empty_input():
    module = load_module()
    value = module.sanitize_windows_filename('   ', default='capture_output')
    assert value == 'capture_output'


def test_paths_module_matches_main_find_ffmpeg_contract(tmp_path, monkeypatch):
    ffmpeg_dir = tmp_path / 'tools'
    ffmpeg_dir.mkdir()
    ffmpeg_path = ffmpeg_dir / 'ffmpeg.exe'
    ffmpeg_path.write_text('fake', encoding='utf-8')

    import usb_cam_paths
    monkeypatch.setattr(usb_cam_paths, 'app_base_dir', lambda: str(tmp_path))
    monkeypatch.setattr(usb_cam_paths, 'candidate_base_dirs', lambda: [str(tmp_path)])
    monkeypatch.setattr(usb_cam_paths.shutil, 'which', lambda _name: None)

    assert usb_cam_paths.find_ffmpeg() == str(ffmpeg_path)


def test_frame_metrics_computes_expected_summary_values():
    import usb_cam_stats

    metrics = usb_cam_stats.frame_metrics(
        frame_count=50,
        capture_duration=2.0,
        total_process=5.0,
        total_size=10485760,
    )

    assert metrics['effective_fps_by_frames'] == 25.0
    assert metrics['process_average_fps'] == 10.0
    assert metrics['total_frame_size_mb'] == 10.0
    assert metrics['average_frame_size_bytes'] == 209715
    assert metrics['estimated_frames_size_per_min_bytes'] == 314572800


def test_stats_helpers_cover_zero_edges_and_nested_folder_sizes(tmp_path):
    import usb_cam_stats

    nested = tmp_path / 'nested'
    deep = nested / 'deep'
    deep.mkdir(parents=True)
    (nested / 'a.bin').write_bytes(b'1234')
    (deep / 'b.bin').write_bytes(b'12')

    assert usb_cam_stats.folder_size(tmp_path / 'missing') == 0
    assert usb_cam_stats.folder_size(nested) == 6
    assert usb_cam_stats.bytes_to_mb(0) == 0.0
    assert usb_cam_stats.bytes_to_mb(1048576) == 1.0

    zero = usb_cam_stats.frame_metrics(
        frame_count=0,
        capture_duration=0.0,
        total_process=0.0,
        total_size=0,
    )
    assert zero['effective_fps_by_frames'] == 0.0
    assert zero['process_average_fps'] == 0.0
    assert zero['average_frame_size_bytes'] == 0
    assert zero['estimated_frames_size_per_min_bytes'] == 0


def test_preview_cmd_builds_expected_pipe_preview_args():
    import usb_cam_ffmpeg

    cmd = usb_cam_ffmpeg.preview_cmd(
        ffmpeg='ffmpeg.exe',
        camera_name='USB Camera',
        width=3840,
        height=2160,
        fps=25,
        preview_fps=5,
        preview_width=640,
    )

    assert cmd[:4] == ['ffmpeg.exe', '-hide_banner', '-loglevel', 'error']
    assert 'video=USB Camera' in cmd
    assert 'fps=5,scale=640:-1' in cmd
    assert cmd[-1] == 'pipe:1'


def test_preview_helpers_extract_png_frame_boundaries():
    import usb_cam_preview

    png = (
        b'\x89PNG\r\n\x1a\n'
        + (13).to_bytes(4, 'big')
        + b'IHDR'
        + (b'\x00' * 13)
        + (0).to_bytes(4, 'big')
        + (0).to_bytes(4, 'big')
        + b'IEND'
        + (0).to_bytes(4, 'big')
    )
    buf = bytearray(b'noise' + png + b'tail')

    end = usb_cam_preview.find_png_end(bytearray(png))
    assert end == len(png)

    frames = []

    class FakeStdout:
        def __init__(self, chunks):
            self._chunks = list(chunks)

        def read(self, _size):
            return self._chunks.pop(0) if self._chunks else b''

    usb_cam_preview.read_preview_frames(
        FakeStdout([b'noise', png[:10], png[10:] + b'tail']),
        frames.append,
    )

    assert frames == [png]


def test_capture_builders_reuse_common_input_args():
    import usb_cam_capture
    from pathlib import Path

    direct = usb_cam_capture.build_direct_cmd(
        ffmpeg='ffmpeg.exe',
        output_dir=Path('out'),
        image_prefix='img',
        width=3840,
        height=2160,
        fps=25,
        camera_name='USB Camera',
        quality_mode='copy',
    )
    record = usb_cam_capture.build_record_cmd(
        ffmpeg='ffmpeg.exe',
        video_path=Path('video.avi'),
        width=3840,
        height=2160,
        fps=25,
        camera_name='USB Camera',
    )
    extract = usb_cam_capture.build_extract_cmd(
        ffmpeg='ffmpeg.exe',
        video_path=Path('video.avi'),
        output_dir=Path('out'),
        image_prefix='img',
    )

    assert direct[0] == 'ffmpeg.exe'
    assert record[0] == 'ffmpeg.exe'
    assert extract[0] == 'ffmpeg.exe'
    assert direct[-1].endswith('img_%06d.jpg')
    assert record[-1] == 'video.avi'
    assert extract[-1].endswith('img_%06d.jpg')


def test_capture_helper_branches_and_fallback_extract_args():
    import usb_cam_capture
    from pathlib import Path

    assert usb_cam_capture.base_input_args(3840, 2160, 25, 'USB Camera') == [
        '-f', 'dshow',
        '-video_size', '3840x2160',
        '-framerate', '25',
        '-vcodec', 'mjpeg',
        '-i', 'video=USB Camera',
        '-map', '0:v:0',
    ]
    assert usb_cam_capture.image_output_args('copy') == ['-c:v', 'copy', '-f', 'image2']
    assert usb_cam_capture.image_output_args('q2') == ['-q:v', '2']
    assert usb_cam_capture.ffmpeg_progress_args('ffmpeg.exe') == [
        'ffmpeg.exe', '-y', '-hide_banner', '-stats_period', '0.5', '-progress', 'pipe:1'
    ]

    extract_q2 = usb_cam_capture.build_extract_cmd(
        ffmpeg='ffmpeg.exe',
        video_path=Path('video.avi'),
        output_dir=Path('out'),
        image_prefix='img',
        fallback_q2=True,
    )
    assert extract_q2 == [
        'ffmpeg.exe', '-y', '-hide_banner', '-stats_period', '0.5', '-progress', 'pipe:1',
        '-i', 'video.avi', '-map', '0:v:0', '-q:v', '2', str(Path('out') / 'img_%06d.jpg')
    ]


def test_process_parser_handles_frame_and_out_time_lines():
    import usb_cam_process

    assert usb_cam_process.parse_ffmpeg_progress_line('frame=  12', fps=25) == 12
    assert usb_cam_process.parse_ffmpeg_progress_line('out_time_ms=2000000', fps=25) == 50
    assert usb_cam_process.parse_ffmpeg_progress_line('nope', fps=25) is None


def test_process_helpers_cover_stop_and_callback_paths(monkeypatch):
    import usb_cam_process

    events = []

    class FakeStdIn:
        def __init__(self, fail=False):
            self.fail = fail
            self.writes = []
            self.flushed = False

        def write(self, data):
            if self.fail:
                raise OSError('stdin fail')
            self.writes.append(data)

        def flush(self):
            if self.fail:
                raise OSError('flush fail')
            self.flushed = True

    class FakeProc:
        def __init__(self, lines=None, stdin_fail=False):
            self.stdin = FakeStdIn(fail=stdin_fail)
            self.stdout = iter(lines or [])
            self.terminated = False

        def wait(self):
            return 7

        def terminate(self):
            self.terminated = True

    proc = FakeProc(lines=['frame=  3\n', 'out_time_ms=2000000\n', 'junk\n'])
    monkeypatch.setattr(usb_cam_process.subprocess, 'Popen', lambda *args, **kwargs: proc)

    returned_proc, code = usb_cam_process.run_ffmpeg_process(
        ['ffmpeg.exe'],
        fps=25,
        log_write=lambda line: events.append(('log', line.strip())),
        frame_callback=lambda frame: events.append(('frame', frame)),
    )
    assert returned_proc is proc
    assert code == 7
    assert events == [
        ('log', 'frame=  3'),
        ('frame', 3),
        ('log', 'out_time_ms=2000000'),
        ('frame', 50),
        ('log', 'junk'),
    ]

    ok_proc = FakeProc()
    usb_cam_process.request_stop_process(ok_proc)
    assert ok_proc.stdin.writes == ['q\n']
    assert ok_proc.stdin.flushed is True
    assert ok_proc.terminated is False

    fail_proc = FakeProc(stdin_fail=True)
    usb_cam_process.request_stop_process(fail_proc)
    assert fail_proc.terminated is True


def test_capture_state_reset_and_snapshot_helpers(tmp_path):
    import usb_cam_capture_state

    state = usb_cam_capture_state.CaptureState(
        capture_running=True,
        start_time=12.5,
        last_ffmpeg_frame=99,
        last_display_frame_count=88,
        last_scan_time=7.0,
        last_session_size_scan_time=8.0,
        cached_frame_count=9,
        cached_frame_total_size=10,
        cached_session_size=11,
        last_fps_sample_time=6.0,
        last_fps_sample_count=5,
        instant_fps=4.5,
    )

    state.reset_for_capture()
    assert state.last_ffmpeg_frame == 0
    assert state.last_display_frame_count == 0
    assert state.last_scan_time == 0.0
    assert state.last_session_size_scan_time == 0.0
    assert state.cached_frame_count == 0
    assert state.cached_frame_total_size == 0
    assert state.cached_session_size == 0
    assert state.last_fps_sample_time == 12.5
    assert state.last_fps_sample_count == 0
    assert state.instant_fps == 0.0

    frames_dir = tmp_path / 'frames'
    session_dir = tmp_path / 'session'
    snap = state.snapshot_for_metrics(current_frames_dir=frames_dir, current_session=session_dir)
    assert snap['current_frames_dir'] == frames_dir
    assert snap['current_session'] == session_dir
    assert snap['start_time'] == 12.5

    state.apply_metrics_snapshot({
        'last_scan_time': 1.0,
        'cached_frame_count': 2,
        'cached_frame_total_size': 3,
        'last_display_frame_count': 4,
        'last_session_size_scan_time': 5.0,
        'cached_session_size': 6,
        'last_fps_sample_time': 7.0,
        'last_fps_sample_count': 8,
        'instant_fps': 9.5,
    })
    assert state.last_scan_time == 1.0
    assert state.cached_frame_count == 2
    assert state.cached_frame_total_size == 3
    assert state.last_display_frame_count == 4
    assert state.last_session_size_scan_time == 5.0
    assert state.cached_session_size == 6
    assert state.last_fps_sample_time == 7.0
    assert state.last_fps_sample_count == 8
    assert state.instant_fps == 9.5

    queue_snapshot = state.queue_snapshot()
    assert queue_snapshot == {'last_ffmpeg_frame': 0, 'capture_running': True}
    state.apply_queue_snapshot({'last_ffmpeg_frame': 13, 'capture_running': False})
    assert state.last_ffmpeg_frame == 13
    assert state.capture_running is False

    state.apply_finalize_result({
        'cached_frame_count': 21,
        'cached_frame_total_size': 22,
        'cached_session_size': 23,
    })
    assert state.cached_frame_count == 21
    assert state.cached_frame_total_size == 22
    assert state.cached_session_size == 23


def test_runtime_meta_builder_and_pipeline_direct_mode():
    import usb_cam_runtime
    from pathlib import Path

    meta = usb_cam_runtime.build_capture_meta(
        app_name='app',
        created_at='2026-01-01T00:00:00',
        camera_name='USB Camera',
        mode='direct_frames',
        quality_mode='copy',
        width=3840,
        height=2160,
        fps=25,
        image_prefix='img',
        ffmpeg='ffmpeg.exe',
        session_dir=Path('session'),
        frames_dir=Path('frames'),
        run_log_path=Path('session/run_log.txt'),
        run_log_max_bytes=123,
        delete_video_after_extract=False,
        manual_start_time='2026-01-01T00:00:01',
    )
    assert meta['app'] == 'app'
    assert meta['output']['image_prefix'] == 'img'
    assert meta['commands'] == []
    assert meta['exit_codes'] == []

    calls = []

    def fake_run_process(cmd, label, allow_manual_stop=True):
        calls.append((cmd, label, allow_manual_stop))
        return 0

    usb_cam_runtime.run_capture_pipeline(
        mode='direct_frames',
        ffmpeg='ffmpeg.exe',
        current_video_dir=None,
        current_frames_dir=None,
        delete_video_after_extract=False,
        current_meta=meta,
        run_process=fake_run_process,
        build_direct_cmd=lambda ffmpeg: ['direct', ffmpeg],
        build_record_cmd=lambda ffmpeg, video_path: ['record', ffmpeg, str(video_path)],
        build_extract_cmd=lambda ffmpeg, video_path, fallback_q2=False: ['extract', ffmpeg, str(video_path), str(fallback_q2)],
    )

    assert calls == [(['direct', 'ffmpeg.exe'], 'direct_frames', True)]
    assert meta['exit_codes'] == [{'direct_frames': 0}]


def test_ui_state_metrics_and_message_dispatch():
    import usb_cam_ui_state

    state = {
        'start_time': 0.0,
        'last_scan_time': 0.0,
        'current_frames_dir': None,
        'cached_frame_count': 3,
        'cached_frame_total_size': 3000,
        'last_ffmpeg_frame': 5,
        'last_display_frame_count': 0,
        'last_session_size_scan_time': 0.0,
        'current_session': None,
        'cached_session_size': 0,
        'last_fps_sample_time': 0.0,
        'last_fps_sample_count': 0,
        'instant_fps': 0.0,
    }
    metrics = usb_cam_ui_state.update_capture_metrics(state, now=2.0, fps=25)
    assert metrics['display_count'] == 5
    assert metrics['capture_fps_text'].endswith('fps')

    snapshot = {'last_ffmpeg_frame': 1, 'capture_running': True}
    assert usb_cam_ui_state.process_ui_message(snapshot, 'ffmpeg_frame', 9) is None
    assert snapshot['last_ffmpeg_frame'] == 9
    action = usb_cam_ui_state.process_ui_message(snapshot, 'preview_status', 'hello world')
    assert action == ('preview_status', 'hello world')


def test_ui_state_covers_scan_branches_and_remaining_actions(tmp_path):
    import usb_cam_ui_state

    session_dir = tmp_path / 'session'
    frames_dir = session_dir / 'frames'
    frames_dir.mkdir(parents=True)
    (frames_dir / 'img_000001.jpg').write_bytes(b'1234')
    (session_dir / 'run_log.txt').write_bytes(b'12')

    state = {
        'start_time': 0.0,
        'last_scan_time': 0.0,
        'current_frames_dir': frames_dir,
        'cached_frame_count': 0,
        'cached_frame_total_size': 0,
        'last_ffmpeg_frame': 0,
        'last_display_frame_count': 0,
        'last_session_size_scan_time': 0.0,
        'current_session': session_dir,
        'cached_session_size': 0,
        'last_fps_sample_time': 0.0,
        'last_fps_sample_count': 0,
        'instant_fps': 0.0,
    }
    metrics = usb_cam_ui_state.update_capture_metrics(state, now=5.0, fps=25)
    assert metrics['display_count'] == 1
    assert metrics['cached_frame_count'] == 1
    assert metrics['cached_frame_total_size'] == 4
    assert metrics['cached_session_size'] == 6
    assert metrics['used_size_text'] == '0.0 MB'
    assert 'MB/分钟' in metrics['estimate_text']
    assert metrics['capture_fps_text'].endswith('fps')

    idle_state = dict(state)
    idle_state.update({
        'current_frames_dir': None,
        'cached_frame_count': 0,
        'cached_frame_total_size': 0,
        'current_session': None,
        'cached_session_size': 0,
        'last_ffmpeg_frame': 0,
        'last_display_frame_count': 0,
        'instant_fps': 0.0,
    })
    idle_metrics = usb_cam_ui_state.update_capture_metrics(idle_state, now=1.0, fps=25)
    assert idle_metrics['estimate_text'] == '约 0 MB/分钟'
    assert idle_metrics['capture_fps_text'] == '-- fps'

    recording_state = dict(idle_state)
    recording_state['cached_session_size'] = 10
    recording_metrics = usb_cam_ui_state.update_capture_metrics(recording_state, now=1.0, fps=25)
    assert recording_metrics['estimate_text'] == '录制中，停止后统计图片空间'

    snapshot = {'last_ffmpeg_frame': 0, 'capture_running': True}
    assert usb_cam_ui_state.process_ui_message(snapshot, 'preview_frame', b'data') == ('preview_frame', b'data')
    assert usb_cam_ui_state.process_ui_message(snapshot, 'preview_stopped', None) == ('preview_stopped', None)
    assert usb_cam_ui_state.process_ui_message(snapshot, 'capture_done', None) == ('capture_done', None)
    assert snapshot['capture_running'] is False
    assert usb_cam_ui_state.process_ui_message(snapshot, 'ffmpeg_frame', 'bad') is None
    assert snapshot['last_ffmpeg_frame'] == 0
    assert usb_cam_ui_state.process_ui_message(snapshot, 'unknown', 'x') is None


def test_run_capture_pipeline_video_mode_falls_back_to_q2_and_deletes_video(tmp_path):
    import usb_cam_runtime

    video_dir = tmp_path / 'video'
    frames_dir = tmp_path / 'frames'
    video_dir.mkdir()
    frames_dir.mkdir()
    video_path = video_dir / 'capture_4k25_mjpeg.avi'
    video_path.write_bytes(b'video-bytes')

    meta = {'exit_codes': []}
    calls = []
    frame_counts = [0, 2]

    def fake_run_process(cmd, label, allow_manual_stop=True):
        calls.append((cmd, label, allow_manual_stop))
        return {'record_video': 0, 'extract_frames_copy': 0, 'extract_frames_q2': 0}[label]

    original_count = usb_cam_runtime.count_frame_files
    usb_cam_runtime.count_frame_files = lambda _frames_dir: [object()] * frame_counts.pop(0)
    try:
        usb_cam_runtime.run_capture_pipeline(
            mode='video_then_frames',
            ffmpeg='ffmpeg.exe',
            current_video_dir=video_dir,
            current_frames_dir=frames_dir,
            delete_video_after_extract=True,
            current_meta=meta,
            run_process=fake_run_process,
            build_direct_cmd=lambda ffmpeg: ['direct', ffmpeg],
            build_record_cmd=lambda ffmpeg, path: ['record', ffmpeg, str(path)],
            build_extract_cmd=lambda ffmpeg, path, fallback_q2=False: ['extract', ffmpeg, str(path), str(fallback_q2)],
        )
    finally:
        usb_cam_runtime.count_frame_files = original_count

    assert calls == [
        (['record', 'ffmpeg.exe', str(video_path)], 'record_video', True),
        (['extract', 'ffmpeg.exe', str(video_path), 'False'], 'extract_frames_copy', False),
        (['extract', 'ffmpeg.exe', str(video_path), 'True'], 'extract_frames_q2', False),
    ]
    assert meta['exit_codes'] == [
        {'record_video': 0},
        {'extract_frames_copy': 0},
        {'extract_frames_q2': 0},
    ]
    assert meta['video_deleted_after_extract'] is True
    assert not video_path.exists()


def test_run_capture_pipeline_records_video_delete_error(tmp_path, monkeypatch):
    import usb_cam_runtime

    video_dir = tmp_path / 'video'
    frames_dir = tmp_path / 'frames'
    video_dir.mkdir()
    frames_dir.mkdir()
    video_path = video_dir / 'capture_4k25_mjpeg.avi'
    video_path.write_bytes(b'video-bytes')

    meta = {'exit_codes': []}
    calls = []

    def fake_run_process(cmd, label, allow_manual_stop=True):
        calls.append((cmd, label, allow_manual_stop))
        return 0

    original_unlink = Path.unlink
    original_count = usb_cam_runtime.count_frame_files
    monkeypatch.setattr(Path, 'unlink', lambda self: (_ for _ in ()).throw(OSError('cannot delete')))
    usb_cam_runtime.count_frame_files = lambda _frames_dir: [object()]
    try:
        usb_cam_runtime.run_capture_pipeline(
            mode='video_then_frames',
            ffmpeg='ffmpeg.exe',
            current_video_dir=video_dir,
            current_frames_dir=frames_dir,
            delete_video_after_extract=True,
            current_meta=meta,
            run_process=fake_run_process,
            build_direct_cmd=lambda ffmpeg: ['direct', ffmpeg],
            build_record_cmd=lambda ffmpeg, path: ['record', ffmpeg, str(path)],
            build_extract_cmd=lambda ffmpeg, path, fallback_q2=False: ['extract', ffmpeg, str(path), str(fallback_q2)],
        )
    finally:
        usb_cam_runtime.count_frame_files = original_count
        monkeypatch.setattr(Path, 'unlink', original_unlink)

    assert calls == [
        (['record', 'ffmpeg.exe', str(video_path)], 'record_video', True),
        (['extract', 'ffmpeg.exe', str(video_path), 'False'], 'extract_frames_copy', False),
    ]
    assert meta['exit_codes'] == [
        {'record_video': 0},
        {'extract_frames_copy': 0},
    ]
    assert meta['video_delete_error'] == 'cannot delete'
    assert video_path.exists()


def test_preview_lifecycle_helpers():
    module = load_module()

    class DummyVar:
        def __init__(self, value=None):
            self.value = value

        def set(self, value):
            self.value = value

        def get(self):
            return self.value

    class DummyButton:
        def __init__(self):
            self.states = []

        def configure(self, **kwargs):
            self.states.append(kwargs)

    class DummyThread:
        def __init__(self, target=None, daemon=None):
            self.target = target
            self.daemon = daemon
            self.started = False

        def start(self):
            self.started = True

    app = object.__new__(module.App)
    app.camera_name_var = DummyVar('USB Camera')
    app.preview_status_var = DummyVar()
    app.preview_start_btn = DummyButton()
    app.preview_stop_btn = DummyButton()
    app.preview_proc = None

    original_thread = module.threading.Thread
    original_find_ffmpeg = module.find_ffmpeg
    original_start_preview_process = module.start_preview_process
    original_stop_preview_process = module.stop_preview_process
    original_showerror = module.messagebox.showerror

    errors = []
    stopped = []
    start_calls = []
    try:
        module.threading.Thread = DummyThread
        module.find_ffmpeg = lambda: 'ffmpeg.exe'
        module.start_preview_process = lambda ffmpeg, cmd: start_calls.append((ffmpeg, cmd)) or object()
        module.stop_preview_process = lambda proc, wait=False: stopped.append((proc, wait))
        module.messagebox.showerror = lambda title, msg: errors.append((title, msg))

        cmd = app.prepare_preview_start('ffmpeg.exe')
        assert cmd[0] == 'ffmpeg.exe'

        app.preview_reader = lambda: None
        app.preview_stderr_reader = lambda: None
        app.launch_preview_threads()
        assert app.preview_worker.started is True
        assert app.preview_err_worker.started is True

        app.mark_preview_running()
        assert app.preview_status_var.get() == '预览运行中'
        assert app.preview_start_btn.states[-1] == {'state': 'disabled'}
        assert app.preview_stop_btn.states[-1] == {'state': 'normal'}

        app.handle_preview_process_stop()
        assert app.preview_proc is None
        assert app.preview_status_var.get() == '预览已停止'

        app.preview_proc = None
        app.start_preview()
        assert start_calls[-1][0] == 'ffmpeg.exe'
        assert app.preview_status_var.get() == '预览运行中'

        failing = RuntimeError('bad preview')
        app.handle_preview_start_error(failing)
        assert app.preview_proc is None
        assert errors[-1] == ('预览启动失败', 'bad preview')

        fake_proc = object()
        app.preview_proc = fake_proc
        app.stop_preview(wait=True)
        assert stopped[-1] == (fake_proc, True)
        assert app.preview_status_var.get() == '预览已停止'
    finally:
        module.threading.Thread = original_thread
        module.find_ffmpeg = original_find_ffmpeg
        module.start_preview_process = original_start_preview_process
        module.stop_preview_process = original_stop_preview_process
        module.messagebox.showerror = original_showerror


def test_capture_context_helpers():
    import usb_cam_capture_context

    ctx = usb_cam_capture_context.CaptureContext()
    session_dir = Path('/tmp/session')
    frames_dir = Path('/tmp/session/frames')
    video_dir = Path('/tmp/session/video')
    writer = object()
    meta = {'commands': []}

    ctx.assign_session_paths(session_dir, frames_dir, video_dir)
    assert ctx.current_session == session_dir
    assert ctx.current_frames_dir == frames_dir
    assert ctx.current_video_dir == video_dir

    ctx.set_log_writer(writer)
    assert ctx.log_writer is writer
    ctx.clear_log_writer()
    assert ctx.log_writer is None

    ctx.set_meta(meta)
    assert ctx.current_meta == meta
    new_meta = {'commands': [1]}
    ctx.update_meta(new_meta)
    assert ctx.current_meta == new_meta


def test_start_capture_prep_helpers(tmp_path):
    module = load_module()

    class DummyVar:
        def __init__(self, value=None):
            self.value = value

        def set(self, value):
            self.value = value

        def get(self):
            return self.value

    class DummyBoolVar(DummyVar):
        pass

    class DummyState:
        def __init__(self):
            self.start_time = 0.0
            self.reset_calls = 0

        def reset_for_capture(self):
            self.reset_calls += 1

    events = []
    app = object.__new__(module.App)
    app.output_dir_var = DummyVar(str(tmp_path))
    app.camera_name_var = DummyVar('USB Camera')
    app.mode_var = DummyVar('direct_frames')
    app.quality_var = DummyVar('copy')
    app.image_prefix_var = DummyVar('img')
    app.delete_video_var = DummyBoolVar(False)
    app.frame_count_var = DummyVar()
    app.elapsed_var = DummyVar()
    app.used_size_var = DummyVar()
    app.estimate_var = DummyVar()
    app.capture_fps_var = DummyVar()
    app.status_var = DummyVar()
    app.capture_state = DummyState()
    app.capture_context = module.CaptureContext()
    app.set_capture_running = lambda running: events.append(('set_capture_running', running))
    app.after = lambda delay, cb: events.append(('after', delay, cb.__name__))

    class DummyThread:
        def __init__(self, target=None, daemon=None):
            self.target = target
            self.daemon = daemon
            self.started = False

        def start(self):
            self.started = True
            events.append(('thread_start', self.target.__name__))

    original_writer = module.LimitedLogWriter
    original_thread = module.threading.Thread
    original_time = module.time.time
    original_prepare_capture_session = module.capture_helpers.prepare_capture_session
    original_begin_capture_run = module.capture_helpers.begin_capture_run
    writer_events = []

    class DummyWriter:
        def __init__(self, path, max_bytes):
            self.path = path
            self.max_bytes = max_bytes
            writer_events.append((path, max_bytes))

    module.LimitedLogWriter = DummyWriter
    module.threading.Thread = DummyThread
    module.time.time = lambda: 123.456
    try:
        app.reset_capture_display()
        assert app.frame_count_var.get() == '0'
        assert app.elapsed_var.get() == '00:00:00'
        assert app.used_size_var.get() == '0 MB'
        assert app.estimate_var.get() == '约 0 MB/分钟'
        assert app.capture_fps_var.get() == '-- fps'

        log_path = app.prepare_capture_session('ffmpeg.exe', 'direct_frames_mjpeg_4k')
        assert app.capture_context.current_session.exists()
        assert app.capture_context.current_frames_dir.exists()
        assert app.capture_context.current_video_dir.exists()
        assert log_path.name == 'run_log.txt'
        assert writer_events[-1][0] == log_path
        assert app.capture_context.current_meta['ffmpeg'] == 'ffmpeg.exe'
        assert app.capture_context.current_meta['mode'] == 'direct_frames'
        assert app.capture_context.current_meta['output']['image_prefix'] == 'img'

        begin_calls = []
        module.capture_helpers.begin_capture_run = lambda **kwargs: begin_calls.append(kwargs) or DummyThread(target=kwargs['worker_capture'], daemon=True)
        app.worker_capture = lambda: None
        app.begin_capture_run(log_path)
        assert app.start_time == 123.456
        assert app.worker.daemon is True
        call = begin_calls[-1]
        assert call['now'] == 123.456
        assert call['capture_state'] is app.capture_state
        assert call['status_var'] is app.status_var
        assert call['log_path'] == log_path
        call['after_update_timer']()
        assert ('after', 500, 'update_timer') in events
    finally:
        module.LimitedLogWriter = original_writer
        module.threading.Thread = original_thread
        module.time.time = original_time
        module.capture_helpers.prepare_capture_session = original_prepare_capture_session
        module.capture_helpers.begin_capture_run = original_begin_capture_run


def test_preview_ui_apply_helpers():
    module = load_module()

    class DummyVar:
        def __init__(self, value=None):
            self.value = value

        def set(self, value):
            self.value = value

        def get(self):
            return self.value

    class DummyButton:
        def __init__(self):
            self.states = []

        def configure(self, **kwargs):
            self.states.append(kwargs)

    class DummyLabel:
        def __init__(self):
            self.calls = []

        def configure(self, **kwargs):
            self.calls.append(kwargs)

    class DummyProc:
        def __init__(self, poll_result=None):
            self._poll_result = poll_result

        def poll(self):
            return self._poll_result

    app = object.__new__(module.App)
    app.preview_status_var = DummyVar('预览运行中')
    app.preview_start_btn = DummyButton()
    app.preview_stop_btn = DummyButton()
    app.preview_label = DummyLabel()
    app.preview_proc = DummyProc(poll_result=0)
    app.preview_image = None

    fake_img = object()
    app.apply_preview_frame(fake_img)
    assert app.preview_image is fake_img
    assert app.preview_label.calls[-1] == {'image': fake_img, 'text': ''}

    app.apply_preview_status_text('hello')
    assert app.preview_status_var.get() == 'hello'

    app.preview_status_var.set('预览运行中')
    app.apply_preview_stopped_ui()
    assert app.preview_proc is None
    assert app.preview_start_btn.states[-1] == {'state': 'normal'}
    assert app.preview_stop_btn.states[-1] == {'state': 'disabled'}
    assert app.preview_status_var.get() == '预览已停止'

    app.preview_proc = DummyProc(poll_result=0)
    app.preview_status_var.set('预览运行中')
    original_should_apply_preview_stopped_ui = module.preview_helpers.should_apply_preview_stopped_ui
    try:
        should_calls = []
        module.preview_helpers.should_apply_preview_stopped_ui = lambda preview_proc: should_calls.append(preview_proc) or True
        app.handle_preview_stopped()
        assert should_calls[-1] is not None
        assert app.preview_proc is None
        assert app.preview_status_var.get() == '预览已停止'
    finally:
        module.preview_helpers.should_apply_preview_stopped_ui = original_should_apply_preview_stopped_ui

    original_photo = module.tk.PhotoImage
    original_build_preview_frame_image = module.preview_helpers.build_preview_frame_image
    original_preview_frame_error_text = module.preview_helpers.preview_frame_error_text
    try:
        build_calls = []
        module.preview_helpers.build_preview_frame_image = lambda action_data, photo_image_factory: build_calls.append((action_data, photo_image_factory)) or ('IMG', 'built')
        app.handle_preview_frame(b'png-bytes')
        assert build_calls[-1][0] == b'png-bytes'
        assert build_calls[-1][1] is module.tk.PhotoImage
        assert app.preview_image[0] == 'IMG'

        module.preview_helpers.build_preview_frame_image = lambda action_data, photo_image_factory: (_ for _ in ()).throw(ValueError('bad frame'))
        module.preview_helpers.preview_frame_error_text = lambda exc: f'ERR:{exc}'
        app.handle_preview_frame(b'bad-bytes')
        assert app.preview_status_var.get() == 'ERR:bad frame'
    finally:
        module.tk.PhotoImage = original_photo
        module.preview_helpers.build_preview_frame_image = original_build_preview_frame_image
        module.preview_helpers.preview_frame_error_text = original_preview_frame_error_text

    app.handle_preview_status('preview ok')
    assert app.preview_status_var.get() == 'preview ok'


def test_ui_apply_helpers(tmp_path):
    module = load_module()

    class DummyVar:
        def __init__(self, value=None):
            self.value = value

        def set(self, value):
            self.value = value

        def get(self):
            return self.value

    class DummyState:
        def __init__(self):
            self.capture_running = True
            self.snapshot_calls = []
            self.metrics_snapshots = []
            self.finalize_calls = []

        def snapshot_for_metrics(self, current_frames_dir, current_session):
            self.snapshot_calls.append((current_frames_dir, current_session))
            return {'snap': True}

        def apply_metrics_snapshot(self, snapshot):
            self.metrics_snapshots.append(snapshot)

        def apply_finalize_result(self, finalized):
            self.finalize_calls.append(finalized)

    app = object.__new__(module.App)
    app.elapsed_var = DummyVar()
    app.frame_count_var = DummyVar()
    app.used_size_var = DummyVar()
    app.estimate_var = DummyVar()
    app.capture_fps_var = DummyVar()
    app.status_var = DummyVar()
    app.capture_state = DummyState()
    app.capture_context = module.CaptureContext(
        current_frames_dir=tmp_path / 'frames',
        current_session=tmp_path / 'session',
    )
    after_calls = []
    running_calls = []
    app.after = lambda delay, cb: after_calls.append((delay, cb.__name__))
    app.set_capture_running = lambda running: running_calls.append(running)

    metrics = {
        'elapsed_text': '00:01:23',
        'display_count': 12,
        'used_size_text': '10 MB',
        'estimate_text': '约 7 MB/分钟',
        'capture_fps_text': '25 fps',
    }
    app.apply_capture_metrics(metrics)
    assert app.elapsed_var.get() == '00:01:23'
    assert app.frame_count_var.get() == '12'
    assert app.used_size_var.get() == '10 MB'
    assert app.estimate_var.get() == '约 7 MB/分钟'
    assert app.capture_fps_var.get() == '25 fps'

    original_time = module.time.time
    original_update_capture_metrics = module.update_capture_metrics
    original_finalize_capture_done_state = module.finalize_capture_done_state
    original_update_capture_timer_tick = module.capture_helpers.update_capture_timer_tick
    original_finalize_capture_done = module.capture_helpers.finalize_capture_done
    try:
        module.time.time = lambda: 123.0
        timer_calls = []
        module.capture_helpers.update_capture_timer_tick = lambda **kwargs: timer_calls.append(kwargs) or metrics
        app.update_timer()
        assert timer_calls[-1]['capture_state'] is app.capture_state
        assert timer_calls[-1]['capture_context'] is app.capture_context
        assert timer_calls[-1]['now'] == 123.0
        assert timer_calls[-1]['fps'] == 25
        assert timer_calls[-1]['update_capture_metrics_fn'] is module.update_capture_metrics
        assert after_calls[-1] == (500, 'update_timer')

        finalized = {
            'cached_frame_count': 12,
            'frame_count_text': '12',
            'cached_session_size': 10485760,
            'used_size_text': '10 MB',
        }
        app.apply_capture_done_ui(finalized)
        assert app.capture_state.finalize_calls[-1] == finalized
        assert app.frame_count_var.get() == '12'
        assert app.used_size_var.get() == '10 MB'

        finalize_calls = []
        module.capture_helpers.finalize_capture_done = lambda **kwargs: finalize_calls.append(kwargs) or finalized
        app.handle_capture_done()
        assert finalize_calls[-1]['capture_context'] is app.capture_context
        assert finalize_calls[-1]['finalize_capture_done_state_fn'] is module.finalize_capture_done_state
        assert running_calls[-1] is False
        assert app.status_var.get() == '已停止/完成。'
    finally:
        module.time.time = original_time
        module.update_capture_metrics = original_update_capture_metrics
        module.finalize_capture_done_state = original_finalize_capture_done_state
        module.capture_helpers.update_capture_timer_tick = original_update_capture_timer_tick
        module.capture_helpers.finalize_capture_done = original_finalize_capture_done


def test_run_process_helpers():
    module = load_module()

    class DummyWriter:
        def __init__(self):
            self.writes = []

        def write(self, text):
            self.writes.append(text)

    class DummyQueue:
        def __init__(self):
            self.items = []

        def put(self, item):
            self.items.append(item)

    app = object.__new__(module.App)
    app.ui_queue = DummyQueue()
    app.capture_context = module.CaptureContext(
        current_meta={'commands': []},
        log_writer=DummyWriter(),
    )
    app.proc = None

    original_run_ffmpeg_process = module.capture_helpers.run_ffmpeg_process
    try:
        module.capture_helpers.run_ffmpeg_process = lambda cmd, fps, log_write, frame_callback: (
            frame_callback('frame-1'),
            log_write('ffmpeg-log\n') if log_write else None,
            ('PROC', 17),
        )[-1]

        app.log_capture_command(['ffmpeg', '-i', 'x'], 'record')
        assert app.capture_context.current_meta['commands'][-1] == {'record': ['ffmpeg', '-i', 'x']}
        assert any('[record] COMMAND:' in w for w in app.capture_context.log_writer.writes)

        cb = app.make_ffmpeg_frame_callback()
        cb('frame-2')
        assert app.ui_queue.items[-1] == ('ffmpeg_frame', 'frame-2', None)

        proc, code = app.execute_ffmpeg_command(['ffmpeg', '-i', 'x'])
        assert proc == 'PROC'
        assert code == 17
        assert app.ui_queue.items[-1] == ('ffmpeg_frame', 'frame-1', None)

        app.log_capture_exit_code('record', 17)
        assert any('[record] EXIT_CODE=17' in w for w in app.capture_context.log_writer.writes)

        code2 = app.run_process(['ffmpeg', '-i', 'x'], 'record')
        assert code2 == 17
        assert app.proc is None
    finally:
        module.capture_helpers.run_ffmpeg_process = original_run_ffmpeg_process


def test_capture_execution_and_finalize_helpers(tmp_path):
    module = load_module()

    events = []

    class DummyWriter:
        def __init__(self):
            self.writes = []
            self.closed = False

        def write(self, text):
            self.writes.append(text)

        def close(self):
            self.closed = True

    class DummyQueue:
        def __init__(self):
            self.items = []

        def put(self, item):
            self.items.append(item)

    class DummyVar:
        def __init__(self, value=None):
            self.value = value

        def set(self, value):
            self.value = value

        def get(self):
            return self.value

    app = object.__new__(module.App)
    app.mode_var = DummyVar('video_then_frames')
    app.delete_video_var = DummyVar(True)
    app.status_var = DummyVar()
    app.ui_queue = DummyQueue()
    app.proc = object()
    app.start_time = 5.0
    app.capture_context = module.CaptureContext(
        current_session=tmp_path / 'session',
        current_frames_dir=tmp_path / 'session' / 'frames',
        current_video_dir=tmp_path / 'session' / 'video',
        current_meta={'ffmpeg': 'ffmpeg.exe', 'commands': []},
        log_writer=DummyWriter(),
    )
    app.run_process = lambda *args, **kwargs: events.append(('run_process', args, kwargs))
    app.build_direct_cmd = lambda ffmpeg: ('direct', ffmpeg)
    app.build_record_cmd = lambda ffmpeg, video_path: ('record', ffmpeg, video_path)
    app.build_extract_cmd = lambda ffmpeg, video_path, fallback_q2=False: ('extract', ffmpeg, video_path, fallback_q2)

    original_run_capture_pipeline = module.capture_helpers.run_capture_pipeline
    original_finalize_session = module.finalize_session
    try:
        module.capture_helpers.run_capture_pipeline = lambda **kwargs: events.append(('pipeline', kwargs))
        app.execute_capture_pipeline('ffmpeg.exe')
        assert events[-1][0] == 'pipeline'
        assert events[-1][1]['ffmpeg'] == 'ffmpeg.exe'
        assert events[-1][1]['current_meta'] is app.capture_context.current_meta
        assert events[-1][1]['current_frames_dir'] == app.capture_context.current_frames_dir

        app.handle_capture_exception(RuntimeError('boom'))
        assert '运行异常：boom' in app.status_var.value
        assert any('运行异常：boom' in w for w in app.capture_context.log_writer.writes)

        app.close_capture_resources()
        assert app.capture_context.log_writer is None
        assert app.proc is None
        assert app.ui_queue.items[-1] == ('capture_done', None, None)

        writer2 = DummyWriter()
        app.capture_context.log_writer = writer2
        result = {
            'current_meta': {'ffmpeg': 'ffmpeg.exe', 'commands': [], 'summary': 'ok'},
            'frame_count': 7,
            'meta_path': tmp_path / 'meta.json',
            'summary_path': tmp_path / 'summary.txt',
            'csv_path': tmp_path / 'frames.csv',
        }
        app.finalize_capture_summary(result)
        assert app.capture_context.current_meta == result['current_meta']
        assert any('完成。图片数：7' in w for w in writer2.writes)

        module.finalize_session = lambda **kwargs: result
        app.finish_session()
        assert app.capture_context.current_meta == result['current_meta']

        writer3 = DummyWriter()
        app.capture_context.current_meta = {'ffmpeg': 'ffmpeg.exe', 'commands': []}
        app.capture_context.log_writer = writer3
        app.ui_queue = DummyQueue()
        app.proc = object()
        app.finish_session = lambda: events.append(('finish_session', None))
        app.execute_capture_pipeline = lambda ffmpeg: events.append(('execute_capture_pipeline', ffmpeg))
        app.worker_capture()
        assert ('execute_capture_pipeline', 'ffmpeg.exe') in events
        assert ('finish_session', None) in events
        assert writer3.closed is True
        assert app.capture_context.log_writer is None
        assert app.ui_queue.items[-1] == ('capture_done', None, None)
    finally:
        module.capture_helpers.run_capture_pipeline = original_run_capture_pipeline
        module.finalize_session = original_finalize_session


def test_process_queue_dispatch_helpers():
    module = load_module()

    events = []

    class DummyVar:
        def __init__(self, value=''):
            self.value = value

        def set(self, value):
            self.value = value

        def get(self):
            return self.value

    class DummyWidget:
        def __init__(self):
            self.calls = []

        def configure(self, **kwargs):
            self.calls.append(kwargs)

    class DummyProc:
        def poll(self):
            return 0

    class DummyState:
        def __init__(self):
            self.finalized = None
            self.running = True

        def apply_finalize_result(self, finalized):
            self.finalized = finalized

    app = object.__new__(module.App)
    app.preview_status_var = DummyVar('预览运行中')
    app.preview_start_btn = DummyWidget()
    app.preview_stop_btn = DummyWidget()
    app.preview_label = DummyWidget()
    app.frame_count_var = DummyVar()
    app.used_size_var = DummyVar()
    app.status_var = DummyVar()
    app.capture_state = DummyState()
    app.capture_context = module.CaptureContext()
    app.preview_proc = DummyProc()
    app.set_capture_running = lambda running: events.append(('set_capture_running', running))

    original_photo = module.tk.PhotoImage
    original_finalize = module.finalize_capture_done_state
    original_build_preview_frame_image = module.preview_helpers.build_preview_frame_image
    original_should_apply_preview_stopped_ui = module.preview_helpers.should_apply_preview_stopped_ui
    module.tk.PhotoImage = lambda **kwargs: {'photo': kwargs}
    module.finalize_capture_done_state = lambda _frames_dir, _session: {
        'cached_frame_count': 3,
        'cached_frame_total_size': 4,
        'frame_count_text': '3',
        'cached_session_size': 5,
        'used_size_text': '5.0 MB',
    }
    try:
        preview_build_calls = []
        module.preview_helpers.build_preview_frame_image = lambda action_data, photo_image_factory: preview_build_calls.append((action_data, photo_image_factory)) or {'photo': {'data': 'cG5nLWJ5dGVz', 'format': 'png'}}
        app.handle_preview_frame(b'png-bytes')
        assert preview_build_calls[-1][0] == b'png-bytes'
        assert preview_build_calls[-1][1] is module.tk.PhotoImage
        assert app.preview_image == {'photo': {'data': 'cG5nLWJ5dGVz', 'format': 'png'}}
        assert app.preview_label.calls[-1] == {'image': app.preview_image, 'text': ''}

        app.handle_preview_status('预览正常')
        assert app.preview_status_var.get() == '预览正常'

        app.preview_status_var.set('预览运行中')
        should_calls = []
        module.preview_helpers.should_apply_preview_stopped_ui = lambda preview_proc: should_calls.append(preview_proc) or True
        app.handle_preview_stopped()
        assert should_calls[-1] is not None
        assert app.preview_proc is None
        assert app.preview_start_btn.calls[-1] == {'state': 'normal'}
        assert app.preview_stop_btn.calls[-1] == {'state': 'disabled'}
        assert app.preview_status_var.get() == '预览已停止'

        app.handle_capture_done()
        assert events[-1] == ('set_capture_running', False)
        assert app.status_var.get() == '已停止/完成。'
        assert app.capture_state.finalized['cached_frame_count'] == 3
        assert app.frame_count_var.get() == '3'
        assert app.used_size_var.get() == '5.0 MB'

        routed = []
        app.handle_preview_frame = lambda data: routed.append(('preview_frame', data))
        app.handle_preview_status = lambda data: routed.append(('preview_status', data))
        app.handle_preview_stopped = lambda: routed.append(('preview_stopped', None))
        app.handle_capture_done = lambda: routed.append(('capture_done', None))
        app.dispatch_ui_action('preview_frame', b'a')
        app.dispatch_ui_action('preview_status', 'b')
        app.dispatch_ui_action('preview_stopped', None)
        app.dispatch_ui_action('capture_done', None)
        assert routed == [
            ('preview_frame', b'a'),
            ('preview_status', 'b'),
            ('preview_stopped', None),
            ('capture_done', None),
        ]

        queue_events = []

        class QueueState:
            def __init__(self):
                self.snapshots = []
                self.applied = []

            def queue_snapshot(self):
                snap = {'n': len(self.snapshots) + 1}
                self.snapshots.append(snap)
                return snap

            def apply_queue_snapshot(self, snapshot):
                self.applied.append(snapshot.copy())

        class QueueObj:
            def __init__(self):
                self.items = [('kind1', 'data1', None)]

            def get_nowait(self):
                if not self.items:
                    raise module.queue.Empty()
                return self.items.pop(0)

        queue_state = QueueState()
        queue_obj = QueueObj()
        module.queue_helpers.process_queue_once(
            queue_obj,
            queue_state,
            lambda snapshot, kind, data: queue_events.append(('process', snapshot.copy(), kind, data)) or ('preview_status', 'ok'),
            lambda kind, data: queue_events.append(('dispatch', kind, data)),
        )
        assert queue_events == [
            ('process', {'n': 1}, 'kind1', 'data1'),
            ('dispatch', 'preview_status', 'ok'),
        ]
        assert queue_state.applied == [{'n': 1}]
    finally:
        module.tk.PhotoImage = original_photo
        module.finalize_capture_done_state = original_finalize
        module.preview_helpers.build_preview_frame_image = original_build_preview_frame_image
        module.preview_helpers.should_apply_preview_stopped_ui = original_should_apply_preview_stopped_ui


def test_finalize_capture_done_state_empty_paths():
    import usb_cam_finalize

    result = usb_cam_finalize.finalize_capture_done_state(None, None)
    assert result['cached_frame_count'] is None
    assert result['cached_session_size'] is None


def test_finalize_capture_done_state_populated_paths(tmp_path):
    import usb_cam_finalize

    session_dir = tmp_path / 'session'
    frames_dir = session_dir / 'frames'
    frames_dir.mkdir(parents=True)
    (frames_dir / 'img_000002.jpg').write_bytes(b'22')
    (frames_dir / 'img_000001.jpg').write_bytes(b'1')
    (session_dir / 'run_log.txt').write_bytes(b'abc')

    result = usb_cam_finalize.finalize_capture_done_state(frames_dir, session_dir)

    assert result['cached_frame_count'] == 2
    assert result['cached_frame_total_size'] == 3
    assert result['frame_count_text'] == '2'
    assert result['cached_session_size'] == 6
    assert result['used_size_text'] == '0.0 MB'


def test_write_frames_csv_and_summary_contract(tmp_path):
    import usb_cam_session_writer

    session_dir = tmp_path / 'session'
    frames_dir = session_dir / 'frames'
    frames_dir.mkdir(parents=True)
    (frames_dir / 'img_000002.jpg').write_bytes(b'22')
    (frames_dir / 'img_000001.jpg').write_bytes(b'1')

    csv_path, files = usb_cam_session_writer.write_frames_csv(session_dir, frames_dir)
    csv_text = csv_path.read_text(encoding='utf-8-sig')
    lines = csv_text.strip().splitlines()
    assert [p.name for p in files] == ['img_000001.jpg', 'img_000002.jpg']
    assert lines[0] == 'index,filename,approx_time_s,file_size_bytes'
    assert lines[1] == '1,img_000001.jpg,0.000,1'
    assert lines[2] == '2,img_000002.jpg,0.040,2'

    summary_path = usb_cam_session_writer.write_summary(session_dir, {
        'app': 'usb-cam',
        'created_at': '2026-01-01T00:00:00',
        'camera_name': 'USB Camera',
        'mode': 'direct_frames',
        'quality_mode': 'copy',
        'frame_count': 2,
        'capture_duration_by_frames_s': 0.08,
        'total_process_duration_s': 1.5,
        'effective_fps_by_frames': 25.0,
        'total_frame_size_mb': 0.01,
        'average_frame_size_mb': 0.005,
        'estimated_frames_size_per_min_mb': 15.0,
        'session_total_size_mb': 0.02,
        'delete_video_after_extract': False,
        'video_path': None,
        'frames_dir': str(frames_dir),
        'run_log_path': str(session_dir / 'run_log.txt'),
    })
    summary_text = summary_path.read_text(encoding='utf-8')
    assert 'USB 摄像头 4K25 手动连拍摘要' in summary_text
    assert '应用版本: usb-cam' in summary_text
    assert '图片数量: 2' in summary_text
    assert f'图片目录: {frames_dir}' in summary_text


def test_session_finalize_updates_meta(tmp_path):
    import usb_cam_session_finalize

    session_dir = tmp_path / 'session'
    frames_dir = session_dir / 'frames'
    frames_dir.mkdir(parents=True)
    (frames_dir / 'img_000001.jpg').write_bytes(b'1234')
    meta = {
        'input': {'fps': 25},
    }
    result = usb_cam_session_finalize.finalize_session(
        current_session=session_dir,
        current_frames_dir=frames_dir,
        current_meta=meta,
        start_time=0.0,
    )
    assert result['frame_count'] == 1
    assert 'frames_csv' in result['current_meta']
    assert result['meta_path'].exists()
    assert result['summary_path'].exists()
