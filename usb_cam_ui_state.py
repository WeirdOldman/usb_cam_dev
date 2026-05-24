from __future__ import annotations

from pathlib import Path

from usb_cam_stats import bytes_to_mb, disk_free_status, folder_size
from usb_cam_session_writer import count_frame_files


def _seconds_to_hms(total_seconds: float | None) -> str:
    if total_seconds is None:
        return "--:--:--"

    total = max(0, int(total_seconds))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def update_capture_metrics(state, now: float, fps: int):
    elapsed_float = max(0.001, now - state['start_time'])
    elapsed = int(elapsed_float)
    h = elapsed // 3600
    m = (elapsed % 3600) // 60
    s = elapsed % 60

    should_scan_frames = (now - state['last_scan_time']) >= 2.0
    if should_scan_frames and state['current_frames_dir'] and state['current_frames_dir'].exists():
        files = count_frame_files(state['current_frames_dir'])
        state['cached_frame_count'] = len(files)
        state['cached_frame_total_size'] = sum(p.stat().st_size for p in files if p.exists())
        state['last_scan_time'] = now

    display_count = max(state['cached_frame_count'], state['last_ffmpeg_frame'], state['last_display_frame_count'])
    state['last_display_frame_count'] = display_count

    should_scan_session = (now - state['last_session_size_scan_time']) >= 5.0
    if should_scan_session and state['current_session'] and state['current_session'].exists():
        state['cached_session_size'] = folder_size(state['current_session'])
        state['last_session_size_scan_time'] = now

    if state['cached_frame_count'] and state['cached_frame_total_size']:
        avg = state['cached_frame_total_size'] / state['cached_frame_count']
        per_min = avg * fps * 60
    else:
        per_min = 0.0

    if display_count and (now - state['last_fps_sample_time']) >= 1.0:
        delta_frames = max(0, display_count - state['last_fps_sample_count'])
        delta_time = max(0.001, now - state['last_fps_sample_time'])
        state['instant_fps'] = delta_frames / delta_time
        state['last_fps_sample_time'] = now
        state['last_fps_sample_count'] = display_count

    disk_status = {
        'disk_free_bytes': 0,
        'disk_free_mb': 0.0,
        'disk_low_space': False,
        'disk_free_warning_text': '',
    }
    if state['current_session'] and state['current_session'].exists():
        disk_status = disk_free_status(state['current_session'])

    write_rate_mb_s = bytes_to_mb(state['cached_session_size']) / elapsed_float if state['cached_session_size'] else 0.0

    estimated_time_left_s = None
    if per_min > 0 and disk_status['disk_free_bytes'] > 0:
        estimated_time_left_s = disk_status['disk_free_bytes'] / (per_min / 60.0)

    capture_health = 'unknown'
    capture_health_reason = 'insufficient_data'
    if disk_status['disk_low_space']:
        capture_health = 'warning'
        capture_health_reason = 'disk_low_space'
    elif state['instant_fps'] > 0 and state['instant_fps'] < (fps * 0.7):
        capture_health = 'warning'
        capture_health_reason = 'fps_below_threshold'
    elif display_count or state['cached_session_size']:
        capture_health = 'ok'
        capture_health_reason = 'stable'

    state['last_write_rate_mb_s'] = write_rate_mb_s
    state['last_estimated_time_left_s'] = estimated_time_left_s
    state['last_health_status'] = capture_health

    if state['cached_frame_count'] and state['cached_frame_total_size']:
        estimate_text = f"约 {bytes_to_mb(per_min):.0f} MB/分钟（仅图片）"
    elif state['cached_session_size']:
        estimate_text = "录制中，停止后统计图片空间"
    else:
        estimate_text = "约 0 MB/分钟"

    return {
        'elapsed_text': f"{h:02d}:{m:02d}:{s:02d}",
        'display_count': display_count,
        'used_size_text': f"{bytes_to_mb(state['cached_session_size']):.1f} MB",
        'estimate_text': estimate_text,
        'capture_fps_text': f"{state['instant_fps']:.2f} fps" if display_count else "-- fps",
        'cached_frame_count': state['cached_frame_count'],
        'cached_frame_total_size': state['cached_frame_total_size'],
        'cached_session_size': state['cached_session_size'],
        'write_rate_mb_s': write_rate_mb_s,
        'estimated_time_left_s': estimated_time_left_s,
        'estimated_time_left_text': _seconds_to_hms(estimated_time_left_s),
        'capture_health': capture_health,
        'capture_health_reason': capture_health_reason,
        **disk_status,
    }


def process_ui_message(state, kind: str, data):
    if kind == 'preview_frame':
        return ('preview_frame', data)
    if kind == 'preview_status':
        return ('preview_status', str(data)[:80])
    if kind == 'preview_stopped':
        return ('preview_stopped', None)
    if kind == 'ffmpeg_frame':
        try:
            state['last_ffmpeg_frame'] = max(state['last_ffmpeg_frame'], int(data))
        except Exception:
            pass
        return None
    if kind == 'capture_done':
        state['capture_running'] = False
        return ('capture_done', None)
    return None
