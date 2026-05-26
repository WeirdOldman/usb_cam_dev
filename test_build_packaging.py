from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
UI_ROOT = REPO_ROOT / "ui"


def test_build_bat_targets_webview_backend_entry():
    content = (REPO_ROOT / "build.bat").read_text(encoding="utf-8")

    assert 'set "ENTRY_SCRIPT=backend\\main.py"' in content
    assert "build_webview.bat" in content


def test_build_bat_collects_ui_dist_directory():
    content = (REPO_ROOT / "build.bat").read_text(encoding="utf-8")

    assert "ui_dist;ui_dist" in content


def test_requirements_pywebview_covers_packaged_runtime_dependencies():
    content = (REPO_ROOT / "requirements-pywebview.txt").read_text(encoding="utf-8")

    assert "fastapi" in content
    assert "uvicorn[standard]" in content
    assert "pywebview" in content
    assert "opencv-python" in content
    assert "numpy" in content
    assert "requests" in content
    assert "psutil" in content
    assert "httpx" in content


def test_build_webview_script_targets_ui_dist_output():
    content = (REPO_ROOT / "build_webview.bat").read_text(encoding="utf-8")

    assert 'set "FRONTEND_OUT=%ROOT_DIR%ui_dist"' in content
    assert 'set "UI_DIR=%ROOT_DIR%ui"' in content
    assert r"node_modules\vite\bin\vite.js" in content
    assert "npm ci" in content
    assert "npm run build" in content
    assert "--configLoader native" not in content
    assert "PACKAGED_BUILD_NAME=dist_packaged_runtime_" in content


def test_build_webview_script_uses_unique_packaged_output_dir():
    content = (REPO_ROOT / "build_webview.bat").read_text(encoding="utf-8")

    assert 'mkdir "%PACKAGED_BUILD_OUT%"' in content
    assert 'mkdir "%PACKAGED_BUILD_OUT%\\assets"' in content
    assert 'xcopy /e /i /y "%PACKAGED_BUILD_OUT%\\*" "%FRONTEND_OUT%\\"' in content
    assert 'if exist "%PACKAGED_BUILD_OUT%" rmdir /s /q "%PACKAGED_BUILD_OUT%"' in content


def test_build_bat_has_explicit_python311_fallback():
    content = (REPO_ROOT / "build.bat").read_text(encoding="utf-8")

    assert r"C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe" in content


def test_build_bat_prefers_python_before_py_launcher_fallback():
    content = (REPO_ROOT / "build.bat").read_text(encoding="utf-8")

    python_index = content.index('python --version >nul 2>nul')
    py_launcher_index = content.index('py -3 --version >nul 2>nul')
    assert python_index < py_launcher_index


def test_build_bat_explains_dist_lock_failure():
    content = (REPO_ROOT / "build.bat").read_text(encoding="utf-8")

    assert "If dist cleanup fails, close any running USB_Cam_4K25.exe first." in content


def test_build_bat_checks_for_running_packaged_process():
    content = (REPO_ROOT / "build.bat").read_text(encoding="utf-8").lower()

    assert "tasklist" in content
    assert "usb_cam_4k25.exe" in content


def test_build_bat_copies_ffmpeg_into_packaged_tools_dir():
    content = (REPO_ROOT / "build.bat").read_text(encoding="utf-8")

    assert r'tools\ffmpeg.exe' in content
    assert r'%TOOLS_DIR%\ffmpeg.exe' in content


def test_build_bat_mentions_packaged_smoke_report_output():
    content = (REPO_ROOT / "build.bat").read_text(encoding="utf-8")

    assert "outputs\\packaged_runtime\\packaged_runtime_smoke_report.json" in content


def test_validate_packaged_runtime_script_runs_summary_validation():
    content = (REPO_ROOT / "validate_packaged_runtime.bat").read_text(encoding="utf-8")

    assert "build.bat" in content
    assert "--packaged-validation-summary-only" in content
    assert "USB_Cam_4K25.exe" in content
    assert "--camera-name" in content


def test_validate_packaged_runtime_failure_sample_script_uses_invalid_camera():
    content = (REPO_ROOT / "validate_packaged_runtime_failure_sample.bat").read_text(encoding="utf-8")

    assert "validate_packaged_runtime.bat" in content
    assert "INVALID_CAMERA" in content


def test_validate_packaged_runtime_script_uses_timestamped_report_dir():
    content = (REPO_ROOT / "validate_packaged_runtime.bat").read_text(encoding="utf-8")

    assert "for /f" in content.lower()
    assert "packaged_runtime" in content
    assert "packaged_validation_summary_report.json" in content


def test_validate_packaged_runtime_script_prints_summary_and_run_dir():
    content = (REPO_ROOT / "validate_packaged_runtime.bat").read_text(encoding="utf-8")

    assert "[RUN_DIR]" in content
    assert "[REPORT]" in content
    assert "[SUMMARY]" in content
    assert "packaged_validation_summary" in content
    assert "[WINDOW]" in content
    assert "[FFMPEG]" in content
    assert "[FRAMES]" in content
    assert "[ROOT]" in content
    assert "[DEVICES]" in content
    assert "[SESSION]" in content
    assert "[READY]" in content
    assert "json.load" in content
    assert "[CSV]" in content
    assert "[SUMMARY_FILE]" in content
    assert "[METADATA]" in content
    assert "[MANIFEST]" in content
    assert "[CHECKLIST]" in content
    assert "[GATE]" in content
    assert "[GATE_REASON]" in content
    assert "[DELTA_READY_SECONDS]" in content
    assert "[DELTA_FRAMES]" in content
    assert "[LATEST]" in content
    assert "[HISTORY]" in content
    assert "[BASELINE_RUN]" in content
    assert "[SKIPPED_RUNS]" in content


def test_validate_packaged_runtime_script_reports_artifact_paths_even_on_failure():
    content = (REPO_ROOT / "validate_packaged_runtime.bat").read_text(encoding="utf-8")

    assert "[ERROR] Packaged validation failed." in content
    assert "[RUN_DIR]" in content
    assert "[REPORT]" in content
    assert "[LATEST]" in content
    assert "[HISTORY]" in content


def test_quickstart_mentions_latest_and_history_indexes():
    content = (REPO_ROOT / "docs" / "requirements" / "WEBVIEW_PACKAGED_RUNTIME_QUICKSTART.md").read_text(encoding="utf-8")

    assert "latest_packaged_validation.json" in content
    assert "packaged_validation_history.json" in content
    assert "delta" in content.lower()
    assert "validate_packaged_runtime_failure_sample.bat" in content


def test_repo_contains_packaged_runtime_ui_source_tree():
    assert (UI_ROOT / "package.json").exists()
    assert (UI_ROOT / "src" / "main.tsx").exists()


def test_ci_workflow_targets_current_webview_runtime_tests():
    content = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "backend/main.py" in content
    assert "test_build_packaging.py" in content
    assert "test_backend_main.py" in content
    assert "test_usb_cam_real_validation.py" in content
    assert "test_usb_cam_refactor.py" not in content


def test_release_workflow_builds_repo_local_ui_and_current_backend_entry():
    content = (REPO_ROOT / ".github" / "workflows" / "build-windows-package.yml").read_text(encoding="utf-8")

    assert "backend/main.py" in content
    assert "usb_burst_cam_4k25_manual_v1_6_3.py" not in content
    assert "test_build_packaging.py" in content
    assert "test_backend_main.py" in content
    assert "test_usb_cam_real_validation.py" in content
    assert "actions/setup-node" in content
    assert "npm ci" in content
