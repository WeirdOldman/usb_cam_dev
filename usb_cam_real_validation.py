from __future__ import annotations

import argparse
import json
import os
import psutil
import requests
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


def wait_for_root_ready(
    api_base_url: str,
    *,
    timeout_seconds: float = 10.0,
    poll_seconds: float = 0.5,
) -> tuple[object | None, bool, int, float, str | None]:
    deadline = time.time() + timeout_seconds
    attempts = 0
    last_error = None
    start = time.time()
    while True:
        attempts += 1
        try:
            response = requests.get(f"{api_base_url.rstrip('/')}/", timeout=5)
            return response, bool(response.ok), attempts, max(0.0, time.time() - start), None
        except Exception as exc:
            last_error = str(exc)
        if time.time() >= deadline:
            return None, False, attempts, max(0.0, time.time() - start), last_error
        time.sleep(poll_seconds)


def packaged_runtime_smoke(*, exe_path: Path, api_base_url: str, startup_seconds: float = 8.0) -> dict:
    launch = launch_packaged_runtime(
        exe_path=exe_path,
        startup_seconds=startup_seconds,
    )
    if not launch.get("ok"):
        return launch

    root_ok = False
    root_payload = None
    ffmpeg_found = None
    ffmpeg_path = None
    camera_devices = []
    failure = None
    root_ready_attempts = 0
    root_ready_seconds = 0.0
    try:
        response, root_ok, root_ready_attempts, root_ready_seconds, root_failure = wait_for_root_ready(api_base_url)
        if response is not None:
            try:
                root_payload = response.json()
            except Exception:
                root_payload = response.text
        else:
            failure = root_failure
        if root_ok:
            ffmpeg_response = requests.get(f"{api_base_url.rstrip('/')}/api/system/ffmpeg-status", timeout=5)
            if ffmpeg_response.ok:
                ffmpeg_payload = ffmpeg_response.json()
                ffmpeg_found = ffmpeg_payload.get("ffmpeg_found")
                ffmpeg_path = ffmpeg_payload.get("ffmpeg_path")
            devices_response = requests.get(f"{api_base_url.rstrip('/')}/api/devices/cameras", timeout=5)
            if devices_response.ok:
                devices_payload = devices_response.json()
                camera_devices = devices_payload.get("devices") or []
    except Exception as exc:
        failure = str(exc)
    finally:
        terminate_packaged_runtime(launch["pid"])
        remaining_conflicts = wait_for_capture_process_conflicts_to_clear()
        if remaining_conflicts and failure is None:
            failure = f"cleanup_conflicts_remaining={remaining_conflicts}"

    return {
        "ok": bool(launch.get("alive") and root_ok),
        "pid": launch["pid"],
        "alive": launch.get("alive"),
        "window_title": launch.get("window_title", ""),
        "root_ok": root_ok,
        "root_payload": root_payload,
        "root_ready_attempts": root_ready_attempts,
        "root_ready_seconds": root_ready_seconds,
        "ffmpeg_found": ffmpeg_found,
        "ffmpeg_path": ffmpeg_path,
        "camera_devices": camera_devices,
        "failure_detail": failure,
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


def wait_for_capture_process_conflicts_to_clear(*, timeout_seconds: float = 3.0, poll_seconds: float = 0.25) -> list[dict]:
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


def run_packaged_runtime_smoke_validation(*, exe_path: Path, api_base_url: str, report_path: Path | None = None) -> dict:
    result = packaged_runtime_smoke(
        exe_path=exe_path,
        api_base_url=api_base_url,
    )
    if report_path is None:
        report_path = packaged_report_paths()["smoke"]
    wrapped = {
        "exe_path": str(exe_path),
        "api_base_url": api_base_url,
        "packaged_runtime_smoke": result,
    }
    write_validation_report(report_path, wrapped)
    wrapped["report_path"] = str(report_path)
    return wrapped


def write_validation_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_validation_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_latest_packaged_validation_index(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_packaged_validation_history(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    filtered = []
    for entry in entries:
        summary_report = entry.get("summary_report")
        if not summary_report:
            continue
        try:
            if not Path(summary_report).exists():
                continue
        except Exception:
            continue
        filtered.append(entry)
    path.write_text(json.dumps({"runs": filtered}, ensure_ascii=False, indent=2), encoding="utf-8")


def _numeric_delta(current: dict, previous: dict, key: str) -> int | float | None:
    current_value = current.get(key)
    previous_value = previous.get(key)
    if isinstance(current_value, (int, float)) and isinstance(previous_value, (int, float)):
        return current_value - previous_value
    return None


def _find_previous_comparable_run(entries: list[dict], keys: list[str]) -> tuple[dict | None, list[str]]:
    skipped: list[str] = []
    for entry in entries:
        if any(isinstance(entry.get(key), (int, float)) for key in keys):
            return entry, skipped
        run_id = entry.get("run_id")
        if run_id:
            skipped.append(str(run_id))
    return None, skipped


def derive_release_gate(payload: dict) -> tuple[str, list[str]]:
    summary = payload.get("packaged_validation_summary", {})
    smoke = summary.get("packaged_runtime_smoke", {})
    release = summary.get("packaged_release_validation", {})
    artifacts = release.get("capture_artifacts") or {}
    delta = payload.get("latest_run_delta") or {}
    reasons: list[str] = []
    if not summary.get("ok", False):
        if smoke.get("failure_detail"):
            reasons.append(str(smoke.get("failure_detail")))
        if release.get("failure_detail"):
            reasons.append(str(release.get("failure_detail")))
        monitor = release.get("monitor") or {}
        capture_start = release.get("capture_start") or {}
        capture_stop = release.get("capture_stop") or {}
        capture_error = (
            monitor.get("capture_last_error")
            or capture_stop.get("capture_last_error")
            or capture_start.get("capture_last_error")
            or monitor.get("status_text")
            or capture_stop.get("status_text")
            or capture_start.get("status_text")
        )
        if capture_error and capture_error not in reasons:
            reasons.append(str(capture_error))
        if (artifacts.get("frame_count") or 0) <= 0:
            reasons.append("Capture frames were not produced in the packaged release validation.")
        if artifacts and not artifacts.get("summary_exists"):
            reasons.append("summary.txt was not produced for the packaged release validation.")
        if artifacts and not artifacts.get("metadata_exists"):
            reasons.append("metadata.json was not produced for the packaged release validation.")
        return "fail", reasons
    if isinstance(delta.get("root_ready_seconds"), (int, float)) and delta.get("root_ready_seconds", 0) > 0.0:
        reasons.append(f"Root readiness regressed versus the previous run by {delta.get('root_ready_seconds')} seconds.")
    if isinstance(delta.get("frame_count"), (int, float)) and delta.get("frame_count", 0) < 0:
        reasons.append(f"Frame production regressed versus the previous run by {abs(delta.get('frame_count'))} frames.")
    if (smoke.get("root_ready_attempts") or 0) >= 4 or (smoke.get("root_ready_seconds") or 0.0) >= 3.0:
        reasons.append("Root readiness was slower than the preferred threshold.")
        return "warning", reasons
    if reasons:
        return "warning", reasons
    return "ready", reasons


def release_gate_policy() -> dict:
    return {
        "warning_root_ready_attempts": 4,
        "warning_root_ready_seconds": 3.0,
    }


def write_release_checklist(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    smoke = payload.get("packaged_validation_summary", {}).get("packaged_runtime_smoke", {})
    release = payload.get("packaged_validation_summary", {}).get("packaged_release_validation", {})
    artifacts = release.get("capture_artifacts") or {}
    release_gate, gate_reasons = derive_release_gate(payload)
    checks = [
        ("Root endpoint reachable", bool(smoke.get("root_ok"))),
        ("FFmpeg detected", bool(release.get("ffmpeg_status", {}).get("ffmpeg_found"))),
        ("Preview start succeeded", bool(release.get("preview_start", {}).get("ok"))),
        ("Preview stop succeeded", bool(release.get("preview_stop", {}).get("ok"))),
        ("Capture start succeeded", bool(release.get("capture_start", {}).get("ok"))),
        ("Capture stop succeeded", bool(release.get("capture_stop", {}).get("ok"))),
        ("Capture frames were produced", bool((artifacts.get("frame_count") or 0) > 0)),
        ("frames.csv exists", bool(artifacts.get("frames_csv_exists"))),
        ("summary.txt exists", bool(artifacts.get("summary_exists"))),
        ("metadata.json exists", bool(artifacts.get("metadata_exists"))),
    ]
    lines = ["# Packaged Release Checklist", "", "## Release Gate", f"- Gate: `{release_gate}`"]
    for reason in gate_reasons:
        lines.append(f"- {reason}")
    lines.append("")
    for label, ok in checks:
        lines.append(f"- [{'x' if ok else ' '}] {label}")
    delta = payload.get("latest_run_delta") or {}
    if delta:
        lines.extend([
            "",
            "## Run Delta",
            f"- Root ready seconds vs previous run: `{delta.get('root_ready_seconds')}`",
            f"- Frame count vs previous run: `{delta.get('frame_count')}`",
        ])
    comparison = payload.get("comparison_baseline") or {}
    if comparison:
        lines.extend([
            "",
            "## Comparison Baseline",
            f"- Selected run: `{comparison.get('selected_run_id')}`",
            f"- Skipped runs: `{comparison.get('skipped_run_ids')}`",
        ])
    if not payload.get("packaged_validation_summary", {}).get("ok", False):
        lines.extend([
            "",
            "## Failure Summary",
        ])
        if smoke.get("failure_detail"):
            lines.append(f"- Smoke failure detail: `{smoke.get('failure_detail')}`")
        if release.get("failure_detail"):
            lines.append(f"- Release failure detail: `{release.get('failure_detail')}`")
        lines.extend([
            "",
            "## Suggested Actions",
        ])
        if smoke.get("failure_detail"):
            lines.append("- Check whether packaged runtime child processes are still running and retry after cleanup.")
        if not release.get("ffmpeg_status", {}).get("ffmpeg_found", False):
            lines.append("- Verify FFmpeg is bundled and reachable from the packaged tools directory.")
        if (artifacts.get("frame_count") or 0) <= 0 or not artifacts.get("summary_exists") or not artifacts.get("metadata_exists"):
            lines.append("- Inspect capture session artifacts and backend logs before accepting the build.")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_validation_markdown_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = payload.get("packaged_validation_summary", {})
    smoke = summary.get("packaged_runtime_smoke", {})
    release = summary.get("packaged_release_validation", {})
    artifacts = release.get("capture_artifacts") or {}
    related = payload.get("related_reports", {})
    lines = [
        "# Packaged Validation Summary",
        "",
        f"- Overall ok: `{summary.get('ok')}`",
        f"- Release gate: `{payload.get('release_gate', '')}`",
        f"- Checklist: `{payload.get('checklist_path', '')}`",
        f"- Latest index: `{payload.get('latest_index_path', '')}`",
        f"- History index: `{payload.get('history_index_path', '')}`",
        f"- Gate warning threshold: `attempts >= {payload.get('gate_policy', {}).get('warning_root_ready_attempts')} or seconds >= {payload.get('gate_policy', {}).get('warning_root_ready_seconds')}`",
        f"- Window title: `{smoke.get('window_title', '')}`",
        f"- Root endpoint ok: `{smoke.get('root_ok')}`",
        f"- Root ready attempts: `{smoke.get('root_ready_attempts')}`",
        f"- Root ready seconds: `{smoke.get('root_ready_seconds')}`",
        f"- FFmpeg path: `{smoke.get('ffmpeg_path', '')}`",
        f"- Camera devices: `{smoke.get('camera_devices', [])}`",
        f"- Capture session: `{artifacts.get('session_dir', '')}`",
        f"- Capture frame count: `{artifacts.get('frame_count')}`",
        f"- Frames CSV: `{artifacts.get('frames_csv_path', '')}`",
        f"- Session summary: `{artifacts.get('summary_path', '')}`",
        f"- Session metadata: `{artifacts.get('metadata_path', '')}`",
        f"- Smoke report: `{related.get('smoke', '')}`",
        f"- Release report: `{related.get('release', '')}`",
        f"- Summary report: `{related.get('summary', '')}`",
        "",
    ]
    delta = payload.get("latest_run_delta") or {}
    if delta:
        lines.extend([
            "## Run Delta",
            "",
            f"- Delta root ready seconds vs previous run: `{delta.get('root_ready_seconds')}`",
            f"- Delta frame count vs previous run: `{delta.get('frame_count')}`",
            "",
        ])
    comparison = payload.get("comparison_baseline") or {}
    if comparison:
        lines.extend([
            "## Comparison Baseline",
            "",
            f"- Comparison baseline run: `{comparison.get('selected_run_id')}`",
            f"- Skipped runs before baseline: `{comparison.get('skipped_run_ids')}`",
            "",
        ])
    path.write_text("\n".join(lines), encoding="utf-8")


def packaged_report_paths(base_dir: Path = Path("outputs") / "packaged_runtime") -> dict[str, Path]:
    run_dir = base_dir / time.strftime("%Y-%m-%d_%H%M%S")
    return {
        "root": run_dir,
        "smoke": run_dir / "packaged_runtime_smoke_report.json",
        "release": run_dir / "packaged_release_validation_report.json",
        "summary": run_dir / "packaged_validation_summary_report.json",
    }


def packaged_report_paths_for_summary_report(report_path: Path) -> dict[str, Path]:
    run_dir = report_path.parent
    return {
        "root": run_dir,
        "smoke": run_dir / "packaged_runtime_smoke_report.json",
        "release": run_dir / "packaged_release_validation_report.json",
        "summary": report_path,
    }


def find_latest_session_dir(output_root: Path) -> Path | None:
    candidates = [p for p in output_root.iterdir() if p.is_dir()] if output_root.exists() else []
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.name)[-1]


def collect_finalized_session_artifacts(
    output_root: Path,
    *,
    retries: int = 5,
    delay_seconds: float = 1.0,
) -> dict | None:
    for attempt in range(retries):
        latest_session = find_latest_session_dir(output_root)
        if latest_session is None:
            time.sleep(delay_seconds)
            continue
        artifacts = collect_session_artifacts(latest_session, latest_session / "frames")
        if artifacts.get("summary_exists") and artifacts.get("metadata_exists"):
            return artifacts
        if attempt < retries - 1:
            time.sleep(delay_seconds)
    return artifacts if "artifacts" in locals() else None


def collect_terminal_monitor_state(
    api_base_url: str,
    *,
    retries: int = 10,
    delay_seconds: float = 1.0,
) -> dict:
    last_payload: dict = {}
    for attempt in range(retries):
        try:
            payload = requests.get(f"{api_base_url.rstrip('/')}/api/monitor", timeout=5).json()
        except Exception:
            payload = last_payload
        if isinstance(payload, dict):
            last_payload = payload
        if last_payload and not last_payload.get("running", False):
            return last_payload
        if attempt < retries - 1:
            time.sleep(delay_seconds)
    return last_payload


def packaged_release_validation(*, exe_path: Path, api_base_url: str, output_root: Path, camera_name: str) -> dict:
    launch = launch_packaged_runtime(
        exe_path=exe_path,
    )
    if not launch.get("ok"):
        return {
            "ok": False,
            "packaged_runtime_smoke": launch,
            "capture_artifacts": None,
            "window_title": launch.get("window_title", ""),
            "camera_devices": [],
        }

    root_response = requests.get(f"{api_base_url.rstrip('/')}/", timeout=5)
    smoke = {
        "ok": bool(root_response.ok and launch.get("alive")),
        "pid": launch["pid"],
        "alive": launch.get("alive"),
        "window_title": launch.get("window_title", ""),
        "root_ok": bool(root_response.ok),
        "root_payload": root_response.json() if root_response.ok else None,
    }
    if not smoke.get("ok"):
        terminate_packaged_runtime(launch["pid"])
        return {
            "ok": False,
            "packaged_runtime_smoke": smoke,
            "capture_artifacts": None,
            "window_title": smoke.get("window_title", ""),
            "camera_devices": smoke.get("camera_devices", []),
        }

    try:
        ffmpeg_payload = requests.get(f"{api_base_url.rstrip('/')}/api/system/ffmpeg-status", timeout=5).json()
        smoke["ffmpeg_found"] = ffmpeg_payload.get("ffmpeg_found")
        smoke["ffmpeg_path"] = ffmpeg_payload.get("ffmpeg_path")
        devices_payload = requests.get(f"{api_base_url.rstrip('/')}/api/devices/cameras", timeout=5).json()
        smoke["camera_devices"] = devices_payload.get("devices") or []
        config_payload = requests.get(f"{api_base_url.rstrip('/')}/api/config", timeout=5).json()
        preview_start_payload = requests.post(f"{api_base_url.rstrip('/')}/api/preview/start", timeout=10).json()
        time.sleep(2)
        preview_stop_payload = requests.post(f"{api_base_url.rstrip('/')}/api/preview/stop", timeout=10).json()
        capture_start_payload = requests.post(
            f"{api_base_url.rstrip('/')}/api/control/start",
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "mode": "direct_frames",
                "output_dir": str(output_root),
                "image_prefix": DEFAULT_IMAGE_PREFIX,
                "quality_mode": "copy",
                "delete_video_after_extract": False,
                "camera_name": camera_name,
            }),
            timeout=15,
        ).json()
        time.sleep(3)
        capture_stop_payload = requests.post(f"{api_base_url.rstrip('/')}/api/control/stop", timeout=10).json()
        artifacts = collect_finalized_session_artifacts(output_root)
        monitor_payload = collect_terminal_monitor_state(api_base_url)

        ok = bool(
            smoke.get("ok")
            and ffmpeg_payload.get("ffmpeg_found")
            and preview_start_payload.get("ok")
            and preview_stop_payload.get("ok")
            and capture_start_payload.get("ok")
            and capture_stop_payload.get("ok")
            and artifacts is not None
            and artifacts.get("frame_count", 0) > 0
            and artifacts.get("summary_exists")
            and artifacts.get("metadata_exists")
        )
        return {
            "ok": ok,
            "window_title": smoke.get("window_title", ""),
            "camera_devices": devices_payload.get("devices") or [],
            "packaged_runtime_smoke": smoke,
            "config": config_payload,
            "ffmpeg_status": ffmpeg_payload,
            "preview_start": preview_start_payload,
            "preview_stop": preview_stop_payload,
            "capture_start": capture_start_payload,
            "capture_stop": capture_stop_payload,
            "monitor": monitor_payload,
            "capture_artifacts": artifacts,
        }
    finally:
        terminate_packaged_runtime(launch["pid"])


def run_packaged_release_validation(*, exe_path: Path, api_base_url: str, output_root: Path, report_path: Path | None = None, camera_name: str = DEFAULT_CAMERA_NAME) -> dict:
    result = packaged_release_validation(
        exe_path=exe_path,
        api_base_url=api_base_url,
        output_root=output_root,
        camera_name=camera_name,
    )
    if report_path is None:
        report_path = packaged_report_paths()["release"]
    wrapped = {
        "exe_path": str(exe_path),
        "api_base_url": api_base_url,
        "output_root": str(output_root),
        "packaged_release_validation": result,
    }
    write_validation_report(report_path, wrapped)
    wrapped["report_path"] = str(report_path)
    return wrapped


def packaged_validation_summary(*, exe_path: Path, api_base_url: str, output_root: Path, camera_name: str = DEFAULT_CAMERA_NAME) -> dict:
    smoke = packaged_runtime_smoke(
        exe_path=exe_path,
        api_base_url=api_base_url,
    )
    release = packaged_release_validation(
        exe_path=exe_path,
        api_base_url=api_base_url,
        output_root=output_root,
        camera_name=camera_name,
    )
    return {
        "ok": bool(smoke.get("ok") and release.get("ok")),
        "packaged_runtime_smoke": smoke,
        "packaged_release_validation": release,
    }


def run_packaged_validation_summary(*, exe_path: Path, api_base_url: str, output_root: Path, report_path: Path | None = None, camera_name: str = DEFAULT_CAMERA_NAME) -> dict:
    paths = packaged_report_paths() if report_path is None else packaged_report_paths_for_summary_report(report_path)
    smoke_wrapped = run_packaged_runtime_smoke_validation(
        exe_path=exe_path,
        api_base_url=api_base_url,
        report_path=paths["smoke"],
    )
    release_wrapped = run_packaged_release_validation(
        exe_path=exe_path,
        api_base_url=api_base_url,
        output_root=output_root,
        report_path=paths["release"],
        camera_name=camera_name,
    )
    result = {
        "ok": bool(
            smoke_wrapped.get("packaged_runtime_smoke", {}).get("ok")
            and release_wrapped.get("packaged_release_validation", {}).get("ok")
        ),
        "packaged_runtime_smoke": smoke_wrapped.get("packaged_runtime_smoke"),
        "packaged_release_validation": release_wrapped.get("packaged_release_validation"),
    }
    report_path = paths["summary"]
    wrapped = {
        "exe_path": str(exe_path),
        "api_base_url": api_base_url,
        "output_root": str(output_root),
        "packaged_validation_summary": result,
        "related_reports": {
            "smoke": str(paths["smoke"]),
            "release": str(paths["release"]),
            "summary": str(paths["summary"]),
        },
    }
    manifest_path = report_path.with_name("packaged_validation_manifest.json")
    checklist_path = report_path.with_name("packaged_release_checklist.md")
    latest_index_path = report_path.parent.parent / "latest_packaged_validation.json"
    history_index_path = report_path.parent.parent / "packaged_validation_history.json"
    smoke_summary = result.get("packaged_runtime_smoke") or {}
    release_artifacts = result.get("packaged_release_validation", {}).get("capture_artifacts") or {}
    latest_payload = {
        "run_id": report_path.parent.name,
        "run_dir": str(report_path.parent),
        "root_ready_attempts": smoke_summary.get("root_ready_attempts"),
        "root_ready_seconds": smoke_summary.get("root_ready_seconds"),
        "frame_count": release_artifacts.get("frame_count"),
        "total_frame_size_bytes": release_artifacts.get("total_frame_size_bytes"),
    }
    history_entries = [latest_payload]
    if history_index_path.exists():
        try:
            existing = json.loads(history_index_path.read_text(encoding="utf-8")).get("runs") or []
            history_entries.extend(entry for entry in existing if entry.get("run_id") != latest_payload["run_id"])
        except Exception:
            pass
    previous_run, skipped_run_ids = _find_previous_comparable_run(
        history_entries[1:],
        ["root_ready_attempts", "root_ready_seconds", "frame_count", "total_frame_size_bytes"],
    )
    if previous_run is not None:
        delta = {
            "root_ready_attempts": _numeric_delta(latest_payload, previous_run, "root_ready_attempts"),
            "root_ready_seconds": _numeric_delta(latest_payload, previous_run, "root_ready_seconds"),
            "frame_count": _numeric_delta(latest_payload, previous_run, "frame_count"),
            "total_frame_size_bytes": _numeric_delta(latest_payload, previous_run, "total_frame_size_bytes"),
        }
        latest_payload["delta"] = delta
        latest_payload["comparison_baseline"] = {
            "selected_run_id": previous_run.get("run_id"),
            "skipped_run_ids": skipped_run_ids,
        }
        result_payload_for_gate = {"packaged_validation_summary": result, "latest_run_delta": delta}
    else:
        result_payload_for_gate = {"packaged_validation_summary": result}
    release_gate, gate_reasons = derive_release_gate(result_payload_for_gate)
    manifest_payload = {
        "run_id": report_path.parent.name,
        "run_dir": str(report_path.parent),
        "overall_ok": result.get("ok"),
        "release_gate": release_gate,
        "release_gate_reasons": gate_reasons,
        "gate_policy": release_gate_policy(),
        "exe_path": str(exe_path),
        "window_title": smoke_summary.get("window_title"),
        "root_ok": smoke_summary.get("root_ok"),
        "root_ready_attempts": smoke_summary.get("root_ready_attempts"),
        "root_ready_seconds": smoke_summary.get("root_ready_seconds"),
        "ffmpeg_path": smoke_summary.get("ffmpeg_path"),
        "camera_devices": smoke_summary.get("camera_devices"),
        "frame_count": release_artifacts.get("frame_count"),
        "total_frame_size_bytes": release_artifacts.get("total_frame_size_bytes"),
        "summary_report": str(report_path),
        "summary_markdown": str(report_path.with_suffix(".md")),
        "smoke_report": str(paths["smoke"]),
        "release_report": str(paths["release"]),
        "release_checklist": str(checklist_path),
        "capture_session_dir": release_artifacts.get("session_dir"),
        "frames_csv_path": release_artifacts.get("frames_csv_path"),
        "summary_path": release_artifacts.get("summary_path"),
        "metadata_path": release_artifacts.get("metadata_path"),
    }
    latest_payload.update({
        "release_gate": manifest_payload["release_gate"],
        "release_gate_reasons": manifest_payload["release_gate_reasons"],
        "summary_report": manifest_payload["summary_report"],
        "summary_markdown": manifest_payload["summary_markdown"],
        "manifest_path": str(manifest_path),
        "checklist_path": str(checklist_path),
    })
    if "delta" in latest_payload:
        wrapped["latest_run_delta"] = delta
        manifest_payload["latest_run_delta"] = delta
    if "comparison_baseline" in latest_payload:
        wrapped["comparison_baseline"] = latest_payload["comparison_baseline"]
        manifest_payload["comparison_baseline"] = latest_payload["comparison_baseline"]
    wrapped["report_path"] = str(report_path)
    wrapped["markdown_report_path"] = str(report_path.with_suffix(".md"))
    wrapped["manifest_path"] = str(manifest_path)
    wrapped["checklist_path"] = str(checklist_path)
    wrapped["latest_index_path"] = str(latest_index_path)
    wrapped["history_index_path"] = str(history_index_path)
    wrapped["release_gate"] = release_gate
    wrapped["release_gate_reasons"] = gate_reasons
    wrapped["gate_policy"] = release_gate_policy()
    write_validation_report(report_path, wrapped)
    write_validation_markdown_report(report_path.with_suffix(".md"), wrapped)
    write_release_checklist(checklist_path, wrapped)
    manifest_payload["report_sizes"] = {
        "summary_report_bytes": report_path.stat().st_size if report_path.exists() else None,
        "summary_markdown_bytes": report_path.with_suffix(".md").stat().st_size if report_path.with_suffix(".md").exists() else None,
        "smoke_report_bytes": paths["smoke"].stat().st_size if paths["smoke"].exists() else None,
        "release_report_bytes": paths["release"].stat().st_size if paths["release"].exists() else None,
        "release_checklist_bytes": checklist_path.stat().st_size if checklist_path.exists() else None,
    }
    write_validation_manifest(manifest_path, manifest_payload)
    write_latest_packaged_validation_index(latest_index_path, latest_payload)
    write_packaged_validation_history(history_index_path, history_entries[:10])
    return wrapped


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
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
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
            api_base_url=args.api_base_url,
            report_path=Path(args.report_path) if args.report_path else None,
        )
    elif args.packaged_validation_summary_only:
        if not args.exe_path:
            raise SystemExit("--packaged-validation-summary-only requires --exe-path")
        result = run_packaged_validation_summary(
            exe_path=Path(args.exe_path),
            api_base_url=args.api_base_url,
            output_root=Path(args.output_root),
            report_path=Path(args.report_path) if args.report_path else None,
            camera_name=args.camera_name,
        )
    elif args.packaged_release_validation_only:
        if not args.exe_path:
            raise SystemExit("--packaged-release-validation-only requires --exe-path")
        result = run_packaged_release_validation(
            exe_path=Path(args.exe_path),
            api_base_url=args.api_base_url,
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
