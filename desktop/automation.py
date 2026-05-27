from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path


def run_desktop_automation(
    *,
    exe_path: Path,
    action: str,
    payload: dict | None = None,
    base_dir: Path | None = None,
    timeout_seconds: float = 60.0,
) -> dict:
    with tempfile.TemporaryDirectory(prefix="usb_cam_automation_") as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)
        command_path = temp_dir / "command.json"
        result_path = temp_dir / "result.json"
        command_path.write_text(
            json.dumps({"action": action, "payload": payload or {}}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        cmd = [
            str(exe_path),
            "--automation-command",
            str(command_path),
            "--automation-result",
            str(result_path),
        ]
        if base_dir is not None:
            cmd.extend(["--base-dir", str(base_dir)])
        proc = subprocess.Popen(cmd, cwd=str(exe_path.parent))
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if result_path.exists():
                break
            if proc.poll() is not None:
                break
            time.sleep(0.2)
        if not result_path.exists():
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
            raise RuntimeError(f"Desktop automation did not produce result in time: {action}")
        if proc.poll() is None:
            proc.wait(timeout=10)
        return json.loads(result_path.read_text(encoding="utf-8"))
