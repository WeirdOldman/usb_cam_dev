# WebView Packaged Runtime Status 2026-05-24

## Current State

The new `PyWebView + FastAPI + React` packaged runtime is now the default packaging entry and can be built successfully.

Confirmed:

- `build.bat` packages `backend\main.py`
- `ui_dist` is included in the packaged output
- `tools\ffmpeg.exe` is copied into the packaged output
- packaged process starts successfully
- packaged process listens on `127.0.0.1:8000`

## Evidence

- packaged output:
  - `E:\codex\usb_cam_dev\dist\USB_Cam_4K25`
- packaged executable:
  - `E:\codex\usb_cam_dev\dist\USB_Cam_4K25\USB_Cam_4K25.exe`
- packaged frontend assets:
  - `E:\codex\usb_cam_dev\dist\USB_Cam_4K25\_internal\ui_dist`
- packaged ffmpeg:
  - `E:\codex\usb_cam_dev\dist\USB_Cam_4K25\tools\ffmpeg.exe`

## Known Runtime Failure

The packaged process currently shows:

- window title: `Unhandled exception in script`

At the same time:

- process remains alive
- local port `8000` is listening

But:

- `http://127.0.0.1:8000/` request times out during packaged runtime validation

## Interpretation

This means the project has crossed the "can package" threshold, but has not yet crossed the "packaged runtime fully usable" threshold.

The current blocker is no longer:

- frontend build
- static asset packaging
- entry-script selection
- tkinter import chain

The current blocker is:

- packaged runtime startup/serve path still hits an exception after process launch
- backend port is open, but request handling is not healthy enough to complete the basic root request

## Next Debug Focus

1. Capture packaged runtime exception details directly from the packaged process.
2. Identify whether the exception is inside:
   - PyWebView window initialization
   - FastAPI request handling
   - runtime event/state serialization
   - packaged file/resource lookup
3. Fix the packaged-runtime exception before removing the legacy Tk UI code.

## Historical Note

This document captured the intermediate state before the final packaged runtime validation succeeded.

Tk retirement was blocked at that time because packaged runtime usability was not yet green.
