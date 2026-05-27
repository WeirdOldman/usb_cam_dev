from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent


def test_build_bat_targets_desktop_entry():
    content = (REPO_ROOT / "build.bat").read_text(encoding="utf-8")

    assert 'set "ENTRY_SCRIPT=desktop\\main.py"' in content
    assert "build_webview.bat" not in content
    assert "ui_dist;ui_dist" not in content


def test_requirements_desktop_covers_runtime_dependencies():
    content = (REPO_ROOT / "requirements-desktop.txt").read_text(encoding="utf-8")

    assert "PySide6" in content
    assert "opencv-python" in content
    assert "numpy" in content
    assert "psutil" in content
    assert "pyinstaller" not in content
    assert "fastapi" not in content
    assert "uvicorn" not in content
    assert "pywebview" not in content


def test_build_bat_has_explicit_python311_fallback():
    content = (REPO_ROOT / "build.bat").read_text(encoding="utf-8")

    assert r"C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe" in content


def test_build_bat_honors_github_python_env_before_local_fallbacks():
    content = (REPO_ROOT / "build.bat").read_text(encoding="utf-8")

    assert "if defined pythonLocation" in content
    assert "if defined Python3_ROOT_DIR" in content
    assert "if defined Python_ROOT_DIR" in content


def test_build_bat_prefers_python_before_py_launcher_fallback():
    content = (REPO_ROOT / "build.bat").read_text(encoding="utf-8")

    github_env_index = content.index("if defined pythonLocation")
    local_fallback_index = content.index(r'C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe')
    python_index = content.index('python --version >nul 2>nul')
    py_launcher_index = content.index('py -3 --version >nul 2>nul')
    assert github_env_index < local_fallback_index
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


def test_validate_packaged_runtime_script_runs_summary_validation():
    content = (REPO_ROOT / "validate_packaged_runtime.bat").read_text(encoding="utf-8")

    assert "build.bat" in content
    assert "--packaged-validation-summary-only" in content
    assert "USB_Cam_4K25.exe" in content
    assert "--camera-name" in content
    assert "--api-base-url" not in content


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
    assert "[DEVICES]" in content
    assert "[SESSION]" in content
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


def test_repo_uses_current_structure_doc_instead_of_legacy_refactor_notes():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/CURRENT_PROJECT_STRUCTURE.md" in readme
    assert "USB_CAM_REFACTOR_STRUCTURE.md" not in readme
    assert "USB_CAM_REFACTOR_ROADMAP.md" not in readme
    assert not (REPO_ROOT / "USB_CAM_REFACTOR_STRUCTURE.md").exists()
    assert not (REPO_ROOT / "USB_CAM_REFACTOR_ROADMAP.md").exists()
    assert (REPO_ROOT / "docs" / "CURRENT_PROJECT_STRUCTURE.md").exists()


def test_repo_drops_obsolete_legacy_phase_docs():
    obsolete_docs = [
        "docs/USB_CAM_DEV_PAUSE_CHECKPOINT_2026-05-07.md",
        "docs/USB_CAM_MANUAL_VALIDATION_CHECKLIST.md",
        "docs/USB_CAM_PHASE4_BUILD_RUN_2026-05-24_R1.md",
        "docs/USB_CAM_PHASE4_CURRENT_STATUS_NOTE.md",
        "docs/USB_CAM_PHASE4_RC_STATUS_2026-05-24.md",
        "docs/USB_CAM_STABILITY_PHASE_CLOSURE_2026-05-24.md",
        "docs/USB_CAM_STABILITY_STATUS_2026-05-24.md",
        "docs/requirements/TK_LEGACY_RETIREMENT_PLAN_2026-05-25.md",
        "docs/requirements/WEBVIEW_PACKAGED_RUNTIME_FINAL_VALIDATION_2026-05-25.md",
        "docs/requirements/WEBVIEW_PACKAGED_RUNTIME_STATUS_2026-05-24.md",
        "docs/requirements/2026-05-01-execute-governed-plan-usb-camera-packaging-pyinstaller-onedir-wi.md",
        "docs/requirements/2026-05-01-refactor-usb-cam-python-tkinter-ffmpeg-windows-desktop-app-phase.md",
    ]

    for relative_path in obsolete_docs:
        assert not (REPO_ROOT / relative_path).exists(), relative_path

    assert not (REPO_ROOT / "docs" / "plans").exists()
    assert not (REPO_ROOT / "docs" / "aegis").exists()


def test_repo_drops_unused_pyinstaller_spec_file():
    assert not (REPO_ROOT / "USB_Cam_4K25.spec").exists()


def test_project_targets_pyside6_controller_entrypoints():
    assert (REPO_ROOT / "desktop" / "main.py").exists()
    assert (REPO_ROOT / "desktop" / "automation.py").exists()
    assert (REPO_ROOT / "controller" / "runtime_controller.py").exists()
    assert (REPO_ROOT / "controller" / "contracts.py").exists()


def test_repo_retires_webview_and_react_source_tree():
    assert not (REPO_ROOT / "ui").exists()
    assert not (REPO_ROOT / "build_webview.bat").exists()
    assert not (REPO_ROOT / "requirements-pywebview.txt").exists()
    assert not (REPO_ROOT / "backend" / "runtime_api.py").exists()


def test_ci_workflow_targets_pyside6_runtime_tests():
    content = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "requirements-desktop.txt pytest pyinstaller" in content
    assert "desktop/main.py" in content
    assert "controller/runtime_controller.py" in content
    assert "test_runtime_controller.py" in content
    assert "test_desktop_main.py" in content
    assert "test_usb_cam_real_validation.py" in content
    assert "actions/setup-node" not in content
    assert "npm ci" not in content
    assert "test_backend_main.py" not in content


def test_release_workflow_targets_pyside6_package_build():
    content = (REPO_ROOT / ".github" / "workflows" / "build-windows-package.yml").read_text(encoding="utf-8")

    assert "requirements-desktop.txt pytest pyinstaller" in content
    assert "desktop/main.py" in content
    assert "controller/runtime_controller.py" in content
    assert "test_runtime_controller.py" in content
    assert "test_desktop_main.py" in content
    assert "actions/setup-node" not in content
    assert "npm ci" not in content
