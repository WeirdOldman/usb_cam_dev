from __future__ import annotations

import base64
from tkinter import messagebox

from usb_cam_preview import build_preview_cmd


def prepare_preview_start(camera_name: str, ffmpeg: str, *, width: int, height: int, fps: int, preview_fps: int, preview_width: int):
    return build_preview_cmd(
        ffmpeg=ffmpeg,
        width=width,
        height=height,
        fps=fps,
        camera_name=camera_name,
        preview_fps=preview_fps,
        preview_width=preview_width,
    )


def launch_preview_threads(thread_factory, preview_reader, preview_stderr_reader):
    preview_worker = thread_factory(target=preview_reader, daemon=True)
    preview_worker.start()
    preview_err_worker = thread_factory(target=preview_stderr_reader, daemon=True)
    preview_err_worker.start()
    return preview_worker, preview_err_worker


def mark_preview_running(status_var, start_btn, stop_btn):
    status_var.set("预览运行中")
    start_btn.configure(state="disabled")
    stop_btn.configure(state="normal")


def handle_preview_start_error(exc: Exception):
    messagebox.showerror("预览启动失败", str(exc))


def handle_preview_process_stop(status_var, start_btn, stop_btn):
    start_btn.configure(state="normal")
    stop_btn.configure(state="disabled")
    status_var.set("预览已停止")


def should_apply_preview_stopped_ui(preview_proc) -> bool:
    return preview_proc is None or preview_proc.poll() is not None


def apply_preview_frame(preview_label, img):
    preview_label.configure(image=img, text="")
    return img


def build_preview_frame_image(action_data, *, photo_image_factory):
    b64 = base64.b64encode(action_data).decode("ascii")
    return photo_image_factory(data=b64, format="png")


def preview_frame_error_text(exc: Exception):
    return f"预览帧错误: {exc}"


def apply_preview_status_text(preview_status_var, text: str):
    preview_status_var.set(text)


def apply_preview_stopped_ui(preview_status_var, preview_start_btn, preview_stop_btn):
    preview_start_btn.configure(state="normal")
    preview_stop_btn.configure(state="disabled")
    if preview_status_var.get() == "预览运行中":
        preview_status_var.set("预览已停止")
