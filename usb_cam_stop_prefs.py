from __future__ import annotations


def default_auto_stop_prefs(**overrides) -> dict:
    prefs = {
        'enabled': True,
        'max_duration_s': None,
        'min_disk_free_mb_hard': 5120.0,
        'min_effective_fps_ratio': None,
    }
    prefs.update(overrides)
    return prefs


def evaluate_auto_stop(*, metrics: dict, now: float, state: dict, prefs: dict | None) -> dict:
    prefs = prefs or default_auto_stop_prefs()
    if not prefs.get('enabled'):
        return {
            'auto_stop': False,
            'auto_stop_reason': None,
            'auto_stop_detail': None,
        }

    max_duration_s = prefs.get('max_duration_s')
    elapsed_s = max(0.0, now - state.get('start_time', 0.0))
    if max_duration_s is not None and elapsed_s >= float(max_duration_s):
        return {
            'auto_stop': True,
            'auto_stop_reason': 'max_duration',
            'auto_stop_detail': f'elapsed={elapsed_s:.1f}s limit={float(max_duration_s):.1f}s',
        }

    min_disk_free_mb_hard = prefs.get('min_disk_free_mb_hard')
    if min_disk_free_mb_hard is not None and metrics.get('disk_free_mb', 0.0) < float(min_disk_free_mb_hard):
        return {
            'auto_stop': True,
            'auto_stop_reason': 'disk_low_space',
            'auto_stop_detail': f"free_mb={metrics.get('disk_free_mb', 0.0):.1f} threshold={float(min_disk_free_mb_hard):.1f}",
        }

    min_effective_fps_ratio = prefs.get('min_effective_fps_ratio')
    instant_fps = float(state.get('instant_fps', 0.0))
    target_fps = float(metrics.get('target_fps', 0.0))
    if (
        min_effective_fps_ratio is not None
        and target_fps > 0
        and instant_fps > 0
        and instant_fps < target_fps * float(min_effective_fps_ratio)
    ):
        return {
            'auto_stop': True,
            'auto_stop_reason': 'fps_below_threshold',
            'auto_stop_detail': f'fps={instant_fps:.2f} threshold={target_fps * float(min_effective_fps_ratio):.2f}',
        }

    return {
        'auto_stop': False,
        'auto_stop_reason': None,
        'auto_stop_detail': None,
    }
