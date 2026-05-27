from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from desktop.main import create_desktop_app, run_automation


def test_create_desktop_app_builds_main_window(tmp_path: Path):
    app = QApplication.instance() or QApplication([])

    controller, window = create_desktop_app(base_dir=tmp_path)

    assert controller.base_dir == tmp_path
    assert window.windowTitle() == "USB Cam 4K25"
    assert window.controller is controller
    assert window.preview_label is not None
    assert window.status_label.text()

    window.close()
    app.quit()


def test_run_automation_smoke_writes_result(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    command_path = tmp_path / "command.json"
    result_path = tmp_path / "result.json"
    command_path.write_text(json.dumps({"action": "smoke"}), encoding="utf-8")

    exit_code = run_automation(
        command_path=command_path,
        result_path=result_path,
        base_dir=tmp_path,
        timeout_seconds=1.0,
    )

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["window_title"] == "USB Cam 4K25"
    assert payload["config"]["output_dir"] == str(tmp_path / "capture_output")
    app.quit()
