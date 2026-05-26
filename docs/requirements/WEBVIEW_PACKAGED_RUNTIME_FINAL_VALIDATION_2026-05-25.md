# WebView Packaged Runtime Final Validation 2026-05-25

## Result

Packaged `PyWebView + FastAPI + React` runtime validation passed for the minimum desktop replacement scope.

## Packaged Artifact

- `E:\codex\usb_cam_dev\dist\USB_Cam_4K25\USB_Cam_4K25.exe`

## Verified

1. Packaged process launches successfully.
2. Packaged window title shows `USB Cam 4K25`.
3. Local FastAPI root endpoint responds:
   - `http://127.0.0.1:8000/`
4. Config endpoint responds.
5. Camera devices endpoint responds.
6. FFmpeg status endpoint responds and resolves packaged `tools\ffmpeg.exe`.
7. Preview start / stop endpoints respond.
8. Capture start / stop endpoints respond.
9. Real output directory artifacts are created.

## Output Evidence

Validated output directory:

- `E:\codex\usb_cam_dev\outputs\packaged_final`

Standard packaged smoke report path:

- `E:\codex\usb_cam_dev\outputs\packaged_runtime\packaged_runtime_smoke_report.json`

## Decision

The new packaged runtime has crossed the minimum threshold required to begin deleting the legacy Tk UI layer.
