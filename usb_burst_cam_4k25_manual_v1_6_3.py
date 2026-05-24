from __future__ import annotations

import csv
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from usb_cam_paths import app_base_dir, find_ffmpeg, safe_image_prefix, sanitize_windows_filename
from usb_cam_session_writer import make_session
from usb_cam_preview import read_preview_frames, start_preview_process, stop_preview_process
from usb_cam_capture import build_direct_cmd as capture_build_direct_cmd, build_record_cmd as capture_build_record_cmd, build_extract_cmd as capture_build_extract_cmd
from usb_cam_process import request_stop_process
from usb_cam_ui_state import update_capture_metrics, process_ui_message
from usb_cam_finalize import finalize_capture_done_state
from usb_cam_session_finalize import finalize_session
from usb_cam_capture_state import CaptureState
from usb_cam_capture_context import CaptureContext
from usb_cam_stats import disk_free_status
import usb_cam_capture_helpers as capture_helpers
import usb_cam_preview_helpers as preview_helpers
import usb_cam_queue_helpers as queue_helpers

APP_NAME = "usb_burst_cam_4k25_manual_v1_6_3"
APP_TITLE = "USB 摄像头 4K25 手动连拍"
WIDTH = 3840
HEIGHT = 2160
FPS = 25
DEFAULT_CAMERA_NAME = "imx678' UVC "
MAX_LOG_BYTES = 10 * 1024 * 1024
PREVIEW_WIDTH = 640
PREVIEW_FPS = 5


def setup_console_encoding():
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class LimitedLogWriter:
    def __init__(self, path: Path, max_bytes: int = MAX_LOG_BYTES):
        self.path = path
        self.max_bytes = max_bytes
        self.written = 0
        self.truncated = False
        self.fp = open(path, "ab")

    def write(self, text: str):
        if self.truncated:
            return
        data = text.encode("utf-8", errors="replace")
        if self.written + len(data) > self.max_bytes:
            remain = max(0, self.max_bytes - self.written)
            if remain > 0:
                self.fp.write(data[:remain])
                self.written += remain
            marker = "\n\n[LOG TRUNCATED: run_log.txt reached 10MB limit]\n"
            marker_b = marker.encode("utf-8")
            if self.written + len(marker_b) <= self.max_bytes + len(marker_b):
                self.fp.write(marker_b)
            self.truncated = True
        else:
            self.fp.write(data)
            self.written += len(data)
        self.fp.flush()

    def close(self):
        self.fp.close()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        setup_console_encoding()
        self.title(f"{APP_TITLE} - v1.6.4")
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        ww = min(960, max(760, sw - 80))
        wh = min(560, max(480, sh - 120))
        self.geometry(f"{ww}x{wh}")
        self.minsize(720, 460)
        self.resizable(True, True)
        self.base_dir = app_base_dir()
        self.proc: subprocess.Popen | None = None
        self.preview_proc: subprocess.Popen | None = None
        self.worker: threading.Thread | None = None
        self.preview_worker: threading.Thread | None = None
        self.preview_err_worker: threading.Thread | None = None
        self.ui_queue: queue.Queue = queue.Queue()
        self.capture_context = CaptureContext()
        self.preview_image = None
        self.capture_state = CaptureState()
        self.create_vars()
        self.setup_style()
        self.build_ui()
        self.after(100, self.process_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_vars(self):
        self.camera_name_var = tk.StringVar(value=DEFAULT_CAMERA_NAME)
        self.output_dir_var = tk.StringVar(value=os.path.join(self.base_dir, "capture_output"))
        self.image_prefix_var = tk.StringVar(value="img")
        self.mode_var = tk.StringVar(value="direct_frames")
        self.quality_var = tk.StringVar(value="copy")
        self.delete_video_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="就绪：可先启动预览调整镜头，再开始采集。")
        self.elapsed_var = tk.StringVar(value="00:00:00")
        self.frame_count_var = tk.StringVar(value="0")
        self.used_size_var = tk.StringVar(value="0 MB")
        self.estimate_var = tk.StringVar(value="约 0 MB/分钟")
        self.capture_fps_var = tk.StringVar(value="-- fps")
        self.preview_status_var = tk.StringVar(value="预览未启动")
        self.ffmpeg_path_var = tk.StringVar(value=find_ffmpeg() or "")

    def setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        bg = "#f4f7fb"
        card = "#ffffff"
        self.configure(bg=bg)
        style.configure("TFrame", background=bg)
        style.configure("Card.TFrame", background=card)
        style.configure("TLabel", background=bg, foreground="#172033", font=("Microsoft YaHei UI", 10))
        style.configure("Card.TLabel", background=card, foreground="#172033", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", background=bg, foreground="#0f172a", font=("Microsoft YaHei UI", 20, "bold"))
        style.configure("Sub.TLabel", background=bg, foreground="#64748b", font=("Microsoft YaHei UI", 10))
        style.configure("Section.TLabel", background=card, foreground="#0f172a", font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(12, 7))
        style.configure("Primary.TButton", font=("Microsoft YaHei UI", 11, "bold"), foreground="white", background="#2563eb", padding=(18, 10))
        style.map("Primary.TButton", background=[("active", "#1d4ed8"), ("disabled", "#93c5fd")])
        style.configure("Danger.TButton", font=("Microsoft YaHei UI", 11, "bold"), foreground="white", background="#dc2626", padding=(18, 10))
        style.map("Danger.TButton", background=[("active", "#b91c1c"), ("disabled", "#fca5a5")])
        style.configure("Big.TLabel", background=card, foreground="#0f172a", font=("Microsoft YaHei UI", 17, "bold"))

    def build_ui(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 6))
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").pack(side="left")

        # 固定顶部工具栏：关键按钮永远在可见区域，不再放到底部。
        toolbar = ttk.Frame(root, style="Card.TFrame", padding=(8, 6))
        toolbar.pack(fill="x", pady=(0, 8))
        self.preview_start_btn = ttk.Button(toolbar, text="启动预览", command=self.start_preview)
        self.preview_start_btn.pack(side="left", padx=(0, 6))
        self.preview_stop_btn = ttk.Button(toolbar, text="停止预览", command=self.stop_preview, state="disabled")
        self.preview_stop_btn.pack(side="left", padx=(0, 14))
        self.start_btn = ttk.Button(toolbar, text="开始采集", style="Primary.TButton", command=self.start_capture)
        self.start_btn.pack(side="left", padx=(0, 6))
        self.stop_btn = ttk.Button(toolbar, text="停止采集", style="Danger.TButton", command=self.stop_capture, state="disabled")
        self.stop_btn.pack(side="left", padx=(0, 14))
        ttk.Button(toolbar, text="输出目录", command=lambda: self.open_path(self.output_dir_var.get())).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="检测FFmpeg", command=self.check_ffmpeg).pack(side="left")
        ttk.Label(toolbar, textvariable=self.preview_status_var, style="Card.TLabel", foreground="#64748b").pack(side="right")

        main = ttk.PanedWindow(root, orient="horizontal")
        main.pack(fill="both", expand=True)
        left = ttk.Frame(main, style="Card.TFrame")
        right = ttk.Frame(main, style="Card.TFrame", padding=10)
        main.add(left, weight=2)
        main.add(right, weight=3)
        self.build_scrollable_left(left)
        self.build_preview(right)

        bottom = ttk.Frame(root)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Label(bottom, textvariable=self.status_var, style="Sub.TLabel").pack(side="left")
        self.progress = ttk.Progressbar(bottom, mode="indeterminate")
        self.progress.pack(side="right", fill="x", expand=True, padx=(16, 0))

    def build_scrollable_left(self, parent):
        canvas = tk.Canvas(parent, background="#ffffff", highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas, style="Card.TFrame", padding=12)
        win = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        def on_content_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event):
            canvas.itemconfigure(win, width=event.width)

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        content.bind("<Configure>", on_content_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        self.build_left(content)

    def row(self, parent, label, widget, r, hint=""):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=8, padx=(0, 12))
        widget.grid(row=r, column=1, sticky="ew", pady=8)
        if hint:
            ttk.Label(parent, text=hint, style="Card.TLabel", foreground="#64748b", wraplength=360).grid(row=r+1, column=1, sticky="w", pady=(0, 4))
            return r + 2
        return r + 1

    def build_left(self, parent):
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="采集设置", style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        r = 1
        out = ttk.Frame(parent, style="Card.TFrame")
        out.columnconfigure(0, weight=1)
        ttk.Entry(out, textvariable=self.output_dir_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(out, text="选择", command=self.choose_output_dir).grid(row=0, column=1, padx=(8, 0))
        r = self.row(parent, "输出目录", out, r)
        r = self.row(parent, "图片前缀", ttk.Entry(parent, textvariable=self.image_prefix_var), r)

        mode_box = ttk.Frame(parent, style="Card.TFrame")
        ttk.Radiobutton(mode_box, text="直接保存图片序列（默认）", variable=self.mode_var, value="direct_frames", command=self.on_mode_change).pack(anchor="w", pady=2)
        ttk.Radiobutton(mode_box, text="先录视频，再自动拆帧", variable=self.mode_var, value="video_then_frames", command=self.on_mode_change).pack(anchor="w", pady=2)
        r = self.row(parent, "工作模式", mode_box, r)

        quality_box = ttk.Frame(parent, style="Card.TFrame")
        ttk.Radiobutton(quality_box, text="原始 MJPEG 复制（推荐）", variable=self.quality_var, value="copy").pack(anchor="w", pady=2)
        ttk.Radiobutton(quality_box, text="高质量重新编码 q=2（备用）", variable=self.quality_var, value="q2").pack(anchor="w", pady=2)
        r = self.row(parent, "画质模式", quality_box, r)

        del_box = ttk.Checkbutton(parent, text="视频拆帧成功后自动删除中间 AVI 视频", variable=self.delete_video_var)
        r = self.row(parent, "空间选项", del_box, r)

        stats = ttk.Frame(parent, style="Card.TFrame")
        stats.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        for i in range(2):
            stats.columnconfigure(i, weight=1)
        self.stat_pair(stats, "运行时间", self.elapsed_var, 0, 0)
        self.stat_pair(stats, "已生成图片", self.frame_count_var, 0, 1)
        self.stat_pair(stats, "实时/估算 FPS", self.capture_fps_var, 2, 0)
        self.stat_pair(stats, "已占用空间", self.used_size_var, 2, 1)
        self.stat_pair(stats, "估算图片空间", self.estimate_var, 4, 0, colspan=2)


    def stat_pair(self, parent, label, var, row, col, colspan=1):
        box = ttk.Frame(parent, style="Card.TFrame")
        box.grid(row=row, column=col, columnspan=colspan, sticky="ew", padx=(0, 20), pady=8)
        ttk.Label(box, text=label, style="Card.TLabel", foreground="#64748b").pack(anchor="w")
        ttk.Label(box, textvariable=var, style="Big.TLabel").pack(anchor="w")

    def build_preview(self, parent):
        ttk.Label(parent, text="实时画面预览", style="Section.TLabel").pack(anchor="w")
        self.preview_label = tk.Label(parent, text="预览未启动", bg="#050816", fg="#94a3b8", font=("Microsoft YaHei UI", 15), width=50, height=18)
        self.preview_label.pack(fill="both", expand=True)

    def on_mode_change(self):
        if self.mode_var.get() == "direct_frames":
            pass
        else:
            pass

    def choose_output_dir(self):
        path = filedialog.askdirectory(initialdir=self.output_dir_var.get() or self.base_dir)
        if path:
            self.output_dir_var.set(path)

    def check_ffmpeg(self):
        ffmpeg = find_ffmpeg()
        if ffmpeg:
            self.ffmpeg_path_var.set(ffmpeg)
            messagebox.showinfo("FFmpeg 可用", ffmpeg)
        else:
            messagebox.showerror("缺少 FFmpeg", "没有找到 FFmpeg。请先运行 download_ffmpeg_portable_v1_6_3.bat，或把 tools 文件夹复制到当前目录。")

    def set_capture_running(self, running: bool):
        self.capture_state.capture_running = running
        self.start_btn.configure(state="disabled" if running else "normal")
        self.stop_btn.configure(state="normal" if running else "disabled")
        if running:
            self.progress.start(12)
        else:
            self.progress.stop()

    def prepare_preview_start(self, ffmpeg: str):
        return preview_helpers.prepare_preview_start(
            self.camera_name_var.get(),
            ffmpeg,
            width=WIDTH,
            height=HEIGHT,
            fps=FPS,
            preview_fps=PREVIEW_FPS,
            preview_width=PREVIEW_WIDTH,
        )

    def launch_preview_threads(self):
        self.preview_worker, self.preview_err_worker = preview_helpers.launch_preview_threads(
            threading.Thread,
            self.preview_reader,
            self.preview_stderr_reader,
        )

    def mark_preview_running(self):
        preview_helpers.mark_preview_running(
            self.preview_status_var,
            self.preview_start_btn,
            self.preview_stop_btn,
        )

    def handle_preview_start_error(self, exc: Exception):
        self.preview_proc = None
        preview_helpers.handle_preview_start_error(exc)

    def start_preview(self):
        if self.preview_proc is not None:
            return
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            messagebox.showerror("缺少 FFmpeg", "没有找到 FFmpeg。请先运行 download_ffmpeg_portable_v1_6_3.bat。")
            return
        cmd = self.prepare_preview_start(ffmpeg)
        try:
            self.preview_proc = start_preview_process(ffmpeg, cmd)
        except Exception as e:
            self.handle_preview_start_error(e)
            return
        self.mark_preview_running()
        self.launch_preview_threads()

    def preview_stderr_reader(self):
        p = self.preview_proc
        if p is None or p.stderr is None:
            return
        try:
            for raw in p.stderr:
                if not raw:
                    break
                try:
                    text = raw.decode("utf-8", errors="replace").strip()
                except Exception:
                    text = str(raw)
                if text:
                    self.ui_queue.put(("preview_status", text, None))
        except Exception:
            pass

    def preview_reader(self):
        p = self.preview_proc
        if p is None or p.stdout is None:
            return
        try:
            read_preview_frames(
                p.stdout,
                lambda frame: self.ui_queue.put(("preview_frame", frame, None)),
            )
        finally:
            self.ui_queue.put(("preview_stopped", None, None))

    def handle_preview_process_stop(self):
        self.preview_proc = None
        preview_helpers.handle_preview_process_stop(
            self.preview_status_var,
            self.preview_start_btn,
            self.preview_stop_btn,
        )

    def stop_preview(self, wait: bool = False):
        p = self.preview_proc
        if p is None:
            return
        stop_preview_process(p, wait=wait)
        self.handle_preview_process_stop()

    def reset_capture_display(self):
        capture_helpers.reset_capture_display(
            self.frame_count_var,
            self.elapsed_var,
            self.used_size_var,
            self.estimate_var,
            self.capture_fps_var,
        )

    def prepare_capture_session(self, ffmpeg: str, mode_prefix: str):
        return capture_helpers.prepare_capture_session(
            output_dir=self.output_dir_var.get(),
            mode_prefix=mode_prefix,
            image_prefix=safe_image_prefix(self.image_prefix_var.get()),
            delete_video_after_extract=bool(self.delete_video_var.get()),
            app_name=APP_NAME,
            created_at=datetime.now().isoformat(timespec="seconds"),
            camera_name=self.camera_name_var.get(),
            mode=self.mode_var.get(),
            quality=self.quality_var.get(),
            ffmpeg=ffmpeg,
            make_session=make_session,
            limited_log_writer_cls=LimitedLogWriter,
            capture_context=self.capture_context,
            max_log_bytes=MAX_LOG_BYTES,
        )

    def begin_capture_run(self, log_path: Path):
        self.start_time = time.time()
        self.worker = capture_helpers.begin_capture_run(
            now=self.start_time,
            capture_state=self.capture_state,
            reset_capture_display_fn=self.reset_capture_display,
            set_capture_running=self.set_capture_running,
            status_var=self.status_var,
            log_path=log_path,
            thread_factory=threading.Thread,
            worker_capture=self.worker_capture,
            after_update_timer=lambda: self.after(500, self.update_timer),
        )

    def start_capture(self):
        if self.proc is not None:
            messagebox.showwarning("正在运行", "当前已有采集任务。")
            return
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            messagebox.showerror("缺少 FFmpeg", "没有找到 FFmpeg。请先运行 download_ffmpeg_portable_v1_6_3.bat。")
            return
        if self.preview_proc is not None:
            self.stop_preview(wait=True)
        mode_prefix = "direct_frames_mjpeg_4k" if self.mode_var.get() == "direct_frames" else "video_then_frames_mjpeg_4k"
        log_path = self.prepare_capture_session(ffmpeg, mode_prefix)
        if self.capture_context.current_session is not None:
            disk_status = disk_free_status(self.capture_context.current_session)
            if disk_status.get('disk_low_space') and disk_status.get('disk_free_warning_text'):
                self.status_var.set(disk_status['disk_free_warning_text'])
                if self.capture_context.log_writer:
                    self.capture_context.log_writer.write(f"\n[warning] {disk_status['disk_free_warning_text']}\n")
        self.begin_capture_run(log_path)

    def build_direct_cmd(self, ffmpeg: str):
        assert self.capture_context.current_frames_dir is not None
        prefix = safe_image_prefix(self.image_prefix_var.get())
        return capture_build_direct_cmd(
            ffmpeg=ffmpeg,
            output_dir=self.capture_context.current_frames_dir,
            image_prefix=prefix,
            width=WIDTH,
            height=HEIGHT,
            fps=FPS,
            camera_name=self.camera_name_var.get(),
            quality_mode=self.quality_var.get(),
        )

    def build_record_cmd(self, ffmpeg: str, video_path: Path):
        return capture_build_record_cmd(
            ffmpeg=ffmpeg,
            video_path=video_path,
            width=WIDTH,
            height=HEIGHT,
            fps=FPS,
            camera_name=self.camera_name_var.get(),
        )

    def build_extract_cmd(self, ffmpeg: str, video_path: Path, fallback_q2: bool = False):
        assert self.capture_context.current_frames_dir is not None
        prefix = safe_image_prefix(self.image_prefix_var.get())
        return capture_build_extract_cmd(
            ffmpeg=ffmpeg,
            video_path=video_path,
            output_dir=self.capture_context.current_frames_dir,
            image_prefix=prefix,
            fallback_q2=fallback_q2,
        )

    def execute_capture_pipeline(self, ffmpeg: str):
        capture_helpers.execute_capture_pipeline(
            mode=self.mode_var.get(),
            ffmpeg=ffmpeg,
            current_video_dir=self.capture_context.current_video_dir,
            current_frames_dir=self.capture_context.current_frames_dir,
            delete_video_after_extract=bool(self.delete_video_var.get()),
            current_meta=self.capture_context.current_meta,
            run_process=self.run_process,
            build_direct_cmd=self.build_direct_cmd,
            build_record_cmd=self.build_record_cmd,
            build_extract_cmd=self.build_extract_cmd,
        )

    def handle_capture_exception(self, exc: Exception):
        capture_helpers.handle_capture_exception(self.capture_context.log_writer, self.status_var, exc)

    def close_capture_resources(self):
        capture_helpers.close_capture_resources(
            self.capture_context.log_writer,
            self.capture_context.clear_log_writer,
            self.ui_queue,
        )
        self.proc = None

    def worker_capture(self):
        ffmpeg = self.capture_context.current_meta["ffmpeg"]
        try:
            self.execute_capture_pipeline(ffmpeg)
            self.finish_session()
        except Exception as e:
            self.handle_capture_exception(e)
        finally:
            self.close_capture_resources()

    def log_capture_command(self, cmd: list[str], label: str):
        capture_helpers.log_capture_command(
            self.capture_context.current_meta,
            self.capture_context.log_writer,
            cmd,
            label,
        )

    def make_ffmpeg_frame_callback(self):
        return capture_helpers.make_ffmpeg_frame_callback(self.ui_queue)

    def execute_ffmpeg_command(self, cmd: list[str]):
        return capture_helpers.execute_ffmpeg_command(
            cmd,
            self.capture_context.log_writer,
            self.ui_queue,
            FPS,
            started_callback=lambda proc: setattr(self, "proc", proc),
        )

    def log_capture_exit_code(self, label: str, code: int):
        capture_helpers.log_capture_exit_code(self.capture_context.log_writer, label, code)

    def run_process(self, cmd: list[str], label: str, allow_manual_stop: bool = True):
        self.log_capture_command(cmd, label)
        proc, code = self.execute_ffmpeg_command(cmd)
        self.log_capture_exit_code(label, code)
        self.proc = None
        return code

    def stop_capture(self):
        self.status_var.set("正在停止，请等待 FFmpeg 收尾...")
        p = self.proc
        if p is not None:
            request_stop_process(p)

    def finalize_capture_summary(self, result: dict):
        capture_helpers.finalize_capture_summary(self.capture_context, result)

    def finish_session(self):
        assert self.capture_context.current_session is not None and self.capture_context.current_frames_dir is not None
        result = finalize_session(
            current_session=self.capture_context.current_session,
            current_frames_dir=self.capture_context.current_frames_dir,
            current_meta=self.capture_context.current_meta,
            start_time=self.start_time,
        )
        self.finalize_capture_summary(result)

    def apply_capture_metrics(self, metrics: dict):
        capture_helpers.apply_capture_metrics(
            self.elapsed_var,
            self.frame_count_var,
            self.used_size_var,
            self.estimate_var,
            self.capture_fps_var,
            metrics,
        )

    def update_timer(self):
        if self.capture_state.capture_running:
            now = time.time()
            metrics = capture_helpers.update_capture_timer_tick(
                capture_state=self.capture_state,
                capture_context=self.capture_context,
                now=now,
                fps=FPS,
                update_capture_metrics_fn=update_capture_metrics,
                log_writer=self.capture_context.log_writer,
            )
            self.apply_capture_metrics(metrics)
            self.after(500, self.update_timer)

    def apply_preview_frame(self, img):
        self.preview_image = preview_helpers.apply_preview_frame(self.preview_label, img)

    def apply_preview_status_text(self, text: str):
        preview_helpers.apply_preview_status_text(self.preview_status_var, text)

    def apply_preview_stopped_ui(self):
        self.preview_proc = None
        preview_helpers.apply_preview_stopped_ui(
            self.preview_status_var,
            self.preview_start_btn,
            self.preview_stop_btn,
        )

    def handle_preview_frame(self, action_data):
        try:
            img = preview_helpers.build_preview_frame_image(
                action_data,
                photo_image_factory=tk.PhotoImage,
            )
            self.apply_preview_frame(img)
        except Exception as e:
            self.preview_status_var.set(preview_helpers.preview_frame_error_text(e))

    def handle_preview_status(self, action_data):
        self.apply_preview_status_text(action_data)

    def handle_preview_stopped(self):
        if preview_helpers.should_apply_preview_stopped_ui(self.preview_proc):
            self.apply_preview_stopped_ui()

    def apply_capture_done_ui(self, finalized: dict):
        if finalized['cached_frame_count'] is not None:
            self.capture_state.apply_finalize_result(finalized)
            self.frame_count_var.set(finalized['frame_count_text'])
        if finalized['cached_session_size'] is not None:
            self.used_size_var.set(finalized['used_size_text'])

    def handle_capture_done(self):
        self.set_capture_running(False)
        self.status_var.set("已停止/完成。")
        finalized = capture_helpers.finalize_capture_done(
            capture_context=self.capture_context,
            finalize_capture_done_state_fn=finalize_capture_done_state,
        )
        self.apply_capture_done_ui(finalized)

    def dispatch_ui_action(self, action_kind: str, action_data):
        queue_helpers.apply_ui_action(self, action_kind, action_data)

    def process_queue(self):
        try:
            while True:
                queue_helpers.process_queue_once(
                    self.ui_queue,
                    self.capture_state,
                    process_ui_message,
                    self.dispatch_ui_action,
                )
        except queue.Empty:
            pass
        self.after(100, self.process_queue)

    def open_path(self, path: str):
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("打开失败", str(e))

    def on_close(self):
        if self.proc is not None:
            if not messagebox.askyesno("正在采集", "当前正在采集，是否停止并退出？"):
                return
            self.stop_capture()
            time.sleep(0.5)
        if self.preview_proc is not None:
            self.stop_preview(wait=True)
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
