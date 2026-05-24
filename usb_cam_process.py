from __future__ import annotations

import os
import re
import subprocess
from typing import Callable


def windows_popen_kwargs() -> dict:
    if os.name != "nt":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


def parse_ffmpeg_progress_line(line: str, fps: int) -> int | None:
    m = re.search(r"frame=\s*(\d+)", line)
    if not m:
        m = re.search(r"frame=?(\d+)", line)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    m = re.search(r"out_time_ms=?(\d+)", line)
    if m:
        try:
            us = int(m.group(1))
            return int((us / 1000000.0) * fps + 0.5)
        except ValueError:
            return None
    return None


def run_ffmpeg_process(
    cmd: list[str],
    fps: int,
    log_write: Callable[[str], None] | None = None,
    frame_callback: Callable[[int], None] | None = None,
    started_callback: Callable[[subprocess.Popen], None] | None = None,
) -> tuple[subprocess.Popen, int]:
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        **windows_popen_kwargs(),
    )
    if started_callback:
        started_callback(proc)
    assert proc.stdout is not None
    last_frame = 0
    for line in proc.stdout:
        if log_write:
            log_write(line)
        parsed = parse_ffmpeg_progress_line(line, fps)
        if parsed is not None:
            last_frame = max(last_frame, parsed)
            if frame_callback:
                frame_callback(last_frame)
    code = proc.wait()
    return proc, code


def request_stop_process(proc: subprocess.Popen):
    try:
        if proc.stdin:
            proc.stdin.write("q\n")
            proc.stdin.flush()
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass
