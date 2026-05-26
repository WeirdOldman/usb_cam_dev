# WebView Packaged Runtime Quickstart

## Goal

为 `USB_Cam_4K25` 的新 `PyWebView + FastAPI + React` 壳提供最小可重复的打包前与打包后验证口径。

## Current Packaging Entry

- Packaging script: `E:\codex\usb_cam_dev\build.bat`
- Frontend asset prep: `E:\codex\usb_cam_dev\build_webview.bat`
- Desktop entry: `E:\codex\usb_cam_dev\backend\main.py`

## Preflight

1. Ensure Python dependencies are installed from:
   - `E:\codex\usb_cam_dev\requirements-pywebview.txt`
2. Ensure Node.js and npm are available.
3. Ensure `E:\codex\usb_cam_dev\tools\ffmpeg.exe` exists if you want real camera capture validation.

## Build Flow

1. Run:
   - `E:\codex\usb_cam_dev\build.bat`
2. The script will:
   - build the frontend in `E:\codex\usb_cam_dev\ui`
   - copy static assets into `E:\codex\usb_cam_dev\ui_dist`
   - package `backend\main.py` with PyInstaller

## Expected Output

- Dist root:
  - `E:\codex\usb_cam_dev\dist\USB_Cam_4K25`

## Minimum Validation

1. Launch packaged app.
2. Verify the window opens without requiring `localhost:5173`.
3. Verify preview area renders.
4. Verify camera device list is visible when FFmpeg can enumerate DirectShow devices.
5. Verify:
   - preview start/stop
   - capture start/stop
   - output directory selection
   - runtime config save
   - FFmpeg status check

## Validation Helper

One-shot packaged validation entry:

- `E:\codex\usb_cam_dev\validate_packaged_runtime.bat`

Optional camera override:

- `E:\codex\usb_cam_dev\validate_packaged_runtime.bat "camera name"`

Failure sample wrapper:

- `E:\codex\usb_cam_dev\validate_packaged_runtime_failure_sample.bat`
  - runs the packaged validation flow with `INVALID_CAMERA`
  - should produce a `fail` gate sample for release validation diagnostics

This batch entry creates a timestamped run directory under:

- `E:\codex\usb_cam_dev\outputs\packaged_runtime\`

At the end of the run it also prints a compact terminal summary including:

- manifest path
- checklist path
- release gate
- release gate reason
- overall ok state
- window title
- root endpoint state
- root readiness attempts / seconds
- ffmpeg path
- camera devices
- capture session directory
- capture frame count
- frames.csv path
- summary.txt path
- metadata.json path

Packaged runtime smoke validation can now be scripted via:

- `usb_cam_real_validation.packaged_runtime_smoke(...)`
- `usb_cam_real_validation.run_packaged_runtime_smoke_validation(...)`

CLI form:

```powershell
python usb_cam_real_validation.py --packaged-runtime-smoke-only --exe-path E:\codex\usb_cam_dev\dist\USB_Cam_4K25\USB_Cam_4K25.exe --api-base-url http://127.0.0.1:8000 --report-path E:\codex\usb_cam_dev\outputs\packaged_runtime_smoke\report.json
```

If `--report-path` is omitted, the default output is:

- `E:\codex\usb_cam_dev\outputs\packaged_runtime\packaged_runtime_smoke_report.json`

The packaged smoke report now captures at least:

- process pid / alive state
- window title
- root endpoint status
- root readiness attempts / ready seconds
- FFmpeg detection result
- camera device list

The packaged release / summary reports now also surface capture evidence file paths for:

- `frames.csv`
- `summary.txt`
- `metadata.json`

Each packaged validation run now also writes a dedicated manifest file that indexes:

- summary JSON report
- summary Markdown report
- smoke report
- release report
- capture session directory
- `frames.csv`
- `summary.txt`
- `metadata.json`

Stable packaged validation index files are also maintained at:

- `E:\codex\usb_cam_dev\outputs\packaged_runtime\latest_packaged_validation.json`
- `E:\codex\usb_cam_dev\outputs\packaged_runtime\packaged_validation_history.json`

These let you inspect:

- the latest packaged validation run without guessing the timestamped directory
- recent packaged validation runs as a lightweight history ledger
- delta metrics such as `root_ready_seconds` and `frame_count` versus the previous run

Each run also emits a human-readable release checklist Markdown file that summarizes the main pass/fail checks for:

- root endpoint reachability
- FFmpeg detection
- preview start / stop
- capture start / stop
- frame production
- `frames.csv`
- `summary.txt`
- `metadata.json`

For a broader packaged release check that also exercises preview/capture/control flow:

```powershell
python usb_cam_real_validation.py --packaged-release-validation-only --exe-path E:\codex\usb_cam_dev\dist\USB_Cam_4K25\USB_Cam_4K25.exe --api-base-url http://127.0.0.1:8000 --output-root E:\codex\usb_cam_dev\outputs\packaged_release --report-path E:\codex\usb_cam_dev\outputs\packaged_runtime\packaged_release_validation_report.json
```

For a single top-level packaged summary report:

```powershell
python usb_cam_real_validation.py --packaged-validation-summary-only --exe-path E:\codex\usb_cam_dev\dist\USB_Cam_4K25\USB_Cam_4K25.exe --api-base-url http://127.0.0.1:8000 --output-root E:\codex\usb_cam_dev\outputs\packaged_release --report-path E:\codex\usb_cam_dev\outputs\packaged_runtime\packaged_validation_summary_report.json
```

## Current Boundary

This quickstart assumes:

- Tk UI has already been retired from the default desktop entry path.
- Static frontend assets are loaded from packaged `ui_dist`.
- Packaged runtime minimum validation has already been completed once and should now be used as the baseline path.
