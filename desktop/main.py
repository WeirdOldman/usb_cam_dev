from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QApplication,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from dataclasses import asdict

from controller.contracts import RuntimeConfigPatch, StartCaptureRequest
from controller.runtime_controller import RuntimeController
from usb_cam_paths import app_base_dir


class DesktopMainWindow(QMainWindow):
    def __init__(self, controller: RuntimeController):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("USB Cam 4K25")
        self.resize(1440, 960)

        self.preview_label = QLabel("Preview not started")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(720, 405)
        self.preview_label.setStyleSheet("background:#0f172a;color:#e2e8f0;border-radius:12px;")

        self.status_label = QLabel("")
        self.metrics_label = QLabel("")
        self.output_dir_edit = QLineEdit()
        self.camera_name_edit = QLineEdit()
        self.image_prefix_edit = QLineEdit()
        self.events_view = QTextEdit()
        self.events_view.setReadOnly(True)

        self.preview_button = QPushButton("Start Preview")
        self.start_button = QPushButton("Start Capture")
        self.stop_button = QPushButton("Stop Capture")
        self.save_button = QPushButton("Save Settings")

        self.preview_button.clicked.connect(self.on_preview_toggle)
        self.start_button.clicked.connect(self.on_start_capture)
        self.stop_button.clicked.connect(self.on_stop_capture)
        self.save_button.clicked.connect(self.on_save_config)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        left = QVBoxLayout()
        right = QVBoxLayout()
        layout.addLayout(left, 2)
        layout.addLayout(right, 1)

        preview_box = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.addWidget(self.preview_label)
        preview_layout.addWidget(self.status_label)
        preview_layout.addWidget(self.metrics_label)
        left.addWidget(preview_box)

        control_box = QGroupBox("Controls")
        control_layout = QGridLayout(control_box)
        control_layout.addWidget(QLabel("Output Dir"), 0, 0)
        control_layout.addWidget(self.output_dir_edit, 0, 1)
        control_layout.addWidget(QLabel("Camera"), 1, 0)
        control_layout.addWidget(self.camera_name_edit, 1, 1)
        control_layout.addWidget(QLabel("Image Prefix"), 2, 0)
        control_layout.addWidget(self.image_prefix_edit, 2, 1)
        control_layout.addWidget(self.preview_button, 3, 0)
        control_layout.addWidget(self.start_button, 3, 1)
        control_layout.addWidget(self.stop_button, 4, 0)
        control_layout.addWidget(self.save_button, 4, 1)
        right.addWidget(control_box)

        event_box = QGroupBox("Recent Events")
        event_layout = QVBoxLayout(event_box)
        event_layout.addWidget(self.events_view)
        right.addWidget(event_box)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_snapshot)
        self.refresh_timer.start(500)

        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self.refresh_preview)
        self.preview_timer.start(333)

        self.refresh_snapshot()

    def refresh_snapshot(self):
        snapshot = self.controller.snapshot()
        config = snapshot.config or self.controller.load_config()
        self.status_label.setText(snapshot.status_text)
        self.metrics_label.setText(
            f"Phase: {snapshot.capture_phase} | FPS: {snapshot.fps:.2f} | Frames: {snapshot.processed_frames} | CPU: {snapshot.cpu_percent:.1f}%"
        )
        self.output_dir_edit.setText(config.output_dir)
        self.camera_name_edit.setText(config.camera_name)
        self.image_prefix_edit.setText(config.image_prefix)
        self.preview_button.setText("Stop Preview" if snapshot.preview_enabled else "Start Preview")
        self.start_button.setDisabled(snapshot.ui_locks.capture_start_disabled)
        self.stop_button.setDisabled(snapshot.ui_locks.capture_stop_disabled)
        events_text = "\n".join(f"[{event.timestamp}] {event.kind}: {event.message}" for event in snapshot.events[-20:])
        self.events_view.setPlainText(events_text)

    def refresh_preview(self):
        frame = self.controller.get_preview_frame()
        if not frame:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(frame, "PNG"):
            self.preview_label.setPixmap(pixmap.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def on_preview_toggle(self):
        snapshot = self.controller.snapshot()
        if snapshot.preview_enabled:
            self.controller.stop_preview()
        else:
            self.controller.start_preview()
        self.refresh_snapshot()

    def on_start_capture(self):
        request = StartCaptureRequest(
            output_dir=self.output_dir_edit.text().strip() or None,
            image_prefix=self.image_prefix_edit.text().strip() or "img",
            camera_name=self.camera_name_edit.text().strip() or self.controller.camera_name,
            mode=self.controller.mode,
            quality_mode=self.controller.quality_mode,
            delete_video_after_extract=self.controller.delete_video_after_extract,
        )
        self.controller.start_capture(request)
        self.refresh_snapshot()

    def on_stop_capture(self):
        self.controller.stop_capture()
        self.refresh_snapshot()

    def on_save_config(self):
        patch = RuntimeConfigPatch(
            output_dir=self.output_dir_edit.text().strip() or None,
            camera_name=self.camera_name_edit.text().strip() or None,
            image_prefix=self.image_prefix_edit.text().strip() or None,
        )
        self.controller.update_config(patch)
        self.refresh_snapshot()


def create_desktop_app(*, base_dir: Path | None = None) -> tuple[RuntimeController, DesktopMainWindow]:
    controller = RuntimeController(base_dir=base_dir or Path(app_base_dir()))
    controller.set_directory_selector(lambda current_dir: QFileDialog.getExistingDirectory(None, "Select Output Directory", current_dir) or None)
    window = DesktopMainWindow(controller)
    return controller, window


def run_automation(
    *,
    command_path: Path,
    result_path: Path,
    base_dir: Path | None = None,
    timeout_seconds: float = 60.0,
) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    controller, window = create_desktop_app(base_dir=base_dir)
    window.showMinimized()

    deadline = time.time() + timeout_seconds
    command_payload: dict | None = None
    while time.time() < deadline:
        app.processEvents()
        if command_path.exists():
            command_payload = json.loads(command_path.read_text(encoding="utf-8"))
            break
        time.sleep(0.1)

    if command_payload is None:
        result_path.write_text(json.dumps({"ok": False, "error": "automation timeout"}, ensure_ascii=False, indent=2), encoding="utf-8")
        window.close()
        app.quit()
        return 1

    action = command_payload.get("action")
    payload = command_payload.get("payload") or {}
    result: dict
    try:
        if action == "smoke":
            devices = controller.load_camera_devices()
            result = {
                "ok": True,
                "window_title": window.windowTitle(),
                "config": asdict(controller.load_config()),
                "snapshot": asdict(controller.snapshot()),
                "devices": devices.devices,
            }
        elif action == "preview_start":
            result = asdict(controller.start_preview())
        elif action == "preview_stop":
            result = asdict(controller.stop_preview())
        elif action == "capture_start":
            request = StartCaptureRequest(
                mode=payload.get("mode", controller.mode),
                output_dir=payload.get("output_dir"),
                image_prefix=payload.get("image_prefix", controller.image_prefix),
                quality_mode=payload.get("quality_mode", controller.quality_mode),
                delete_video_after_extract=bool(payload.get("delete_video_after_extract", controller.delete_video_after_extract)),
                camera_name=payload.get("camera_name", controller.camera_name),
            )
            result = asdict(controller.start_capture(request))
        elif action == "capture_stop":
            result = asdict(controller.stop_capture())
        elif action == "release_validation":
            preview_start = asdict(controller.start_preview())
            time.sleep(float(payload.get("preview_seconds", 2.0)))
            preview_stop = asdict(controller.stop_preview())
            request = StartCaptureRequest(
                mode=payload.get("mode", "direct_frames"),
                output_dir=payload.get("output_dir"),
                image_prefix=payload.get("image_prefix", "img"),
                quality_mode=payload.get("quality_mode", "copy"),
                delete_video_after_extract=bool(payload.get("delete_video_after_extract", False)),
                camera_name=payload.get("camera_name", controller.camera_name),
            )
            capture_start = asdict(controller.start_capture(request))
            time.sleep(float(payload.get("capture_seconds", 3.0)))
            capture_stop = asdict(controller.stop_capture())
            time.sleep(float(payload.get("settle_seconds", 1.0)))
            result = {
                "ok": bool(preview_start.get("ok") and preview_stop.get("ok") and capture_start.get("ok") and capture_stop.get("ok")),
                "window_title": window.windowTitle(),
                "config": asdict(controller.load_config()),
                "devices": controller.load_camera_devices().devices,
                "preview_start": preview_start,
                "preview_stop": preview_stop,
                "capture_start": capture_start,
                "capture_stop": capture_stop,
                "monitor": asdict(controller.snapshot()),
            }
        elif action == "snapshot":
            result = {"ok": True, "snapshot": asdict(controller.snapshot())}
        elif action == "set_config":
            patch = RuntimeConfigPatch(
                camera_name=payload.get("camera_name"),
                output_dir=payload.get("output_dir"),
                image_prefix=payload.get("image_prefix"),
                mode=payload.get("mode"),
                quality_mode=payload.get("quality_mode"),
                delete_video_after_extract=payload.get("delete_video_after_extract"),
            )
            result = asdict(controller.update_config(patch))
        else:
            result = {"ok": False, "error": f"unknown action: {action}"}
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}

    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    window.close()
    app.quit()
    return 0 if result.get("ok") else 1


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="USB Cam 4K25 PySide6 desktop entry")
    parser.add_argument("--automation-command")
    parser.add_argument("--automation-result")
    parser.add_argument("--base-dir")
    args = parser.parse_args(argv)

    if args.automation_command and args.automation_result:
        return run_automation(
            command_path=Path(args.automation_command),
            result_path=Path(args.automation_result),
            base_dir=Path(args.base_dir) if args.base_dir else None,
        )

    app = QApplication.instance() or QApplication(sys.argv)
    _controller, window = create_desktop_app(base_dir=Path(args.base_dir) if args.base_dir else None)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
