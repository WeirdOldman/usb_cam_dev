@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "APP_DIR=%SCRIPT_DIR%dist\USB_Cam_4K25"
set "APP_EXE=%APP_DIR%\USB_Cam_4K25.exe"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmmss"') do set "RUN_ID=%%I"
set "RUN_DIR=%SCRIPT_DIR%outputs\packaged_runtime\%RUN_ID%"
set "REPORT_PATH=%RUN_DIR%\packaged_validation_summary_report.json"
set "VALIDATION_OUTPUT_ROOT=%SCRIPT_DIR%outputs\packaged_release"
set "CAMERA_NAME_ARG="
if not "%~1"=="" (
  set "CAMERA_NAME_ARG=--camera-name %~1"
)

call "%SCRIPT_DIR%build.bat"
if errorlevel 1 (
  echo [ERROR] Build step failed.
  exit /b 1
)

if not exist "%APP_EXE%" (
  echo [ERROR] Packaged executable not found: %APP_EXE%
  exit /b 1
)

set "PY_CMD="
if not defined PY_CMD (
  if exist "C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe" (
    set "PY_CMD=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe"
  )
)

if not defined PY_CMD (
  py -3 --version >nul 2>nul
  if not errorlevel 1 (
    set "PY_CMD=py -3"
  )
)

if not defined PY_CMD (
  python --version >nul 2>nul
  if not errorlevel 1 (
    set "PY_CMD=python"
  )
)

if not defined PY_CMD (
  echo [ERROR] Python launcher not found. Install Python 3.10+ first.
  exit /b 1
)

%PY_CMD% usb_cam_real_validation.py ^
  --packaged-validation-summary-only ^
  --exe-path "%APP_EXE%" ^
  --output-root "%VALIDATION_OUTPUT_ROOT%" ^
  %CAMERA_NAME_ARG% ^
  --report-path "%REPORT_PATH%"

set "VALIDATION_EXIT=%ERRORLEVEL%"

echo [RUN_DIR] %RUN_DIR%
echo [REPORT] %REPORT_PATH%
if exist "%REPORT_PATH%" (
  for /f "delims=" %%I in ('%PY_CMD% -c "import json; p=r'%REPORT_PATH%'; data=json.load(open(p,'r',encoding='utf-8')); s=data.get('packaged_validation_summary',{}); smoke=s.get('packaged_runtime_smoke',{}); release=s.get('packaged_release_validation',{}); artifacts=release.get('capture_artifacts') or {}; reasons=data.get('release_gate_reasons') or []; latest_path=data.get('latest_index_path'); history_path=data.get('history_index_path'); latest={}; delta={}; comparison={}; import pathlib; latest = json.load(open(latest_path,'r',encoding='utf-8')) if latest_path and pathlib.Path(latest_path).exists() else {}; delta = latest.get('delta') or {}; comparison = latest.get('comparison_baseline') or {}; print('[LATEST] ' + str(latest_path)); print('[HISTORY] ' + str(history_path)); print('[BASELINE_RUN] ' + str(comparison.get('selected_run_id'))); print('[SKIPPED_RUNS] ' + str(comparison.get('skipped_run_ids'))); print('[MANIFEST] ' + str(data.get('manifest_path'))); print('[CHECKLIST] ' + str(data.get('checklist_path'))); print('[GATE] ' + str(data.get('release_gate'))); print('[GATE_REASON] ' + (' | '.join(map(str, reasons)) if reasons else '')); print('[SUMMARY] ok=' + str(s.get('ok'))); print('[WINDOW] ' + str(smoke.get('window_title'))); print('[READY] attempts=' + str(smoke.get('root_ready_attempts')) + ' seconds=' + str(smoke.get('root_ready_seconds'))); print('[DELTA_READY_SECONDS] ' + str(delta.get('root_ready_seconds'))); print('[FFMPEG] ' + str(smoke.get('ffmpeg_path'))); print('[DEVICES] ' + str(smoke.get('camera_devices'))); print('[SESSION] ' + str(artifacts.get('session_dir'))); print('[FRAMES] ' + str(artifacts.get('frame_count'))); print('[DELTA_FRAMES] ' + str(delta.get('frame_count'))); print('[CSV] ' + str(artifacts.get('frames_csv_path'))); print('[SUMMARY_FILE] ' + str(artifacts.get('summary_path'))); print('[METADATA] ' + str(artifacts.get('metadata_path')))"') do echo %%I
) else (
  echo [WARN] Validation report not found: %REPORT_PATH%
)

if %VALIDATION_EXIT% neq 0 (
  echo [ERROR] Packaged validation failed.
  exit /b %VALIDATION_EXIT%
)

echo [OK] Packaged validation completed.
exit /b 0
