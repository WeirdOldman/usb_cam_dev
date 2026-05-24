from __future__ import annotations

import argparse
import json
import os
import psutil
import shutil
import subprocess
import threading
import time
from pathlib import Path

from usb_cam_capture import build_direct_cmd, build_extract_cmd, build_record_cmd
from usb_cam_preview import build_preview_cmd, read_preview_frames, start_preview_process, stop_preview_process
from usb_cam_process import parse_ffmpeg_progress_line, request_stop_process, run_ffmpeg_process
from usb_cam_session_finalize import finalize_session
from usb_cam_session_writer import count_frame_files, make_session
from usb_cam_stop_prefs import evaluate_auto_stop


WIDTH = 3840
HEIGHT = 2160
FPS = 25
DEFAULT_CAMERA_NAME = "imx678' UVC "
DEFAULT_IMAGE_PREFIX = "img"


def classify_capture_failure(*, output_text: str, return_code: int) -> dict:
    lowered = (output_text or "").lower()
    if "device already in use" in lowered:
        return {
            "failure_reason": "camera_in_use",
            "failure_detail": "device already in use by other application",
        }
    return {
        "failure_reason": "capture_failed",
        "failure_detail": f"return_code={return_code}",
    }


def detect_capture_process_conflicts() -> list[dict]:
    current_pid = os.getpid()
    conflicts = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        info = proc.info
        if info["pid"] == current_pid:
            continue
        name = (info.get("name") or "").lower()
        if name in {"ffmpeg.exe", "usb_cam_4k25.exe"}:
            conflicts.append({
                "pid": info["pid"],
                "name": info.get("name"),
                "cmdline": info.get("cmdline") or [],
            })
    return conflicts


def validation_disk_floor_env(override_mb: float) -> str | None:
    previous = os.environ.get("USB_CAM_AUTOSTOP_DISK_MB")
    os.environ["USB_CAM_AUTOSTOP_DISK_MB"] = str(float(override_mb))
    return previous


def validation_success(result: dict) -> bool:
    for value in result.values():
        if isinstance(value, dict) and not value.get("ok", False):
            return False
    return True


def collect_session_artifacts(session: Path, frames_dir: Path) -> dict:
    frame_files = count_frame_files(frames_dir)
    video_dir = session / "video"
    video_files = sorted(p.name for p in video_dir.glob("*") if p.is_file()) if video_dir.exists() else []
    return {
        "session_dir": str(session),
        "frame_count": len(frame_files),
        "frame_names": [p.name for p in frame_files],
        "total_frame_size_bytes": sum(p.stat().st_size for p in frame_files if p.exists()),
        "frames_csv_exists": (session / "frames.csv").exists(),
        "summary_exists": (session / "summary.txt").exists(),
        "metadata_exists": (session / "metadata.json").exists(),
        "video_files": video_files,
    }


def preview_smoke(*, ffmpeg: str, camera_name: str, seconds: float) -> dict:
    cmd = build_preview_cmd(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
        preview_fps=5,
        preview_width=640,
    )
    proc = start_preview_process(ffmpeg, cmd)
    start = time.time()
    frame_counter = {"count": 0}

    def emit(_frame: bytes) -> None:
        frame_counter["count"] += 1
        if time.time() - start >= seconds:
            stop_preview_process(proc)

    try:
        if proc.stdout is None:
            raise RuntimeError("preview stdout unavailable")
        read_preview_frames(proc.stdout, emit)
        if proc.poll() is None:
            stop_preview_process(proc, wait=True)
    finally:
        if proc.poll() is None:
            stop_preview_process(proc, wait=True)

    return {
        "ok": frame_counter["count"] > 0,
        "preview_frames": frame_counter["count"],
        "return_code": proc.returncode,
    }


def _base_meta(*, ffmpeg: str, camera_name: str, mode: str, frames_dir: Path, session_dir: Path, video_path: str | None) -> dict:
    created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "app": "usb_cam_real_validation",
        "created_at": created_at,
        "camera_name": camera_name,
        "mode": mode,
        "quality_mode": "copy",
        "input": {"width": WIDTH, "height": HEIGHT, "fps": FPS, "codec": "mjpeg"},
        "output": {
            "original_size_only": True,
            "scale": "none",
            "dpi_metadata_modified": False,
            "image_prefix": DEFAULT_IMAGE_PREFIX,
        },
        "ffmpeg": ffmpeg,
        "session_dir": str(session_dir),
        "frames_dir": str(frames_dir),
        "video_path": video_path,
        "run_log_path": str(session_dir / "run_log.txt"),
        "run_log_max_bytes": 10 * 1024 * 1024,
        "commands": [],
        "exit_codes": [],
        "delete_video_after_extract": False,
        "manual_start_time": created_at,
        "auto_stopped": False,
        "stop_reason": None,
        "stop_reason_detail": None,
    }


def run_ffmpeg_process_for_duration(cmd: list[str], *, fps: int, seconds: float) -> tuple[subprocess.Popen, int]:
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def stop_later() -> None:
        time.sleep(seconds)
        request_stop_process(proc)

    stopper = threading.Thread(target=stop_later, daemon=True)
    stopper.start()

    assert proc.stdout is not None
    for line in proc.stdout:
        parse_ffmpeg_progress_line(line, fps)

    code = proc.wait()
    stopper.join(timeout=1)
    return proc, code


def validate_direct_capture(*, ffmpeg: str, camera_name: str, output_root: Path, seconds: float) -> dict:
    session, frames_dir, _video_dir = make_session(str(output_root), "direct_frames_validation")
    cmd = build_direct_cmd(ffmpeg, frames_dir, DEFAULT_IMAGE_PREFIX, WIDTH, HEIGHT, FPS, camera_name, "copy")
    start = time.time()
    _proc, code = run_ffmpeg_process_for_duration(cmd, fps=FPS, seconds=seconds)
    meta = _base_meta(ffmpeg=ffmpeg, camera_name=camera_name, mode="direct_frames", frames_dir=frames_dir, session_dir=session, video_path=None)
    meta["commands"].append({"direct_frames": cmd})
    meta["exit_codes"].append({"direct_frames": code})
    finalize_session(current_session=session, current_frames_dir=frames_dir, current_meta=meta, start_time=start)
    artifacts = collect_session_artifacts(session, frames_dir)
    artifacts.update({"ok": artifacts["frame_count"] > 0, "exit_codes": meta["exit_codes"]})
    return artifacts


def validate_direct_capture_disk_floor_autostop(*, ffmpeg: str, camera_name: str, output_root: Path, disk_floor_override_mb: float) -> dict:
    session, frames_dir, _video_dir = make_session(str(output_root), "direct_frames_disk_floor_validation")
    cmd = build_direct_cmd(ffmpeg, frames_dir, DEFAULT_IMAGE_PREFIX, WIDTH, HEIGHT, FPS, camera_name, "copy")
    start = time.time()
    meta = _base_meta(ffmpeg=ffmpeg, camera_name=camera_name, mode="direct_frames", frames_dir=frames_dir, session_dir=session, video_path=None)
    meta["commands"].append({"direct_frames": cmd})
    output_lines = []

    previous_override = validation_disk_floor_env(disk_floor_override_mb)
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        last_frame = 0
        for line in proc.stdout:
            output_lines.append(line)
            parsed = parse_ffmpeg_progress_line(line, FPS)
            if parsed is not None:
                last_frame = max(last_frame, parsed)
                usage = shutil.disk_usage(session)
                metrics = {
                    "disk_free_mb": usage.free / 1024 / 1024,
                    "target_fps": FPS,
                }
                decision = evaluate_auto_stop(
                    metrics=metrics,
                    now=time.time(),
                    state={"start_time": start, "instant_fps": FPS},
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
                    request_stop_process(proc)
                    break
        code = proc.wait()
        meta["exit_codes"].append({"direct_frames": code})
    finally:
        if previous_override is None:
            os.environ.pop("USB_CAM_AUTOSTOP_DISK_MB", None)
        else:
            os.environ["USB_CAM_AUTOSTOP_DISK_MB"] = previous_override

    finalize_session(current_session=session, current_frames_dir=frames_dir, current_meta=meta, start_time=start)
    artifacts = collect_session_artifacts(session, frames_dir)
    failure = classify_capture_failure(output_text="".join(output_lines), return_code=code)
    artifacts.update({
        "ok": bool(meta["auto_stopped"]) and meta["stop_reason"] == "disk_low_space",
        "auto_stopped": meta["auto_stopped"],
        "stop_reason": meta["stop_reason"],
        "stop_reason_detail": meta["stop_reason_detail"],
        **failure,
        "process_conflicts": detect_capture_process_conflicts(),
    })
    return artifacts


def validate_direct_capture_max_duration_autostop(*, ffmpeg: str, camera_name: str, output_root: Path, max_duration_s: float) -> dict:
    session, frames_dir, _video_dir = make_session(str(output_root), "direct_frames_max_duration_validation")
    cmd = build_direct_cmd(ffmpeg, frames_dir, DEFAULT_IMAGE_PREFIX, WIDTH, HEIGHT, FPS, camera_name, "copy")
    start = time.time()
    meta = _base_meta(ffmpeg=ffmpeg, camera_name=camera_name, mode="direct_frames", frames_dir=frames_dir, session_dir=session, video_path=None)
    meta["commands"].append({"direct_frames": cmd})
    output_lines = []

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        output_lines.append(line)
        parsed = parse_ffmpeg_progress_line(line, FPS)
        if parsed is not None:
            decision = evaluate_auto_stop(
                metrics={"disk_free_mb": 999999.0, "target_fps": FPS},
                now=time.time(),
                state={"start_time": start, "instant_fps": FPS},
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
                request_stop_process(proc)
                break
    code = proc.wait()
    meta["exit_codes"].append({"direct_frames": code})

    finalize_session(current_session=session, current_frames_dir=frames_dir, current_meta=meta, start_time=start)
    artifacts = collect_session_artifacts(session, frames_dir)
    failure = classify_capture_failure(output_text="".join(output_lines), return_code=code)
    artifacts.update({
        "ok": bool(meta["auto_stopped"]) and meta["stop_reason"] == "max_duration",
        "auto_stopped": meta["auto_stopped"],
        "stop_reason": meta["stop_reason"],
        "stop_reason_detail": meta["stop_reason_detail"],
        **failure,
        "process_conflicts": detect_capture_process_conflicts(),
    })
    return artifacts


def validate_direct_capture_fps_ratio_autostop(*, ffmpeg: str, camera_name: str, output_root: Path, min_effective_fps_ratio: float) -> dict:
    session, frames_dir, _video_dir = make_session(str(output_root), "direct_frames_fps_ratio_validation")
    cmd = build_direct_cmd(ffmpeg, frames_dir, DEFAULT_IMAGE_PREFIX, WIDTH, HEIGHT, FPS, camera_name, "copy")
    start = time.time()
    meta = _base_meta(ffmpeg=ffmpeg, camera_name=camera_name, mode="direct_frames", frames_dir=frames_dir, session_dir=session, video_path=None)
    meta["commands"].append({"direct_frames": cmd})
    output_lines = []

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        output_lines.append(line)
        parsed = parse_ffmpeg_progress_line(line, FPS)
        if parsed is not None:
            decision = evaluate_auto_stop(
                metrics={"disk_free_mb": 999999.0, "target_fps": FPS},
                now=time.time(),
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
                request_stop_process(proc)
                break
    code = proc.wait()
    meta["exit_codes"].append({"direct_frames": code})

    finalize_session(current_session=session, current_frames_dir=frames_dir, current_meta=meta, start_time=start)
    artifacts = collect_session_artifacts(session, frames_dir)
    failure = classify_capture_failure(output_text="".join(output_lines), return_code=code)
    artifacts.update({
        "ok": bool(meta["auto_stopped"]) and meta["stop_reason"] == "fps_below_threshold",
        "auto_stopped": meta["auto_stopped"],
        "stop_reason": meta["stop_reason"],
        "stop_reason_detail": meta["stop_reason_detail"],
        **failure,
        "process_conflicts": detect_capture_process_conflicts(),
    })
    return artifacts


def validate_video_then_frames_disk_floor_autostop(*, ffmpeg: str, camera_name: str, output_root: Path, disk_floor_override_mb: float) -> dict:
    session, frames_dir, video_dir = make_session(str(output_root), "video_then_frames_disk_floor_validation")
    video_path = video_dir / "capture_4k25_mjpeg.avi"
    cmd = build_record_cmd(ffmpeg, video_path, WIDTH, HEIGHT, FPS, camera_name)
    start = time.time()
    meta = _base_meta(ffmpeg=ffmpeg, camera_name=camera_name, mode="video_then_frames", frames_dir=frames_dir, session_dir=session, video_path=str(video_path))
    meta["commands"].append({"record_video": cmd})
    output_lines = []

    previous_override = validation_disk_floor_env(disk_floor_override_mb)
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        last_frame = 0
        for line in proc.stdout:
            output_lines.append(line)
            parsed = parse_ffmpeg_progress_line(line, FPS)
            if parsed is not None:
                last_frame = max(last_frame, parsed)
                usage = shutil.disk_usage(session)
                metrics = {
                    "disk_free_mb": usage.free / 1024 / 1024,
                    "target_fps": FPS,
                }
                decision = evaluate_auto_stop(
                    metrics=metrics,
                    now=time.time(),
                    state={"start_time": start, "instant_fps": FPS},
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
                    request_stop_process(proc)
                    break
        code = proc.wait()
        meta["exit_codes"].append({"record_video": code})
    finally:
        if previous_override is None:
            os.environ.pop("USB_CAM_AUTOSTOP_DISK_MB", None)
        else:
            os.environ["USB_CAM_AUTOSTOP_DISK_MB"] = previous_override

    finalize_session(current_session=session, current_frames_dir=frames_dir, current_meta=meta, start_time=start)
    artifacts = collect_session_artifacts(session, frames_dir)
    failure = classify_capture_failure(output_text="".join(output_lines), return_code=code)
    artifacts.update({
        "ok": bool(meta["auto_stopped"]) and meta["stop_reason"] == "disk_low_space",
        "auto_stopped": meta["auto_stopped"],
        "stop_reason": meta["stop_reason"],
        "stop_reason_detail": meta["stop_reason_detail"],
        **failure,
        "process_conflicts": detect_capture_process_conflicts(),
    })
    return artifacts


def validate_video_then_frames(*, ffmpeg: str, camera_name: str, output_root: Path, seconds: float) -> dict:
    session, frames_dir, video_dir = make_session(str(output_root), "video_then_frames_validation")
    video_path = video_dir / "capture_4k25_mjpeg.avi"
    record_cmd = build_record_cmd(ffmpeg, video_path, WIDTH, HEIGHT, FPS, camera_name)
    start = time.time()
    _proc, code1 = run_ffmpeg_process_for_duration(record_cmd, fps=FPS, seconds=seconds)
    meta = _base_meta(ffmpeg=ffmpeg, camera_name=camera_name, mode="video_then_frames", frames_dir=frames_dir, session_dir=session, video_path=str(video_path))
    meta["commands"].append({"record_video": record_cmd})
    meta["exit_codes"].append({"record_video": code1})

    if video_path.exists() and video_path.stat().st_size > 0:
        extract_cmd = build_extract_cmd(ffmpeg, video_path, frames_dir, DEFAULT_IMAGE_PREFIX, fallback_q2=False)
        _proc2, code2 = run_ffmpeg_process(extract_cmd, fps=FPS)
        meta["commands"].append({"extract_frames_copy": extract_cmd})
        meta["exit_codes"].append({"extract_frames_copy": code2})

    finalize_session(current_session=session, current_frames_dir=frames_dir, current_meta=meta, start_time=start)
    artifacts = collect_session_artifacts(session, frames_dir)
    artifacts.update({"ok": artifacts["frame_count"] > 0 and len(artifacts["video_files"]) > 0, "exit_codes": meta["exit_codes"]})
    return artifacts


def run_disk_floor_autostop_validation(*, ffmpeg: str, camera_name: str, output_root: Path, disk_floor_override_mb: float) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    conflicts = detect_capture_process_conflicts()
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
    result = validate_direct_capture_disk_floor_autostop(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        disk_floor_override_mb=disk_floor_override_mb,
    )
    return {
        "disk_floor_override_mb": disk_floor_override_mb,
        "disk_floor_autostop": result,
    }


def run_video_then_frames_disk_floor_autostop_validation(*, ffmpeg: str, camera_name: str, output_root: Path, disk_floor_override_mb: float) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    conflicts = detect_capture_process_conflicts()
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
    result = validate_video_then_frames_disk_floor_autostop(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        disk_floor_override_mb=disk_floor_override_mb,
    )
    return {
        "disk_floor_override_mb": disk_floor_override_mb,
        "video_then_frames_disk_floor_autostop": result,
    }


def run_max_duration_autostop_validation(*, ffmpeg: str, camera_name: str, output_root: Path, max_duration_s: float) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    conflicts = detect_capture_process_conflicts()
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
    result = validate_direct_capture_max_duration_autostop(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        max_duration_s=max_duration_s,
    )
    return {
        "max_duration_s": max_duration_s,
        "max_duration_autostop": result,
    }


def run_fps_ratio_autostop_validation(*, ffmpeg: str, camera_name: str, output_root: Path, min_effective_fps_ratio: float) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    conflicts = detect_capture_process_conflicts()
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
    result = validate_direct_capture_fps_ratio_autostop(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        min_effective_fps_ratio=min_effective_fps_ratio,
    )
    return {
        "min_effective_fps_ratio": min_effective_fps_ratio,
        "fps_ratio_autostop": result,
    }


def run_validation(*, ffmpeg: str, camera_name: str, output_root: Path, capture_seconds: float, preview_seconds: float, disk_floor_override_mb: float | None = None) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    previous_override = None
    if disk_floor_override_mb is not None:
        previous_override = validation_disk_floor_env(disk_floor_override_mb)

    try:
        preview = preview_smoke(ffmpeg=ffmpeg, camera_name=camera_name, seconds=preview_seconds)
        direct = validate_direct_capture(ffmpeg=ffmpeg, camera_name=camera_name, output_root=output_root, seconds=capture_seconds)
        video_then_frames = validate_video_then_frames(ffmpeg=ffmpeg, camera_name=camera_name, output_root=output_root, seconds=capture_seconds)
        return {
            "disk_floor_override_mb": disk_floor_override_mb,
            "preview": preview,
            "direct_frames": direct,
            "video_then_frames": video_then_frames,
        }
    finally:
        if disk_floor_override_mb is not None:
            if previous_override is None:
                os.environ.pop("USB_CAM_AUTOSTOP_DISK_MB", None)
            else:
                os.environ["USB_CAM_AUTOSTOP_DISK_MB"] = previous_override


def main() -> int:
    parser = argparse.ArgumentParser(description="Headless real-camera validation for usb_cam_dev")
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--camera-name", default=DEFAULT_CAMERA_NAME)
    parser.add_argument("--output-root", default=str(Path("_validation") / "real_runs"))
    parser.add_argument("--capture-seconds", type=float, default=2.0)
    parser.add_argument("--preview-seconds", type=float, default=2.0)
    parser.add_argument("--disk-floor-override-mb", type=float, default=None)
    parser.add_argument("--max-duration-s", type=float, default=None)
    parser.add_argument("--min-effective-fps-ratio", type=float, default=None)
    parser.add_argument("--disk-floor-autostop-only", action="store_true")
    parser.add_argument("--video-then-frames-disk-floor-autostop-only", action="store_true")
    parser.add_argument("--max-duration-autostop-only", action="store_true")
    parser.add_argument("--fps-ratio-autostop-only", action="store_true")
    args = parser.parse_args()

    if args.disk_floor_autostop_only:
        if args.disk_floor_override_mb is None:
            raise SystemExit("--disk-floor-autostop-only requires --disk-floor-override-mb")
        result = run_disk_floor_autostop_validation(
            ffmpeg=args.ffmpeg,
            camera_name=args.camera_name,
            output_root=Path(args.output_root),
            disk_floor_override_mb=args.disk_floor_override_mb,
        )
    elif args.video_then_frames_disk_floor_autostop_only:
        if args.disk_floor_override_mb is None:
            raise SystemExit("--video-then-frames-disk-floor-autostop-only requires --disk-floor-override-mb")
        result = run_video_then_frames_disk_floor_autostop_validation(
            ffmpeg=args.ffmpeg,
            camera_name=args.camera_name,
            output_root=Path(args.output_root),
            disk_floor_override_mb=args.disk_floor_override_mb,
        )
    elif args.max_duration_autostop_only:
        if args.max_duration_s is None:
            raise SystemExit("--max-duration-autostop-only requires --max-duration-s")
        result = run_max_duration_autostop_validation(
            ffmpeg=args.ffmpeg,
            camera_name=args.camera_name,
            output_root=Path(args.output_root),
            max_duration_s=args.max_duration_s,
        )
    elif args.fps_ratio_autostop_only:
        if args.min_effective_fps_ratio is None:
            raise SystemExit("--fps-ratio-autostop-only requires --min-effective-fps-ratio")
        result = run_fps_ratio_autostop_validation(
            ffmpeg=args.ffmpeg,
            camera_name=args.camera_name,
            output_root=Path(args.output_root),
            min_effective_fps_ratio=args.min_effective_fps_ratio,
        )
    else:
        result = run_validation(
            ffmpeg=args.ffmpeg,
            camera_name=args.camera_name,
            output_root=Path(args.output_root),
            capture_seconds=args.capture_seconds,
            preview_seconds=args.preview_seconds,
            disk_floor_override_mb=args.disk_floor_override_mb,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if validation_success(result) else 1


if __name__ == "__main__":
    raise SystemExit(main())
