from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import psutil

from desktop.automation import run_desktop_automation
from usb_cam_capture import build_direct_cmd, build_extract_cmd, build_record_cmd
from usb_cam_preview import build_preview_cmd, read_preview_frames, start_preview_process, stop_preview_process
from usb_cam_process import parse_ffmpeg_progress_line, request_stop_process, run_ffmpeg_process
from usb_cam_session_finalize import finalize_session
from usb_cam_session_writer import count_frame_files, make_session
from usb_cam_stop_prefs import evaluate_auto_stop
from usb_cam_validation_capture import (
    run_disk_floor_autostop_validation_impl,
    run_fps_ratio_autostop_validation_impl,
    run_max_duration_autostop_validation_impl,
    run_validation_impl,
    run_video_then_frames_disk_floor_autostop_validation_impl,
    validate_direct_capture_disk_floor_autostop_impl,
    validate_direct_capture_fps_ratio_autostop_impl,
    validate_direct_capture_impl,
    validate_direct_capture_max_duration_autostop_impl,
    validate_video_then_frames_disk_floor_autostop_impl,
    validate_video_then_frames_impl,
)
from usb_cam_validation_packaged import (
    collect_finalized_session_artifacts_impl,
    collect_terminal_monitor_state_impl,
    packaged_release_validation_impl,
    packaged_runtime_smoke_impl,
    run_packaged_validation_summary_impl,
)
from usb_cam_validation_reports import (
    derive_release_gate as derive_release_gate_impl,
    packaged_report_paths as packaged_report_paths_impl,
    packaged_report_paths_for_summary_report as packaged_report_paths_for_summary_report_impl,
    release_gate_policy as release_gate_policy_impl,
    write_latest_packaged_validation_index as write_latest_packaged_validation_index_impl,
    write_packaged_validation_history as write_packaged_validation_history_impl,
    write_release_checklist as write_release_checklist_impl,
    write_validation_manifest as write_validation_manifest_impl,
    write_validation_markdown_report as write_validation_markdown_report_impl,
    write_validation_report as write_validation_report_impl,
)


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
            conflicts.append(
                {
                    "pid": info["pid"],
                    "name": info.get("name"),
                    "cmdline": info.get("cmdline") or [],
                }
            )
    return conflicts


def validation_disk_floor_env(override_mb: float) -> str | None:
    previous = os.environ.get("USB_CAM_AUTOSTOP_DISK_MB")
    os.environ["USB_CAM_AUTOSTOP_DISK_MB"] = str(float(override_mb))
    return previous


def validation_success(result: dict) -> bool:
    for value in result.values():
        if isinstance(value, dict) and "ok" in value and not value.get("ok", False):
            return False
    return True


def launch_packaged_runtime(*, exe_path: Path, startup_seconds: float = 8.0) -> dict:
    conflicts = detect_capture_process_conflicts()
    if conflicts:
        return {
            "ok": False,
            "preflight_failed": True,
            "failure_reason": "camera_in_use",
            "failure_detail": "capture-related process already running before packaged runtime validation",
            "process_conflicts": conflicts,
        }

    proc = subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
    time.sleep(startup_seconds)

    alive = psutil.pid_exists(proc.pid)
    window_title = read_packaged_window_title(proc.pid)
    return {
        "ok": bool(alive),
        "pid": proc.pid,
        "alive": alive,
        "window_title": window_title,
    }


def terminate_packaged_runtime(pid: int) -> None:
    try:
        proc = psutil.Process(pid)
        children = proc.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except Exception:
                pass
        for child in children:
            try:
                child.wait(timeout=5)
            except psutil.TimeoutExpired:
                try:
                    child.kill()
                except Exception:
                    pass
            except Exception:
                pass
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except psutil.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
    except Exception:
        pass


def wait_for_capture_process_conflicts_to_clear(
    *, timeout_seconds: float = 3.0, poll_seconds: float = 0.25
) -> list[dict]:
    deadline = time.time() + timeout_seconds
    while True:
        conflicts = detect_capture_process_conflicts()
        if not conflicts:
            return []
        if time.time() >= deadline:
            return conflicts
        time.sleep(poll_seconds)


def read_packaged_window_title(pid: int) -> str:
    try:
        proc = psutil.Process(pid)
        return proc.name()
    except Exception:
        return ""


def packaged_runtime_smoke(*, exe_path: Path, startup_seconds: float = 8.0) -> dict:
    return packaged_runtime_smoke_impl(
        exe_path=exe_path,
        startup_seconds=startup_seconds,
        run_desktop_automation_fn=run_desktop_automation,
    )


def run_packaged_runtime_smoke_validation(
    *, exe_path: Path, report_path: Path | None = None
) -> dict:
    result = packaged_runtime_smoke(
        exe_path=exe_path,
    )
    if report_path is None:
        report_path = packaged_report_paths()["smoke"]
    wrapped = {
        "exe_path": str(exe_path),
        "packaged_runtime_smoke": result,
    }
    write_validation_report(report_path, wrapped)
    wrapped["report_path"] = str(report_path)
    return wrapped


def write_validation_report(path: Path, payload: dict) -> None:
    write_validation_report_impl(path, payload)


def write_validation_manifest(path: Path, payload: dict) -> None:
    write_validation_manifest_impl(path, payload)


def write_latest_packaged_validation_index(path: Path, payload: dict) -> None:
    write_latest_packaged_validation_index_impl(path, payload)


def write_packaged_validation_history(path: Path, entries: list[dict]) -> None:
    write_packaged_validation_history_impl(path, entries)


def derive_release_gate(payload: dict) -> tuple[str, list[str]]:
    return derive_release_gate_impl(payload)


def release_gate_policy() -> dict:
    return release_gate_policy_impl()


def write_release_checklist(path: Path, payload: dict) -> None:
    write_release_checklist_impl(path, payload)


def write_validation_markdown_report(path: Path, payload: dict) -> None:
    write_validation_markdown_report_impl(path, payload)


def packaged_report_paths(base_dir: Path = Path("outputs") / "packaged_runtime") -> dict[str, Path]:
    return packaged_report_paths_impl(base_dir)


def packaged_report_paths_for_summary_report(report_path: Path) -> dict[str, Path]:
    return packaged_report_paths_for_summary_report_impl(report_path)


def find_latest_session_dir(output_root: Path) -> Path | None:
    candidates = [p for p in output_root.iterdir() if p.is_dir()] if output_root.exists() else []
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.name)[-1]


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
        "frames_csv_path": str(session / "frames.csv"),
        "summary_exists": (session / "summary.txt").exists(),
        "summary_path": str(session / "summary.txt"),
        "metadata_exists": (session / "metadata.json").exists(),
        "metadata_path": str(session / "metadata.json"),
        "video_files": video_files,
    }


def collect_finalized_session_artifacts(
    output_root: Path,
    *,
    retries: int = 5,
    delay_seconds: float = 1.0,
) -> dict | None:
    return collect_finalized_session_artifacts_impl(
        output_root,
        retries=retries,
        delay_seconds=delay_seconds,
        find_latest_session_dir_fn=find_latest_session_dir,
        collect_session_artifacts_fn=collect_session_artifacts,
        sleep_fn=time.sleep,
    )


def collect_terminal_monitor_state(
    exe_path: Path,
    *,
    retries: int = 10,
    delay_seconds: float = 1.0,
) -> dict:
    return collect_terminal_monitor_state_impl(
        exe_path,
        retries=retries,
        delay_seconds=delay_seconds,
        run_desktop_automation_fn=run_desktop_automation,
        sleep_fn=time.sleep,
    )


def packaged_release_validation(*, exe_path: Path, output_root: Path, camera_name: str) -> dict:
    return packaged_release_validation_impl(
        exe_path=exe_path,
        output_root=output_root,
        camera_name=camera_name,
        run_desktop_automation_fn=run_desktop_automation,
        collect_finalized_session_artifacts_fn=collect_finalized_session_artifacts,
    )


def run_packaged_release_validation(
    *,
    exe_path: Path,
    output_root: Path,
    report_path: Path | None = None,
    camera_name: str = DEFAULT_CAMERA_NAME,
) -> dict:
    result = packaged_release_validation(
        exe_path=exe_path,
        output_root=output_root,
        camera_name=camera_name,
    )
    if report_path is None:
        report_path = packaged_report_paths()["release"]
    wrapped = {
        "exe_path": str(exe_path),
        "output_root": str(output_root),
        "packaged_release_validation": result,
    }
    write_validation_report(report_path, wrapped)
    wrapped["report_path"] = str(report_path)
    return wrapped


def packaged_validation_summary(
    *, exe_path: Path, output_root: Path, camera_name: str = DEFAULT_CAMERA_NAME
) -> dict:
    smoke = packaged_runtime_smoke(
        exe_path=exe_path,
    )
    release = packaged_release_validation(
        exe_path=exe_path,
        output_root=output_root,
        camera_name=camera_name,
    )
    return {
        "ok": bool(smoke.get("ok") and release.get("ok")),
        "packaged_runtime_smoke": smoke,
        "packaged_release_validation": release,
    }


def run_packaged_validation_summary(
    *,
    exe_path: Path,
    output_root: Path,
    report_path: Path | None = None,
    camera_name: str = DEFAULT_CAMERA_NAME,
) -> dict:
    return run_packaged_validation_summary_impl(
        exe_path=exe_path,
        output_root=output_root,
        report_path=report_path,
        camera_name=camera_name,
        packaged_report_paths_fn=packaged_report_paths,
        packaged_report_paths_for_summary_report_fn=packaged_report_paths_for_summary_report,
        run_packaged_runtime_smoke_validation_fn=run_packaged_runtime_smoke_validation,
        run_packaged_release_validation_fn=run_packaged_release_validation,
        write_validation_report_fn=write_validation_report,
        write_validation_markdown_report_fn=write_validation_markdown_report,
        write_release_checklist_fn=write_release_checklist,
        write_validation_manifest_fn=write_validation_manifest,
        write_latest_packaged_validation_index_fn=write_latest_packaged_validation_index,
        write_packaged_validation_history_fn=write_packaged_validation_history,
        derive_release_gate_fn=derive_release_gate,
        release_gate_policy_fn=release_gate_policy,
    )


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
    return validate_direct_capture_impl(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        seconds=seconds,
        make_session_fn=make_session,
        build_direct_cmd_fn=build_direct_cmd,
        run_ffmpeg_process_for_duration_fn=run_ffmpeg_process_for_duration,
        base_meta_fn=_base_meta,
        finalize_session_fn=finalize_session,
        collect_session_artifacts_fn=collect_session_artifacts,
        default_image_prefix=DEFAULT_IMAGE_PREFIX,
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
    )


def validate_direct_capture_disk_floor_autostop(
    *, ffmpeg: str, camera_name: str, output_root: Path, disk_floor_override_mb: float
) -> dict:
    return validate_direct_capture_disk_floor_autostop_impl(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        disk_floor_override_mb=disk_floor_override_mb,
        make_session_fn=make_session,
        build_direct_cmd_fn=build_direct_cmd,
        base_meta_fn=_base_meta,
        validation_disk_floor_env_fn=validation_disk_floor_env,
        subprocess_module=subprocess,
        parse_ffmpeg_progress_line_fn=parse_ffmpeg_progress_line,
        shutil_module=shutil,
        evaluate_auto_stop_fn=evaluate_auto_stop,
        request_stop_process_fn=request_stop_process,
        finalize_session_fn=finalize_session,
        collect_session_artifacts_fn=collect_session_artifacts,
        classify_capture_failure_fn=classify_capture_failure,
        detect_capture_process_conflicts_fn=detect_capture_process_conflicts,
        default_image_prefix=DEFAULT_IMAGE_PREFIX,
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
        os_module=os,
        time_module=time,
    )


def validate_direct_capture_max_duration_autostop(
    *, ffmpeg: str, camera_name: str, output_root: Path, max_duration_s: float
) -> dict:
    return validate_direct_capture_max_duration_autostop_impl(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        max_duration_s=max_duration_s,
        make_session_fn=make_session,
        build_direct_cmd_fn=build_direct_cmd,
        base_meta_fn=_base_meta,
        subprocess_module=subprocess,
        parse_ffmpeg_progress_line_fn=parse_ffmpeg_progress_line,
        evaluate_auto_stop_fn=evaluate_auto_stop,
        request_stop_process_fn=request_stop_process,
        finalize_session_fn=finalize_session,
        collect_session_artifacts_fn=collect_session_artifacts,
        classify_capture_failure_fn=classify_capture_failure,
        detect_capture_process_conflicts_fn=detect_capture_process_conflicts,
        default_image_prefix=DEFAULT_IMAGE_PREFIX,
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
        time_module=time,
    )


def validate_direct_capture_fps_ratio_autostop(
    *, ffmpeg: str, camera_name: str, output_root: Path, min_effective_fps_ratio: float
) -> dict:
    return validate_direct_capture_fps_ratio_autostop_impl(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        min_effective_fps_ratio=min_effective_fps_ratio,
        make_session_fn=make_session,
        build_direct_cmd_fn=build_direct_cmd,
        base_meta_fn=_base_meta,
        subprocess_module=subprocess,
        parse_ffmpeg_progress_line_fn=parse_ffmpeg_progress_line,
        evaluate_auto_stop_fn=evaluate_auto_stop,
        request_stop_process_fn=request_stop_process,
        finalize_session_fn=finalize_session,
        collect_session_artifacts_fn=collect_session_artifacts,
        classify_capture_failure_fn=classify_capture_failure,
        detect_capture_process_conflicts_fn=detect_capture_process_conflicts,
        default_image_prefix=DEFAULT_IMAGE_PREFIX,
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
        time_module=time,
    )


def validate_video_then_frames_disk_floor_autostop(
    *, ffmpeg: str, camera_name: str, output_root: Path, disk_floor_override_mb: float
) -> dict:
    return validate_video_then_frames_disk_floor_autostop_impl(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        disk_floor_override_mb=disk_floor_override_mb,
        make_session_fn=make_session,
        build_record_cmd_fn=build_record_cmd,
        base_meta_fn=_base_meta,
        validation_disk_floor_env_fn=validation_disk_floor_env,
        subprocess_module=subprocess,
        parse_ffmpeg_progress_line_fn=parse_ffmpeg_progress_line,
        shutil_module=shutil,
        evaluate_auto_stop_fn=evaluate_auto_stop,
        request_stop_process_fn=request_stop_process,
        finalize_session_fn=finalize_session,
        collect_session_artifacts_fn=collect_session_artifacts,
        classify_capture_failure_fn=classify_capture_failure,
        detect_capture_process_conflicts_fn=detect_capture_process_conflicts,
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
        os_module=os,
        time_module=time,
    )


def validate_video_then_frames(*, ffmpeg: str, camera_name: str, output_root: Path, seconds: float) -> dict:
    return validate_video_then_frames_impl(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        seconds=seconds,
        make_session_fn=make_session,
        build_record_cmd_fn=build_record_cmd,
        run_ffmpeg_process_for_duration_fn=run_ffmpeg_process_for_duration,
        base_meta_fn=_base_meta,
        build_extract_cmd_fn=build_extract_cmd,
        run_ffmpeg_process_fn=run_ffmpeg_process,
        finalize_session_fn=finalize_session,
        collect_session_artifacts_fn=collect_session_artifacts,
        default_image_prefix=DEFAULT_IMAGE_PREFIX,
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
    )


def run_disk_floor_autostop_validation(
    *, ffmpeg: str, camera_name: str, output_root: Path, disk_floor_override_mb: float
) -> dict:
    return run_disk_floor_autostop_validation_impl(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        disk_floor_override_mb=disk_floor_override_mb,
        detect_capture_process_conflicts_fn=detect_capture_process_conflicts,
        validate_direct_capture_disk_floor_autostop_fn=validate_direct_capture_disk_floor_autostop,
    )


def run_video_then_frames_disk_floor_autostop_validation(
    *, ffmpeg: str, camera_name: str, output_root: Path, disk_floor_override_mb: float
) -> dict:
    return run_video_then_frames_disk_floor_autostop_validation_impl(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        disk_floor_override_mb=disk_floor_override_mb,
        detect_capture_process_conflicts_fn=detect_capture_process_conflicts,
        validate_video_then_frames_disk_floor_autostop_fn=validate_video_then_frames_disk_floor_autostop,
    )


def run_max_duration_autostop_validation(
    *, ffmpeg: str, camera_name: str, output_root: Path, max_duration_s: float
) -> dict:
    return run_max_duration_autostop_validation_impl(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        max_duration_s=max_duration_s,
        detect_capture_process_conflicts_fn=detect_capture_process_conflicts,
        validate_direct_capture_max_duration_autostop_fn=validate_direct_capture_max_duration_autostop,
    )


def run_fps_ratio_autostop_validation(
    *, ffmpeg: str, camera_name: str, output_root: Path, min_effective_fps_ratio: float
) -> dict:
    return run_fps_ratio_autostop_validation_impl(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        min_effective_fps_ratio=min_effective_fps_ratio,
        detect_capture_process_conflicts_fn=detect_capture_process_conflicts,
        validate_direct_capture_fps_ratio_autostop_fn=validate_direct_capture_fps_ratio_autostop,
    )


def run_validation(
    *,
    ffmpeg: str,
    camera_name: str,
    output_root: Path,
    capture_seconds: float,
    preview_seconds: float,
    disk_floor_override_mb: float | None = None,
) -> dict:
    return run_validation_impl(
        ffmpeg=ffmpeg,
        camera_name=camera_name,
        output_root=output_root,
        capture_seconds=capture_seconds,
        preview_seconds=preview_seconds,
        disk_floor_override_mb=disk_floor_override_mb,
        validation_disk_floor_env_fn=validation_disk_floor_env,
        preview_smoke_fn=preview_smoke,
        validate_direct_capture_fn=validate_direct_capture,
        validate_video_then_frames_fn=validate_video_then_frames,
        os_module=os,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Headless real-camera validation for usb_cam_dev")
    parser.add_argument("--ffmpeg")
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
    parser.add_argument("--packaged-runtime-smoke-only", action="store_true")
    parser.add_argument("--packaged-release-validation-only", action="store_true")
    parser.add_argument("--packaged-validation-summary-only", action="store_true")
    parser.add_argument("--exe-path", default=None)
    parser.add_argument("--report-path", default=None)
    args = parser.parse_args()
    packaged_validation_mode = (
        args.packaged_runtime_smoke_only
        or args.packaged_release_validation_only
        or args.packaged_validation_summary_only
    )

    if not packaged_validation_mode and not args.ffmpeg:
        raise SystemExit("--ffmpeg is required for non-packaged validation modes")

    if args.packaged_runtime_smoke_only:
        if not args.exe_path:
            raise SystemExit("--packaged-runtime-smoke-only requires --exe-path")
        result = run_packaged_runtime_smoke_validation(
            exe_path=Path(args.exe_path),
            report_path=Path(args.report_path) if args.report_path else None,
        )
    elif args.packaged_validation_summary_only:
        if not args.exe_path:
            raise SystemExit("--packaged-validation-summary-only requires --exe-path")
        result = run_packaged_validation_summary(
            exe_path=Path(args.exe_path),
            output_root=Path(args.output_root),
            report_path=Path(args.report_path) if args.report_path else None,
            camera_name=args.camera_name,
        )
    elif args.packaged_release_validation_only:
        if not args.exe_path:
            raise SystemExit("--packaged-release-validation-only requires --exe-path")
        result = run_packaged_release_validation(
            exe_path=Path(args.exe_path),
            output_root=Path(args.output_root),
            report_path=Path(args.report_path) if args.report_path else None,
            camera_name=args.camera_name,
        )
    elif args.disk_floor_autostop_only:
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
