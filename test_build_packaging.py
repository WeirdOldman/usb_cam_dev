import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
UI_ROOT = REPO_ROOT / "ui"


def load_ui_package() -> dict:
    return json.loads((UI_ROOT / "package.json").read_text(encoding="utf-8"))


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
    assert "npm ci" in content
    assert "npm run build" in content
    assert "--configLoader native" not in content
    assert "PACKAGED_BUILD_NAME=dist_packaged_runtime_" in content
    assert "set \"NODE_EXE=" not in content
    assert "set \"VITE_ENTRY=" not in content


def test_build_webview_script_uses_unique_packaged_output_dir():
    content = (REPO_ROOT / "build_webview.bat").read_text(encoding="utf-8")

    assert 'mkdir "%PACKAGED_BUILD_OUT%"' in content
    assert 'xcopy /e /i /y "%PACKAGED_BUILD_OUT%\\*" "%FRONTEND_OUT%\\"' in content
    assert 'if exist "%PACKAGED_BUILD_OUT%" rmdir /s /q "%PACKAGED_BUILD_OUT%"' in content


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


def test_ui_package_is_project_specific_and_trimmed_to_current_runtime():
    package = load_ui_package()

    assert package["name"] == "usb-cam-4k25-ui"
    assert set(package["dependencies"]) == {
        "lucide-react",
        "react",
        "react-dom",
        "tw-animate-css",
    }
    assert set(package["devDependencies"]) == {
        "@tailwindcss/vite",
        "@vitejs/plugin-react",
        "tailwindcss",
        "vite",
    }
    assert "peerDependencies" not in package
    assert "peerDependenciesMeta" not in package


def test_ui_tree_does_not_keep_template_residue():
    assert not (UI_ROOT / "src" / "app" / "components" / "figma").exists()
    assert not (UI_ROOT / "src" / "app" / "components" / "ui").exists()


def test_ui_readme_matches_current_project_scope():
    content = (UI_ROOT / "README.md").read_text(encoding="utf-8")

    assert "USB Cam 4K25" in content
    assert "PyWebView" in content
    assert "Figma" not in content


def test_vite_config_drops_figma_template_hooks():
    content = (UI_ROOT / "vite.config.ts").read_text(encoding="utf-8")

    assert "figma:asset/" not in content
    assert "@figma/my-make-file" not in content
    assert "required for Make" not in content


def test_repo_uses_current_structure_doc_instead_of_legacy_refactor_notes():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/CURRENT_PROJECT_STRUCTURE.md" in readme
    assert "USB_CAM_REFACTOR_STRUCTURE.md" not in readme
    assert "USB_CAM_REFACTOR_ROADMAP.md" not in readme
    assert not (REPO_ROOT / "USB_CAM_REFACTOR_STRUCTURE.md").exists()
    assert not (REPO_ROOT / "USB_CAM_REFACTOR_ROADMAP.md").exists()
    assert (REPO_ROOT / "docs" / "CURRENT_PROJECT_STRUCTURE.md").exists()


def test_stability_policy_tracks_current_webview_runtime_only():
    content = (REPO_ROOT / "docs" / "USB_CAM_STABILITY_POLICY.md").read_text(encoding="utf-8")

    assert "PyWebView" in content
    assert "backend/main.py" in content
    assert "Tkinter UI stays" not in content
    assert "usb_burst_cam_4k25_manual_v1_6_3.py" not in content


def test_project_handoff_doc_points_to_current_runtime_assets_only():
    content = (REPO_ROOT / "docs" / "USB_CAM_PROJECT_HANDOFF.md").read_text(encoding="utf-8")

    assert "135 passed" in content
    assert "CURRENT_PROJECT_STRUCTURE.md" in content
    assert "WEBVIEW_PACKAGED_RUNTIME_FINAL_VALIDATION_2026-05-26.md" in content
    assert "TK_LEGACY_RETIREMENT_PLAN_2026-05-25.md" not in content
    assert "test_usb_cam_refactor.py" not in content
    assert "usb_burst_cam_4k25_manual_v1_6_3.py" not in content


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
        "docs/USB_CAM_UI_FUTURE_OPTIONS_PYSIDE6_VS_CSHARP.md",
    ]

    for relative_path in obsolete_docs:
        assert not (REPO_ROOT / relative_path).exists(), relative_path

    assert not (REPO_ROOT / "docs" / "plans").exists()
    assert not (REPO_ROOT / "docs" / "aegis").exists()


def test_repo_drops_unused_pyinstaller_spec_file():
    assert not (REPO_ROOT / "USB_Cam_4K25.spec").exists()

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    handoff = (REPO_ROOT / "docs" / "USB_CAM_PROJECT_HANDOFF.md").read_text(encoding="utf-8")

    assert "USB_Cam_4K25.spec" not in readme
    assert "USB_Cam_4K25.spec" not in handoff


def test_backend_main_delegates_api_and_host_owners():
    content = (REPO_ROOT / "backend" / "main.py").read_text(encoding="utf-8")

    assert "from backend.runtime_api import (" in content
    assert "RuntimeApiConfig" in content
    assert "create_runtime_app" in content
    assert "from backend.runtime_host import (" in content
    assert (REPO_ROOT / "backend" / "runtime_api.py").exists()
    assert (REPO_ROOT / "backend" / "runtime_host.py").exists()


def test_backend_main_delegates_runtime_monitor_and_capture_owners():
    content = (REPO_ROOT / "backend" / "main.py").read_text(encoding="utf-8")

    assert "from backend.runtime_monitor import (" in content
    assert "from backend.runtime_capture import (" in content
    assert (REPO_ROOT / "backend" / "runtime_monitor.py").exists()
    assert (REPO_ROOT / "backend" / "runtime_capture.py").exists()


def test_real_validation_delegates_packaged_and_report_helpers():
    content = (REPO_ROOT / "usb_cam_real_validation.py").read_text(encoding="utf-8")

    assert "from usb_cam_validation_packaged import (" in content
    assert "from usb_cam_validation_reports import (" in content
    assert (REPO_ROOT / "usb_cam_validation_packaged.py").exists()
    assert (REPO_ROOT / "usb_cam_validation_reports.py").exists()


def test_real_validation_delegates_capture_validation_helpers():
    content = (REPO_ROOT / "usb_cam_real_validation.py").read_text(encoding="utf-8")

    assert "from usb_cam_validation_capture import (" in content
    assert (REPO_ROOT / "usb_cam_validation_capture.py").exists()


def test_runtime_api_websocket_stream_is_not_ack_driven():
    content = (REPO_ROOT / "backend" / "runtime_api.py").read_text(encoding="utf-8")

    assert 'await websocket.receive_text()' not in content
    assert "asyncio.sleep" in content


def test_idle_preview_is_disabled_by_default_in_frontend_and_ui():
    runtime_hook = (REPO_ROOT / "ui" / "src" / "app" / "components" / "monitoring" / "useMonitoringRuntime.ts").read_text(encoding="utf-8")
    preview_panel = (REPO_ROOT / "ui" / "src" / "app" / "components" / "monitoring" / "MonitoringPreviewPanel.tsx").read_text(encoding="utf-8")

    assert 'previewEnabled: false' in runtime_hook
    assert 'ws.send("ack")' not in runtime_hook
    assert "const streamActive = previewEnabled || isRunning" in preview_panel


def test_packaged_runtime_playbook_replaces_phase4_step_docs():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/USB_CAM_PACKAGED_RUNTIME_PLAYBOOK.md" in readme
    assert "USB_CAM_PHASE4_TASK3_1_FIRST_BUILD_GUIDE.md" not in readme
    assert "USB_CAM_PHASE4_TASK3_2_FIRST_BUILD_RECORD_TEMPLATE.md" not in readme
    assert "USB_CAM_PHASE4_TASK3_3_WINDOWS_RUN_PACKAGE.md" not in readme
    assert (REPO_ROOT / "docs" / "USB_CAM_PACKAGED_RUNTIME_PLAYBOOK.md").exists()
    assert not (REPO_ROOT / "docs" / "USB_CAM_PHASE4_TASK3_1_FIRST_BUILD_GUIDE.md").exists()
    assert not (REPO_ROOT / "docs" / "USB_CAM_PHASE4_TASK3_2_FIRST_BUILD_RECORD_TEMPLATE.md").exists()
    assert not (REPO_ROOT / "docs" / "USB_CAM_PHASE4_TASK3_3_WINDOWS_RUN_PACKAGE.md").exists()


def test_docs_clarify_local_tools_boundary():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    structure = (REPO_ROOT / "docs" / "CURRENT_PROJECT_STRUCTURE.md").read_text(encoding="utf-8")

    assert "tools/" in readme
    assert "不受版本控制" in readme
    assert "本地运行依赖" in readme
    assert "tools/" in structure
    assert "本地运行依赖" in structure
    assert "不受版本控制" in structure


def test_ci_workflow_targets_current_webview_runtime_tests():
    content = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "backend/main.py" in content
    assert "test_build_packaging.py" in content
    assert "test_backend_main.py" in content
    assert "test_usb_cam_real_validation.py" in content
    assert "test_usb_cam_refactor.py" not in content
    assert "requirements-pywebview.txt pytest pyinstaller" in content


def test_release_workflow_builds_repo_local_ui_and_current_backend_entry():
    content = (REPO_ROOT / ".github" / "workflows" / "build-windows-package.yml").read_text(encoding="utf-8")

    assert "backend/main.py" in content
    assert "usb_burst_cam_4k25_manual_v1_6_3.py" not in content
    assert "test_build_packaging.py" in content
    assert "test_backend_main.py" in content
    assert "test_usb_cam_real_validation.py" in content
    assert "actions/setup-node" in content
    assert "npm ci" in content
