from __future__ import annotations

import json
import time
from pathlib import Path


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
        lines.extend(
            [
                "",
                "## Run Delta",
                f"- Root ready seconds vs previous run: `{delta.get('root_ready_seconds')}`",
                f"- Frame count vs previous run: `{delta.get('frame_count')}`",
            ]
        )
    comparison = payload.get("comparison_baseline") or {}
    if comparison:
        lines.extend(
            [
                "",
                "## Comparison Baseline",
                f"- Selected run: `{comparison.get('selected_run_id')}`",
                f"- Skipped runs: `{comparison.get('skipped_run_ids')}`",
            ]
        )
    if not payload.get("packaged_validation_summary", {}).get("ok", False):
        lines.extend(["", "## Failure Summary"])
        if smoke.get("failure_detail"):
            lines.append(f"- Smoke failure detail: `{smoke.get('failure_detail')}`")
        if release.get("failure_detail"):
            lines.append(f"- Release failure detail: `{release.get('failure_detail')}`")
        lines.extend(["", "## Suggested Actions"])
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
        lines.extend(
            [
                "## Run Delta",
                "",
                f"- Delta root ready seconds vs previous run: `{delta.get('root_ready_seconds')}`",
                f"- Delta frame count vs previous run: `{delta.get('frame_count')}`",
                "",
            ]
        )
    comparison = payload.get("comparison_baseline") or {}
    if comparison:
        lines.extend(
            [
                "## Comparison Baseline",
                "",
                f"- Comparison baseline run: `{comparison.get('selected_run_id')}`",
                f"- Skipped runs before baseline: `{comparison.get('skipped_run_ids')}`",
                "",
            ]
        )
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
