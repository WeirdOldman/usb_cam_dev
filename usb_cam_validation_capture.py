from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def validate_direct_capture_impl(
    *,
    ffmpeg: str,
    camera_name: str,
    output_root: Path,
    seconds: float,
    make_session_fn: Callable[..., tuple[Path, Path, Path | None]],
    build_direct_cmd_fn: Callable[..., list[str]],
    run_ffmpeg_process_for_duration_fn: Callable[..., tuple[Any, int]],
    base_meta_fn: Callable[..., dict],
    finalize_session_fn: Callable[..., Any],
    collect_session_artifacts_fn: Callable[[Path, Path], dict],
    default_image_prefix: str,
    width: int,
    height: int,
    fps: int,
) -> dict:
    session, frames_dir, _video_dir = make_session_fn(str(output_root), "direct_frames_validation")
    cmd = build_direct_cmd_fn(ffmpeg, frames_dir, default_image_prefix, width, height, fps, camera_name, "copy")
    start = __import__("time").time()
    _proc, code = run_ffmpeg_process_for_duration_fn(cmd, fps=fps, seconds=seconds)
    meta = base_meta_fn(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        mode="direct_frames",
        frames_dir=frames_dir,
        session_dir=session,
        video_path=None,
    )
    meta["commands"].append({"direct_frames": cmd})
    meta["exit_codes"].append({"direct_frames": code})
    finalize_session_fn(current_session=session, current_frames_dir=frames_dir, current_meta=meta, start_time=start)
    artifacts = collect_session_artifacts_fn(session, frames_dir)
    artifacts.update({"ok": artifacts["frame_count"] > 0, "exit_codes": meta["exit_codes"]})
    return artifacts


def validate_direct_capture_disk_floor_autostop_impl(
    *,
    ffmpeg: str,
    camera_name: str,
    output_root: Path,
    disk_floor_override_mb: float,
    make_session_fn: Callable[..., tuple[Path, Path, Path | None]],
    build_direct_cmd_fn: Callable[..., list[str]],
    base_meta_fn: Callable[..., dict],
    validation_disk_floor_env_fn: Callable[[float], str | None],
    subprocess_module: Any,
    parse_ffmpeg_progress_line_fn: Callable[[str, int], int | None],
    shutil_module: Any,
    evaluate_auto_stop_fn: Callable[..., dict],
    request_stop_process_fn: Callable[[Any], None],
    finalize_session_fn: Callable[..., Any],
    collect_session_artifacts_fn: Callable[[Path, Path], dict],
    classify_capture_failure_fn: Callable[..., dict],
    detect_capture_process_conflicts_fn: Callable[[], list[dict]],
    default_image_prefix: str,
    width: int,
    height: int,
    fps: int,
    os_module: Any,
    time_module: Any,
) -> dict:
    session, frames_dir, _video_dir = make_session_fn(str(output_root), "direct_frames_disk_floor_validation")
    cmd = build_direct_cmd_fn(ffmpeg, frames_dir, default_image_prefix, width, height, fps, camera_name, "copy")
    start = time_module.time()
    meta = base_meta_fn(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        mode="direct_frames",
        frames_dir=frames_dir,
        session_dir=session,
        video_path=None,
    )
    meta["commands"].append({"direct_frames": cmd})
    output_lines: list[str] = []

    previous_override = validation_disk_floor_env_fn(disk_floor_override_mb)
    try:
        proc = subprocess_module.Popen(
            cmd,
            stdin=subprocess_module.PIPE,
            stdout=subprocess_module.PIPE,
            stderr=subprocess_module.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            output_lines.append(line)
            parsed = parse_ffmpeg_progress_line_fn(line, fps)
            if parsed is not None:
                usage = shutil_module.disk_usage(session)
                metrics = {
                    "disk_free_mb": usage.free / 1024 / 1024,
                    "target_fps": fps,
                }
                decision = evaluate_auto_stop_fn(
                    metrics=metrics,
                    now=time_module.time(),
                    state={"start_time": start, "instant_fps": fps},
                    prefs={
                        "enabled": True,
                        "max_duration_s": None,
                        "min_disk_free_mb_hard": disk_floor_override_mb,
                        "min_effective_fps_ratio": None,
                    },
                )
                if decision["auto_stop"]:
                    meta["auto_stopped"] = True
                    meta["stop_reason"] = decision["auto_stop_reason"]
                    meta["stop_reason_detail"] = decision["auto_stop_detail"]
                    request_stop_process_fn(proc)
                    break
        code = proc.wait()
        meta["exit_codes"].append({"direct_frames": code})
    finally:
        if previous_override is None:
            os_module.environ.pop("USB_CAM_AUTOSTOP_DISK_MB", None)
        else:
            os_module.environ["USB_CAM_AUTOSTOP_DISK_MB"] = previous_override

    finalize_session_fn(current_session=session, current_frames_dir=frames_dir, current_meta=meta, start_time=start)
    artifacts = collect_session_artifacts_fn(session, frames_dir)
    failure = classify_capture_failure_fn(output_text="".join(output_lines), return_code=code)
    artifacts.update(
        {
            "ok": bool(meta["auto_stopped"]) and meta["stop_reason"] == "disk_low_space",
            "auto_stopped": meta["auto_stopped"],
            "stop_reason": meta["stop_reason"],
            "stop_reason_detail": meta["stop_reason_detail"],
            **failure,
            "process_conflicts": detect_capture_process_conflicts_fn(),
        }
    )
    return artifacts


def validate_direct_capture_max_duration_autostop_impl(
    *,
    ffmpeg: str,
    camera_name: str,
    output_root: Path,
    max_duration_s: float,
    make_session_fn: Callable[..., tuple[Path, Path, Path | None]],
    build_direct_cmd_fn: Callable[..., list[str]],
    base_meta_fn: Callable[..., dict],
    subprocess_module: Any,
    parse_ffmpeg_progress_line_fn: Callable[[str, int], int | None],
    evaluate_auto_stop_fn: Callable[..., dict],
    request_stop_process_fn: Callable[[Any], None],
    finalize_session_fn: Callable[..., Any],
    collect_session_artifacts_fn: Callable[[Path, Path], dict],
    classify_capture_failure_fn: Callable[..., dict],
    detect_capture_process_conflicts_fn: Callable[[], list[dict]],
    default_image_prefix: str,
    width: int,
    height: int,
    fps: int,
    time_module: Any,
) -> dict:
    session, frames_dir, _video_dir = make_session_fn(str(output_root), "direct_frames_max_duration_validation")
    cmd = build_direct_cmd_fn(ffmpeg, frames_dir, default_image_prefix, width, height, fps, camera_name, "copy")
    start = time_module.time()
    meta = base_meta_fn(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        mode="direct_frames",
        frames_dir=frames_dir,
        session_dir=session,
        video_path=None,
    )
    meta["commands"].append({"direct_frames": cmd})
    output_lines: list[str] = []

    proc = subprocess_module.Popen(
        cmd,
        stdin=subprocess_module.PIPE,
        stdout=subprocess_module.PIPE,
        stderr=subprocess_module.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        output_lines.append(line)
        parsed = parse_ffmpeg_progress_line_fn(line, fps)
        if parsed is not None:
            decision = evaluate_auto_stop_fn(
                metrics={"disk_free_mb": 999999.0, "target_fps": fps},
                now=time_module.time(),
                state={"start_time": start, "instant_fps": fps},
                prefs={
                    "enabled": True,
                    "max_duration_s": max_duration_s,
                    "min_disk_free_mb_hard": None,
                    "min_effective_fps_ratio": None,
                },
            )
            if decision["auto_stop"]:
                meta["auto_stopped"] = True
                meta["stop_reason"] = decision["auto_stop_reason"]
                meta["stop_reason_detail"] = decision["auto_stop_detail"]
                request_stop_process_fn(proc)
                break
    code = proc.wait()
    meta["exit_codes"].append({"direct_frames": code})

    finalize_session_fn(current_session=session, current_frames_dir=frames_dir, current_meta=meta, start_time=start)
    artifacts = collect_session_artifacts_fn(session, frames_dir)
    failure = classify_capture_failure_fn(output_text="".join(output_lines), return_code=code)
    artifacts.update(
        {
            "ok": bool(meta["auto_stopped"]) and meta["stop_reason"] == "max_duration",
            "auto_stopped": meta["auto_stopped"],
            "stop_reason": meta["stop_reason"],
            "stop_reason_detail": meta["stop_reason_detail"],
            **failure,
            "process_conflicts": detect_capture_process_conflicts_fn(),
        }
    )
    return artifacts


def validate_direct_capture_fps_ratio_autostop_impl(
    *,
    ffmpeg: str,
    camera_name: str,
    output_root: Path,
    min_effective_fps_ratio: float,
    make_session_fn: Callable[..., tuple[Path, Path, Path | None]],
    build_direct_cmd_fn: Callable[..., list[str]],
    base_meta_fn: Callable[..., dict],
    subprocess_module: Any,
    parse_ffmpeg_progress_line_fn: Callable[[str, int], int | None],
    evaluate_auto_stop_fn: Callable[..., dict],
    request_stop_process_fn: Callable[[Any], None],
    finalize_session_fn: Callable[..., Any],
    collect_session_artifacts_fn: Callable[[Path, Path], dict],
    classify_capture_failure_fn: Callable[..., dict],
    detect_capture_process_conflicts_fn: Callable[[], list[dict]],
    default_image_prefix: str,
    width: int,
    height: int,
    fps: int,
    time_module: Any,
) -> dict:
    session, frames_dir, _video_dir = make_session_fn(str(output_root), "direct_frames_fps_ratio_validation")
    cmd = build_direct_cmd_fn(ffmpeg, frames_dir, default_image_prefix, width, height, fps, camera_name, "copy")
    start = time_module.time()
    meta = base_meta_fn(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        mode="direct_frames",
        frames_dir=frames_dir,
        session_dir=session,
        video_path=None,
    )
    meta["commands"].append({"direct_frames": cmd})
    output_lines: list[str] = []

    proc = subprocess_module.Popen(
        cmd,
        stdin=subprocess_module.PIPE,
        stdout=subprocess_module.PIPE,
        stderr=subprocess_module.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        output_lines.append(line)
        parsed = parse_ffmpeg_progress_line_fn(line, fps)
        if parsed is not None:
            decision = evaluate_auto_stop_fn(
                metrics={"disk_free_mb": 999999.0, "target_fps": fps},
                now=time_module.time(),
                state={"start_time": start, "instant_fps": 5.0},
                prefs={
                    "enabled": True,
                    "max_duration_s": None,
                    "min_disk_free_mb_hard": None,
                    "min_effective_fps_ratio": min_effective_fps_ratio,
                },
            )
            if decision["auto_stop"]:
                meta["auto_stopped"] = True
                meta["stop_reason"] = decision["auto_stop_reason"]
                meta["stop_reason_detail"] = decision["auto_stop_detail"]
                request_stop_process_fn(proc)
                break
    code = proc.wait()
    meta["exit_codes"].append({"direct_frames": code})

    finalize_session_fn(current_session=session, current_frames_dir=frames_dir, current_meta=meta, start_time=start)
    artifacts = collect_session_artifacts_fn(session, frames_dir)
    failure = classify_capture_failure_fn(output_text="".join(output_lines), return_code=code)
    artifacts.update(
        {
            "ok": bool(meta["auto_stopped"]) and meta["stop_reason"] == "fps_below_threshold",
            "auto_stopped": meta["auto_stopped"],
            "stop_reason": meta["stop_reason"],
            "stop_reason_detail": meta["stop_reason_detail"],
            **failure,
            "process_conflicts": detect_capture_process_conflicts_fn(),
        }
    )
    return artifacts


def validate_video_then_frames_disk_floor_autostop_impl(
    *,
    ffmpeg: str,
    camera_name: str,
    output_root: Path,
    disk_floor_override_mb: float,
    make_session_fn: Callable[..., tuple[Path, Path, Path | None]],
    build_record_cmd_fn: Callable[..., list[str]],
    base_meta_fn: Callable[..., dict],
    validation_disk_floor_env_fn: Callable[[float], str | None],
    subprocess_module: Any,
    parse_ffmpeg_progress_line_fn: Callable[[str, int], int | None],
    shutil_module: Any,
    evaluate_auto_stop_fn: Callable[..., dict],
    request_stop_process_fn: Callable[[Any], None],
    finalize_session_fn: Callable[..., Any],
    collect_session_artifacts_fn: Callable[[Path, Path], dict],
    classify_capture_failure_fn: Callable[..., dict],
    detect_capture_process_conflicts_fn: Callable[[], list[dict]],
    width: int,
    height: int,
    fps: int,
    os_module: Any,
    time_module: Any,
) -> dict:
    session, frames_dir, video_dir = make_session_fn(str(output_root), "video_then_frames_disk_floor_validation")
    video_path = video_dir / "capture_4k25_mjpeg.avi"
    cmd = build_record_cmd_fn(ffmpeg, video_path, width, height, fps, camera_name)
    start = time_module.time()
    meta = base_meta_fn(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        mode="video_then_frames",
        frames_dir=frames_dir,
        session_dir=session,
        video_path=str(video_path),
    )
    meta["commands"].append({"record_video": cmd})
    output_lines: list[str] = []

    previous_override = validation_disk_floor_env_fn(disk_floor_override_mb)
    try:
        proc = subprocess_module.Popen(
            cmd,
            stdin=subprocess_module.PIPE,
            stdout=subprocess_module.PIPE,
            stderr=subprocess_module.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            output_lines.append(line)
            parsed = parse_ffmpeg_progress_line_fn(line, fps)
            if parsed is not None:
                usage = shutil_module.disk_usage(session)
                metrics = {
                    "disk_free_mb": usage.free / 1024 / 1024,
                    "target_fps": fps,
                }
                decision = evaluate_auto_stop_fn(
                    metrics=metrics,
                    now=time_module.time(),
                    state={"start_time": start, "instant_fps": fps},
                    prefs={
                        "enabled": True,
                        "max_duration_s": None,
                        "min_disk_free_mb_hard": disk_floor_override_mb,
                        "min_effective_fps_ratio": None,
                    },
                )
                if decision["auto_stop"]:
                    meta["auto_stopped"] = True
                    meta["stop_reason"] = decision["auto_stop_reason"]
                    meta["stop_reason_detail"] = decision["auto_stop_detail"]
                    request_stop_process_fn(proc)
                    break
        code = proc.wait()
        meta["exit_codes"].append({"record_video": code})
    finally:
        if previous_override is None:
            os_module.environ.pop("USB_CAM_AUTOSTOP_DISK_MB", None)
        else:
            os_module.environ["USB_CAM_AUTOSTOP_DISK_MB"] = previous_override

    finalize_session_fn(current_session=session, current_frames_dir=frames_dir, current_meta=meta, start_time=start)
    artifacts = collect_session_artifacts_fn(session, frames_dir)
    failure = classify_capture_failure_fn(output_text="".join(output_lines), return_code=code)
    artifacts.update(
        {
            "ok": bool(meta["auto_stopped"]) and meta["stop_reason"] == "disk_low_space",
            "auto_stopped": meta["auto_stopped"],
            "stop_reason": meta["stop_reason"],
            "stop_reason_detail": meta["stop_reason_detail"],
            **failure,
            "process_conflicts": detect_capture_process_conflicts_fn(),
        }
    )
    return artifacts


def validate_video_then_frames_impl(
    *,
    ffmpeg: str,
    camera_name: str,
    output_root: Path,
    seconds: float,
    make_session_fn: Callable[..., tuple[Path, Path, Path | None]],
    build_record_cmd_fn: Callable[..., list[str]],
    run_ffmpeg_process_for_duration_fn: Callable[..., tuple[Any, int]],
    base_meta_fn: Callable[..., dict],
    build_extract_cmd_fn: Callable[..., list[str]],
    run_ffmpeg_process_fn: Callable[..., tuple[Any, int]],
    finalize_session_fn: Callable[..., Any],
    collect_session_artifacts_fn: Callable[[Path, Path], dict],
    default_image_prefix: str,
    width: int,
    height: int,
    fps: int,
) -> dict:
    session, frames_dir, video_dir = make_session_fn(str(output_root), "video_then_frames_validation")
    video_path = video_dir / "capture_4k25_mjpeg.avi"
    record_cmd = build_record_cmd_fn(ffmpeg, video_path, width, height, fps, camera_name)
    start = __import__("time").time()
    _proc, code1 = run_ffmpeg_process_for_duration_fn(record_cmd, fps=fps, seconds=seconds)
    meta = base_meta_fn(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        mode="video_then_frames",
        frames_dir=frames_dir,
        session_dir=session,
        video_path=str(video_path),
    )
    meta["commands"].append({"record_video": record_cmd})
    meta["exit_codes"].append({"record_video": code1})

    if video_path.exists() and video_path.stat().st_size > 0:
        extract_cmd = build_extract_cmd_fn(ffmpeg, video_path, frames_dir, default_image_prefix, fallback_q2=False)
        _proc2, code2 = run_ffmpeg_process_fn(extract_cmd, fps=fps)
        meta["commands"].append({"extract_frames_copy": extract_cmd})
        meta["exit_codes"].append({"extract_frames_copy": code2})

    finalize_session_fn(current_session=session, current_frames_dir=frames_dir, current_meta=meta, start_time=start)
    artifacts = collect_session_artifacts_fn(session, frames_dir)
    artifacts.update({"ok": artifacts["frame_count"] > 0 and len(artifacts["video_files"]) > 0, "exit_codes": meta["exit_codes"]})
    return artifacts


def run_disk_floor_autostop_validation_impl(
    *,
    ffmpeg: str,
    camera_name: str,
    output_root: Path,
    disk_floor_override_mb: float,
    detect_capture_process_conflicts_fn: Callable[[], list[dict]],
    validate_direct_capture_disk_floor_autostop_fn: Callable[..., dict],
) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    conflicts = detect_capture_process_conflicts_fn()
    if conflicts:
        return {
            "disk_floor_override_mb": disk_floor_override_mb,
            "disk_floor_autostop": {
                "ok": False,
                "preflight_failed": True,
                "failure_reason": "camera_in_use",
                "failure_detail": "capture-related process already running before validation",
                "process_conflicts": conflicts,
            },
        }
    result = validate_direct_capture_disk_floor_autostop_fn(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        disk_floor_override_mb=disk_floor_override_mb,
    )
    return {
        "disk_floor_override_mb": disk_floor_override_mb,
        "disk_floor_autostop": result,
    }


def run_video_then_frames_disk_floor_autostop_validation_impl(
    *,
    ffmpeg: str,
    camera_name: str,
    output_root: Path,
    disk_floor_override_mb: float,
    detect_capture_process_conflicts_fn: Callable[[], list[dict]],
    validate_video_then_frames_disk_floor_autostop_fn: Callable[..., dict],
) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    conflicts = detect_capture_process_conflicts_fn()
    if conflicts:
        return {
            "disk_floor_override_mb": disk_floor_override_mb,
            "video_then_frames_disk_floor_autostop": {
                "ok": False,
                "preflight_failed": True,
                "failure_reason": "camera_in_use",
                "failure_detail": "capture-related process already running before validation",
                "process_conflicts": conflicts,
            },
        }
    result = validate_video_then_frames_disk_floor_autostop_fn(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        disk_floor_override_mb=disk_floor_override_mb,
    )
    return {
        "disk_floor_override_mb": disk_floor_override_mb,
        "video_then_frames_disk_floor_autostop": result,
    }


def run_max_duration_autostop_validation_impl(
    *,
    ffmpeg: str,
    camera_name: str,
    output_root: Path,
    max_duration_s: float,
    detect_capture_process_conflicts_fn: Callable[[], list[dict]],
    validate_direct_capture_max_duration_autostop_fn: Callable[..., dict],
) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    conflicts = detect_capture_process_conflicts_fn()
    if conflicts:
        return {
            "max_duration_s": max_duration_s,
            "max_duration_autostop": {
                "ok": False,
                "preflight_failed": True,
                "failure_reason": "camera_in_use",
                "failure_detail": "capture-related process already running before validation",
                "process_conflicts": conflicts,
            },
        }
    result = validate_direct_capture_max_duration_autostop_fn(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        max_duration_s=max_duration_s,
    )
    return {
        "max_duration_s": max_duration_s,
        "max_duration_autostop": result,
    }


def run_fps_ratio_autostop_validation_impl(
    *,
    ffmpeg: str,
    camera_name: str,
    output_root: Path,
    min_effective_fps_ratio: float,
    detect_capture_process_conflicts_fn: Callable[[], list[dict]],
    validate_direct_capture_fps_ratio_autostop_fn: Callable[..., dict],
) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    conflicts = detect_capture_process_conflicts_fn()
    if conflicts:
        return {
            "min_effective_fps_ratio": min_effective_fps_ratio,
            "fps_ratio_autostop": {
                "ok": False,
                "preflight_failed": True,
                "failure_reason": "camera_in_use",
                "failure_detail": "capture-related process already running before validation",
                "process_conflicts": conflicts,
            },
        }
    result = validate_direct_capture_fps_ratio_autostop_fn(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        min_effective_fps_ratio=min_effective_fps_ratio,
    )
    return {
        "min_effective_fps_ratio": min_effective_fps_ratio,
        "fps_ratio_autostop": result,
    }


def run_validation_impl(
    *,
    ffmpeg: str,
    camera_name: str,
    output_root: Path,
    capture_seconds: float,
    preview_seconds: float,
    disk_floor_override_mb: float | None,
    validation_disk_floor_env_fn: Callable[[float], str | None],
    preview_smoke_fn: Callable[..., dict],
    validate_direct_capture_fn: Callable[..., dict],
    validate_video_then_frames_fn: Callable[..., dict],
    os_module: Any,
) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    previous_override = None
    if disk_floor_override_mb is not None:
        previous_override = validation_disk_floor_env_fn(disk_floor_override_mb)

    try:
        preview = preview_smoke_fn(ffmpeg=ffmpeg, camera_name=camera_name, seconds=preview_seconds)
        direct = validate_direct_capture_fn(
            ffmpeg=ffmpeg,
            camera_name=camera_name,
            output_root=output_root,
            seconds=capture_seconds,
        )
        video_then_frames = validate_video_then_frames_fn(
            ffmpeg=ffmpeg,
            camera_name=camera_name,
            output_root=output_root,
            seconds=capture_seconds,
        )
        return {
            "disk_floor_override_mb": disk_floor_override_mb,
            "preview": preview,
            "direct_frames": direct,
            "video_then_frames": video_then_frames,
        }
    finally:
        if disk_floor_override_mb is not None:
            if previous_override is None:
                os_module.environ.pop("USB_CAM_AUTOSTOP_DISK_MB", None)
            else:
                os_module.environ["USB_CAM_AUTOSTOP_DISK_MB"] = previous_override
