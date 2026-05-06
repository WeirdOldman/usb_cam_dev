from __future__ import annotations

import os
import shutil
import sys


def app_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def candidate_base_dirs() -> list[str]:
    dirs = []
    for d in [
        app_base_dir(),
        os.getcwd(),
        os.path.dirname(os.path.abspath(__file__)),
        os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv else "",
    ]:
        if d and d not in dirs:
            dirs.append(d)
    return dirs


def find_ffmpeg(user_value: str = "auto") -> str | None:
    candidates = []
    if user_value and user_value.lower() not in ("auto", "ffmpeg"):
        candidates.append(user_value)
    for base_dir in candidate_base_dirs():
        candidates += [
            os.path.join(base_dir, "tools", "ffmpeg.exe"),
            os.path.join(base_dir, "ffmpeg.exe"),
        ]
    for c in candidates:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    found = shutil.which("ffmpeg")
    return found if found else None


def safe_image_prefix(text: str) -> str:
    prefix = (text or "img").strip() or "img"
    bad = '<>:"/\\|?*'
    for ch in bad:
        prefix = prefix.replace(ch, '_')
    return prefix


def sanitize_windows_filename(name: str, default: str = "usb_cam") -> str:
    cleaned = (name or default).strip() or default
    for ch in '<>:"/\\|?*':
        cleaned = cleaned.replace(ch, '_')
    cleaned = cleaned.rstrip('. ')
    return cleaned or default
