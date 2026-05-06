from __future__ import annotations

import subprocess
import threading

from usb_cam_ffmpeg import preview_cmd

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def build_preview_cmd(ffmpeg: str, camera_name: str, width: int, height: int, fps: int, preview_fps: int, preview_width: int) -> list[str]:
    return preview_cmd(ffmpeg, camera_name, width, height, fps, preview_fps, preview_width)


def find_png_end(buf: bytearray) -> int | None:
    if len(buf) < 8:
        return None
    pos = 8
    while True:
        if len(buf) < pos + 8:
            return None
        length = int.from_bytes(buf[pos:pos+4], "big")
        typ = bytes(buf[pos+4:pos+8])
        pos += 8 + length + 4
        if len(buf) < pos:
            return None
        if typ == b"IEND":
            return pos


def read_preview_frames(stdout, emit):
    buf = bytearray()
    while True:
        chunk = stdout.read(8192)
        if not chunk:
            break
        buf.extend(chunk)
        while True:
            start = buf.find(PNG_SIG)
            if start < 0:
                if len(buf) > len(PNG_SIG):
                    del buf[:-len(PNG_SIG)]
                break
            if start > 0:
                del buf[:start]
            end = find_png_end(buf)
            if end is None:
                break
            emit(bytes(buf[:end]))
            del buf[:end]


def start_preview_process(ffmpeg: str, cmd: list[str]) -> subprocess.Popen:
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def stop_preview_process(p: subprocess.Popen, wait: bool = False):
    try:
        if p.stdin:
            p.stdin.write(b"q\n")
            p.stdin.flush()
    except Exception:
        try:
            p.terminate()
        except Exception:
            pass
    if wait:
        try:
            p.wait(timeout=3)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
