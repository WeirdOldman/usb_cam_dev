from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from usb_cam_session_writer import write_frames_csv, write_metadata, write_summary
from usb_cam_stats import bytes_to_mb, folder_size, frame_metrics


def finalize_session(*, current_session: Path, current_frames_dir: Path, current_meta: dict, start_time: float):
    csv_path, files = write_frames_csv(current_session, current_frames_dir)
    total_size = sum(p.stat().st_size for p in files if p.exists())
    frame_count = len(files)
    capture_duration = frame_count / current_meta['input']['fps'] if frame_count else 0.0
    total_process = time.time() - start_time
    current_meta.update({
        'manual_stop_time': datetime.now().isoformat(timespec='seconds'),
        'frames_csv': str(csv_path),
        **frame_metrics(
            frame_count=frame_count,
            capture_duration=capture_duration,
            total_process=total_process,
            total_size=total_size,
        ),
    })

    finalize_errors = []
    current_meta['finalize_errors'] = finalize_errors

    meta_path = None
    try:
        meta_path = write_metadata(current_session, current_meta)
    except Exception as exc:
        finalize_errors.append(f'metadata_write_initial: {exc}')

    summary_path = None
    try:
        summary_path = write_summary(current_session, current_meta)
    except Exception as exc:
        finalize_errors.append(f'summary_write: {exc}')

    session_total = folder_size(current_session)
    current_meta['session_total_size_bytes'] = session_total
    current_meta['session_total_size_mb'] = bytes_to_mb(session_total)

    try:
        meta_path = write_metadata(current_session, current_meta)
    except Exception as exc:
        finalize_errors.append(f'metadata_write_final: {exc}')

    if summary_path is None:
        try:
            summary_path = write_summary(current_session, current_meta)
        except Exception:
            pass

    return {
        'csv_path': csv_path,
        'meta_path': meta_path,
        'summary_path': summary_path,
        'frame_count': frame_count,
        'current_meta': current_meta,
    }
