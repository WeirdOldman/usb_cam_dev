from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

import requests
import uvicorn
from fastapi import FastAPI


def select_output_directory(*, webview_window: Any, current_dir: str | None, fallback_dir: str) -> str | None:
    if webview_window is None:
        raise RuntimeError("PyWebView window is not initialized")

    import webview

    initial_dir = current_dir or fallback_dir
    selected = webview_window.create_file_dialog(webview.FOLDER_DIALOG, directory=initial_dir)
    if not selected:
        return None
    if isinstance(selected, (list, tuple)):
        return str(selected[0]) if selected else None
    return str(selected)


def require_window(window: Any) -> Any:
    if window is None:
        raise RuntimeError("PyWebView window is not initialized")
    return window


def open_path_in_system(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
        return
    raise RuntimeError("open_system_path currently only supports Windows")


def query_camera_devices(ffmpeg_path: str | None, *, popen_kwargs: Callable[[], dict[str, Any]]) -> list[str]:
    if not ffmpeg_path:
        return []

    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-list_devices",
        "true",
        "-f",
        "dshow",
        "-i",
        "dummy",
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        **popen_kwargs(),
    )
    text = f"{proc.stdout}\n{proc.stderr}"
    devices: list[str] = []
    for line in text.splitlines():
        if '"' not in line:
            continue
        quoted = line.split('"')
        if len(quoted) < 2:
            continue
        name = quoted[1].strip()
        if name and name not in devices and "Alternative name" not in line:
            devices.append(name)
    return devices


def append_runtime_log(path: Path, message: str) -> None:
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(path, "a", encoding="utf-8", errors="replace") as fp:
        fp.write(f"[{timestamp}] {message}\n")


def resolve_frontend_target(frontend_dir: Path, dev_url: str) -> str:
    candidates = [
        frontend_dir / "index.html",
        frontend_dir.parent / "_internal" / frontend_dir.name / "index.html",
    ]
    for index_file in candidates:
        if index_file.exists():
            return index_file.resolve().as_uri()
    return dev_url


def run_api_server(app: FastAPI, *, host: str, port: int) -> None:
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    server.run()


def wait_for_frontend_ready(url: str, *, timeout_seconds: float = 30.0) -> None:
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            response = requests.get(url, timeout=1.0)
            if response.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Frontend dev server not reachable: {url}")


def resolve_webview_debug_mode(raw_value: str | None) -> bool:
    raw = (raw_value or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}
