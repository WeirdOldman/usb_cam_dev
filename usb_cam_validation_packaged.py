from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable


def packaged_runtime_smoke_impl(
    *,
    exe_path: Path,
    api_base_url: str,
    startup_seconds: float,
    launch_packaged_runtime_fn: Callable[..., dict],
    requests_get: Callable[..., Any],
    terminate_packaged_runtime_fn: Callable[[int], None],
    wait_for_capture_process_conflicts_to_clear_fn: Callable[..., list[dict]],
) -> dict:
    launch = launch_packaged_runtime_fn(
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
    start = time.time()
    try:
        deadline = start + 10.0
        last_error = None
        while True:
            root_ready_attempts += 1
            try:
                response = requests_get(f"{api_base_url.rstrip('/')}/", timeout=5)
                root_ok = bool(response.ok)
                root_ready_seconds = max(0.0, time.time() - start)
                if response is not None:
                    try:
                        root_payload = response.json()
                    except Exception:
                        root_payload = response.text
                break
            except Exception as exc:
                last_error = str(exc)
            if time.time() >= deadline:
                failure = last_error
                root_ready_seconds = max(0.0, time.time() - start)
                break
            time.sleep(0.5)

        if root_ok:
            ffmpeg_response = requests_get(f"{api_base_url.rstrip('/')}/api/system/ffmpeg-status", timeout=5)
            if ffmpeg_response.ok:
                ffmpeg_payload = ffmpeg_response.json()
                ffmpeg_found = ffmpeg_payload.get("ffmpeg_found")
                ffmpeg_path = ffmpeg_payload.get("ffmpeg_path")
            devices_response = requests_get(f"{api_base_url.rstrip('/')}/api/devices/cameras", timeout=5)
            if devices_response.ok:
                devices_payload = devices_response.json()
                camera_devices = devices_payload.get("devices") or []
    except Exception as exc:
        failure = str(exc)
    finally:
        terminate_packaged_runtime_fn(launch["pid"])
        remaining_conflicts = wait_for_capture_process_conflicts_to_clear_fn()
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


def collect_finalized_session_artifacts_impl(
    output_root: Path,
    *,
    retries: int,
    delay_seconds: float,
    find_latest_session_dir_fn: Callable[[Path], Path | None],
    collect_session_artifacts_fn: Callable[[Path, Path], dict],
    sleep_fn: Callable[[float], None],
) -> dict | None:
    artifacts: dict | None = None
    for attempt in range(retries):
        latest_session = find_latest_session_dir_fn(output_root)
        if latest_session is None:
            sleep_fn(delay_seconds)
            continue
        artifacts = collect_session_artifacts_fn(latest_session, latest_session / "frames")
        if artifacts.get("summary_exists") and artifacts.get("metadata_exists"):
            return artifacts
        if attempt < retries - 1:
            sleep_fn(delay_seconds)
    return artifacts


def collect_terminal_monitor_state_impl(
    api_base_url: str,
    *,
    retries: int,
    delay_seconds: float,
    requests_get: Callable[..., Any],
    sleep_fn: Callable[[float], None],
) -> dict:
    last_payload: dict = {}
    for attempt in range(retries):
        try:
            payload = requests_get(f"{api_base_url.rstrip('/')}/api/monitor", timeout=5).json()
        except Exception:
            payload = last_payload
        if isinstance(payload, dict):
            last_payload = payload
        if last_payload and not last_payload.get("running", False):
            return last_payload
        if attempt < retries - 1:
            sleep_fn(delay_seconds)
    return last_payload


def packaged_release_validation_impl(
    *,
    exe_path: Path,
    api_base_url: str,
    output_root: Path,
    camera_name: str,
    launch_packaged_runtime_fn: Callable[..., dict],
    requests_get: Callable[..., Any],
    requests_post: Callable[..., Any],
    terminate_packaged_runtime_fn: Callable[[int], None],
    collect_finalized_session_artifacts_fn: Callable[[Path], dict | None],
    collect_terminal_monitor_state_fn: Callable[[str], dict],
) -> dict:
    launch = launch_packaged_runtime_fn(exe_path=exe_path)
    if not launch.get("ok"):
        return {
            "ok": False,
            "packaged_runtime_smoke": launch,
            "capture_artifacts": None,
            "window_title": launch.get("window_title", ""),
            "camera_devices": [],
        }

    root_response = requests_get(f"{api_base_url.rstrip('/')}/", timeout=5)
    smoke = {
        "ok": bool(root_response.ok and launch.get("alive")),
        "pid": launch["pid"],
        "alive": launch.get("alive"),
        "window_title": launch.get("window_title", ""),
        "root_ok": bool(root_response.ok),
        "root_payload": root_response.json() if root_response.ok else None,
    }
    if not smoke.get("ok"):
        terminate_packaged_runtime_fn(launch["pid"])
        return {
            "ok": False,
            "packaged_runtime_smoke": smoke,
            "capture_artifacts": None,
            "window_title": smoke.get("window_title", ""),
            "camera_devices": smoke.get("camera_devices", []),
        }

    try:
        ffmpeg_payload = requests_get(f"{api_base_url.rstrip('/')}/api/system/ffmpeg-status", timeout=5).json()
        smoke["ffmpeg_found"] = ffmpeg_payload.get("ffmpeg_found")
        smoke["ffmpeg_path"] = ffmpeg_payload.get("ffmpeg_path")
        devices_payload = requests_get(f"{api_base_url.rstrip('/')}/api/devices/cameras", timeout=5).json()
        smoke["camera_devices"] = devices_payload.get("devices") or []
        config_payload = requests_get(f"{api_base_url.rstrip('/')}/api/config", timeout=5).json()
        preview_start_payload = requests_post(f"{api_base_url.rstrip('/')}/api/preview/start", timeout=10).json()
        time.sleep(2)
        preview_stop_payload = requests_post(f"{api_base_url.rstrip('/')}/api/preview/stop", timeout=10).json()
        capture_start_payload = requests_post(
            f"{api_base_url.rstrip('/')}/api/control/start",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "mode": "direct_frames",
                    "output_dir": str(output_root),
                    "image_prefix": "img",
                    "quality_mode": "copy",
                    "delete_video_after_extract": False,
                    "camera_name": camera_name,
                }
            ),
            timeout=15,
        ).json()
        time.sleep(3)
        capture_stop_payload = requests_post(f"{api_base_url.rstrip('/')}/api/control/stop", timeout=10).json()
        artifacts = collect_finalized_session_artifacts_fn(output_root)
        monitor_payload = collect_terminal_monitor_state_fn(api_base_url)

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
        terminate_packaged_runtime_fn(launch["pid"])


def run_packaged_validation_summary_impl(
    *,
    exe_path: Path,
    api_base_url: str,
    output_root: Path,
    report_path: Path | None,
    camera_name: str,
    packaged_report_paths_fn: Callable[[], dict[str, Path]],
    packaged_report_paths_for_summary_report_fn: Callable[[Path], dict[str, Path]],
    run_packaged_runtime_smoke_validation_fn: Callable[..., dict],
    run_packaged_release_validation_fn: Callable[..., dict],
    write_validation_report_fn: Callable[[Path, dict], None],
    write_validation_markdown_report_fn: Callable[[Path, dict], None],
    write_release_checklist_fn: Callable[[Path, dict], None],
    write_validation_manifest_fn: Callable[[Path, dict], None],
    write_latest_packaged_validation_index_fn: Callable[[Path, dict], None],
    write_packaged_validation_history_fn: Callable[[Path, list[dict]], None],
    derive_release_gate_fn: Callable[[dict], tuple[str, list[str]]],
    release_gate_policy_fn: Callable[[], dict],
) -> dict:
    paths = packaged_report_paths_fn() if report_path is None else packaged_report_paths_for_summary_report_fn(report_path)
    smoke_wrapped = run_packaged_runtime_smoke_validation_fn(
        exe_path=exe_path,
        api_base_url=api_base_url,
        report_path=paths["smoke"],
    )
    release_wrapped = run_packaged_release_validation_fn(
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
    summary_report_path = paths["summary"]
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
    manifest_path = summary_report_path.with_name("packaged_validation_manifest.json")
    checklist_path = summary_report_path.with_name("packaged_release_checklist.md")
    latest_index_path = summary_report_path.parent.parent / "latest_packaged_validation.json"
    history_index_path = summary_report_path.parent.parent / "packaged_validation_history.json"
    smoke_summary = result.get("packaged_runtime_smoke") or {}
    release_artifacts = result.get("packaged_release_validation", {}).get("capture_artifacts") or {}
    latest_payload = {
        "run_id": summary_report_path.parent.name,
        "run_dir": str(summary_report_path.parent),
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
    release_gate, gate_reasons = derive_release_gate_fn(result_payload_for_gate)
    manifest_payload = {
        "run_id": summary_report_path.parent.name,
        "run_dir": str(summary_report_path.parent),
        "overall_ok": result.get("ok"),
        "release_gate": release_gate,
        "release_gate_reasons": gate_reasons,
        "gate_policy": release_gate_policy_fn(),
        "exe_path": str(exe_path),
        "window_title": smoke_summary.get("window_title"),
        "root_ok": smoke_summary.get("root_ok"),
        "root_ready_attempts": smoke_summary.get("root_ready_attempts"),
        "root_ready_seconds": smoke_summary.get("root_ready_seconds"),
        "ffmpeg_path": smoke_summary.get("ffmpeg_path"),
        "camera_devices": smoke_summary.get("camera_devices"),
        "frame_count": release_artifacts.get("frame_count"),
        "total_frame_size_bytes": release_artifacts.get("total_frame_size_bytes"),
        "summary_report": str(summary_report_path),
        "summary_markdown": str(summary_report_path.with_suffix(".md")),
        "smoke_report": str(paths["smoke"]),
        "release_report": str(paths["release"]),
        "release_checklist": str(checklist_path),
        "capture_session_dir": release_artifacts.get("session_dir"),
        "frames_csv_path": release_artifacts.get("frames_csv_path"),
        "summary_path": release_artifacts.get("summary_path"),
        "metadata_path": release_artifacts.get("metadata_path"),
    }
    latest_payload.update(
        {
            "release_gate": manifest_payload["release_gate"],
            "release_gate_reasons": manifest_payload["release_gate_reasons"],
            "summary_report": manifest_payload["summary_report"],
            "summary_markdown": manifest_payload["summary_markdown"],
            "manifest_path": str(manifest_path),
            "checklist_path": str(checklist_path),
        }
    )
    if "delta" in latest_payload:
        wrapped["latest_run_delta"] = delta
        manifest_payload["latest_run_delta"] = delta
    if "comparison_baseline" in latest_payload:
        wrapped["comparison_baseline"] = latest_payload["comparison_baseline"]
        manifest_payload["comparison_baseline"] = latest_payload["comparison_baseline"]
    wrapped["report_path"] = str(summary_report_path)
    wrapped["markdown_report_path"] = str(summary_report_path.with_suffix(".md"))
    wrapped["manifest_path"] = str(manifest_path)
    wrapped["checklist_path"] = str(checklist_path)
    wrapped["latest_index_path"] = str(latest_index_path)
    wrapped["history_index_path"] = str(history_index_path)
    wrapped["release_gate"] = release_gate
    wrapped["release_gate_reasons"] = gate_reasons
    wrapped["gate_policy"] = release_gate_policy_fn()
    write_validation_report_fn(summary_report_path, wrapped)
    write_validation_markdown_report_fn(summary_report_path.with_suffix(".md"), wrapped)
    write_release_checklist_fn(checklist_path, wrapped)
    manifest_payload["report_sizes"] = {
        "summary_report_bytes": summary_report_path.stat().st_size if summary_report_path.exists() else None,
        "summary_markdown_bytes": summary_report_path.with_suffix(".md").stat().st_size if summary_report_path.with_suffix(".md").exists() else None,
        "smoke_report_bytes": paths["smoke"].stat().st_size if paths["smoke"].exists() else None,
        "release_report_bytes": paths["release"].stat().st_size if paths["release"].exists() else None,
        "release_checklist_bytes": checklist_path.stat().st_size if checklist_path.exists() else None,
    }
    write_validation_manifest_fn(manifest_path, manifest_payload)
    write_latest_packaged_validation_index_fn(latest_index_path, latest_payload)
    write_packaged_validation_history_fn(history_index_path, history_entries[:10])
    return wrapped


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
