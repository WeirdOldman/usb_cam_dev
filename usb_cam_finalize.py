from __future__ import annotations

from pathlib import Path

from usb_cam_session_writer import count_frame_files
from usb_cam_stats import bytes_to_mb, folder_size


def finalize_capture_done_state(current_frames_dir: Path | None, current_session: Path | None) -> dict:
    result = {
        'cached_frame_count': None,
        'cached_frame_total_size': None,
        'frame_count_text': None,
        'cached_session_size': None,
        'used_size_text': None,
    }
    if current_frames_dir and current_frames_dir.exists():
        final_files = count_frame_files(current_frames_dir)
        result['cached_frame_count'] = len(final_files)
        result['cached_frame_total_size'] = sum(p.stat().st_size for p in final_files if p.exists())
        result['frame_count_text'] = str(result['cached_frame_count'])
    if current_session and current_session.exists():
        session_size = folder_size(current_session)
        result['cached_session_size'] = session_size
        result['used_size_text'] = f"{bytes_to_mb(session_size):.1f} MB"
    return result
