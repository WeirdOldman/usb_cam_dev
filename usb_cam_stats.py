from __future__ import annotations

import shutil
from pathlib import Path


def folder_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for p in path.rglob('*'):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def bytes_to_mb(n: int | float) -> float:
    return float(n) / 1024 / 1024


def disk_free_status(path: Path, warning_threshold_mb: float = 512.0) -> dict:
    try:
        usage = shutil.disk_usage(path)
        free_bytes = int(usage.free)
        free_mb = bytes_to_mb(free_bytes)
        is_low = free_mb < warning_threshold_mb
        return {
            'disk_free_bytes': free_bytes,
            'disk_free_mb': free_mb,
            'disk_low_space': is_low,
            'disk_free_warning_text': f'磁盘剩余空间不足：{free_mb:.1f} MB' if is_low else '',
        }
    except Exception:
        return {
            'disk_free_bytes': 0,
            'disk_free_mb': 0.0,
            'disk_low_space': False,
            'disk_free_warning_text': '',
        }


def frame_metrics(frame_count: int, capture_duration: float, total_process: float, total_size: int) -> dict:
    avg_size = (total_size / frame_count) if frame_count else 0
    estimated_per_min = avg_size * 25 * 60
    return {
        'total_process_duration_s': total_process,
        'capture_duration_by_frames_s': capture_duration,
        'effective_fps_by_frames': frame_count / capture_duration if capture_duration else 0.0,
        'process_average_fps': frame_count / total_process if total_process else 0.0,
        'frame_count': frame_count,
        'total_frame_size_bytes': total_size,
        'total_frame_size_mb': bytes_to_mb(total_size),
        'average_frame_size_bytes': int(avg_size) if frame_count else 0,
        'average_frame_size_mb': bytes_to_mb(avg_size) if frame_count else 0,
        'estimated_frames_size_per_min_bytes': int(estimated_per_min),
        'estimated_frames_size_per_min_mb': bytes_to_mb(estimated_per_min),
    }
