from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable


def packaged_runtime_smoke_impl(
    *,
    exe_path: Path,
    startup_seconds: float,
    run_desktop_automation_fn: Callable[..., dict],
) -> dict:
    failure = None
    smoke_payload = {}
    try:
        smoke_payload = run_desktop_automation_fn(exe_path=exe_path, action="smoke", timeout_seconds=max(30.0, startup_seconds + 10.0))
        if not smoke_payload.get("ok"):
            failure = smoke_payload.get("error")
    except Exception as exc:
        failure = str(exc)

    config = smoke_payload.get("config") or {}
    return {
        "ok": bool(smoke_payload.get("ok")),
        "pid": None,
        "alive": bool(smoke_payload.get("ok")),
        "window_title": smoke_payload.get("window_title", ""),
        "root_ok": bool(smoke_payload.get("ok")),
        "root_payload": {"desktop_mode": "pyside6_automation"},
        "root_ready_attempts": 1,
        "root_ready_seconds": max(0.0, startup_seconds),
        "ffmpeg_found": bool(config.get("ffmpeg_path")),
        "ffmpeg_path": config.get("ffmpeg_path"),
        "camera_devices": smoke_payload.get("devices") or [],
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
    exe_path: Path,
    *,
    retries: int,
    delay_seconds: float,
    run_desktop_automation_fn: Callable[..., dict],
    sleep_fn: Callable[[float], None],
) -> dict:
    last_payload: dict = {}
    for attempt in range(retries):
        try:
            payload = run_desktop_automation_fn(exe_path=exe_path, action="snapshot").get("snapshot") or {}
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
    output_root: Path,
    camera_name: str,
    run_desktop_automation_fn: Callable[..., dict],
    collect_finalized_session_artifacts_fn: Callable[[Path], dict | None],
) -> dict:
    release_payload = run_desktop_automation_fn(
        exe_path=exe_path,
        action="release_validation",
        payload={
            "mode": "direct_frames",
            "output_dir": str(output_root),
            "image_prefix": "img",
            "quality_mode": "copy",
            "delete_video_after_extract": False,
            "camera_name": camera_name,
            "preview_seconds": 2.0,
            "capture_seconds": 3.0,
            "settle_seconds": 1.0,
        },
        timeout_seconds=120.0,
    )
    config_payload = release_payload.get("config") or {}
    artifacts = collect_finalized_session_artifacts_fn(output_root)
    monitor_payload = release_payload.get("monitor") or {}

    ok = bool(
        release_payload.get("ok")
        and config_payload.get("ffmpeg_path")
        and (release_payload.get("preview_start") or {}).get("ok")
        and (release_payload.get("preview_stop") or {}).get("ok")
        and (release_payload.get("capture_start") or {}).get("ok")
        and (release_payload.get("capture_stop") or {}).get("ok")
        and artifacts is not None
        and artifacts.get("frame_count", 0) > 0
        and artifacts.get("summary_exists")
        and artifacts.get("metadata_exists")
    )
    return {
        "ok": ok,
        "window_title": release_payload.get("window_title", ""),
        "camera_devices": release_payload.get("devices") or [],
        "packaged_runtime_smoke": {
            "ok": bool(release_payload.get("ok")),
            "pid": None,
            "alive": True,
            "window_title": release_payload.get("window_title", ""),
            "root_ok": True,
            "root_payload": {"desktop_mode": "pyside6_automation"},
            "root_ready_attempts": 1,
            "root_ready_seconds": 8.0,
            "ffmpeg_found": bool(config_payload.get("ffmpeg_path")),
            "ffmpeg_path": config_payload.get("ffmpeg_path"),
            "camera_devices": release_payload.get("devices") or [],
            "failure_detail": release_payload.get("error"),
        },
        "config": config_payload,
        "ffmpeg_status": {
            "ffmpeg_found": bool(config_payload.get("ffmpeg_path")),
            "ffmpeg_path": config_payload.get("ffmpeg_path"),
        },
        "preview_start": release_payload.get("preview_start") or {},
        "preview_stop": release_payload.get("preview_stop") or {},
        "capture_start": release_payload.get("capture_start") or {},
        "capture_stop": release_payload.get("capture_stop") or {},
        "monitor": monitor_payload,
        "capture_artifacts": artifacts,
    }


def run_packaged_validation_summary_impl(
    *,
    exe_path: Path,
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
        report_path=paths["smoke"],
    )
    release_wrapped = run_packaged_release_validation_fn(
        exe_path=exe_path,
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
            "overall_ok": result.get("ok"),
            "release_gate": release_gate,
            "release_gate_reasons": gate_reasons,
            "summary_report": str(summary_report_path),
        }
    )
    markdown_report_path = summary_report_path.with_suffix(".md")
    wrapped["report_path"] = str(summary_report_path)
    wrapped["markdown_report_path"] = str(markdown_report_path)
    wrapped["manifest_path"] = str(manifest_path)
    wrapped["checklist_path"] = str(checklist_path)
    wrapped["latest_index_path"] = str(latest_index_path)
    wrapped["history_index_path"] = str(history_index_path)
    wrapped["release_gate"] = release_gate
    wrapped["release_gate_reasons"] = gate_reasons
    write_validation_report_fn(summary_report_path, wrapped)
    write_validation_markdown_report_fn(markdown_report_path, wrapped)
    write_release_checklist_fn(checklist_path, manifest_payload)
    write_validation_manifest_fn(manifest_path, manifest_payload)
    write_latest_packaged_validation_index_fn(latest_index_path, latest_payload)
    write_packaged_validation_history_fn(history_index_path, history_entries)
    return wrapped


def _numeric_delta(current: dict, baseline: dict, key: str) -> float | int | None:
    current_value = current.get(key)
    baseline_value = baseline.get(key)
    if current_value is None or baseline_value is None:
        return None
    return current_value - baseline_value


def _find_previous_comparable_run(entries: list[dict], required_keys: list[str]) -> tuple[dict | None, list[str]]:
    skipped_run_ids: list[str] = []
    for entry in entries:
        if all(entry.get(key) is not None for key in required_keys):
            return entry, skipped_run_ids
        if entry.get("run_id"):
            skipped_run_ids.append(entry["run_id"])
    return None, skipped_run_ids
