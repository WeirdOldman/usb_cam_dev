# Tk Legacy Retirement Plan 2026-05-25

## Goal

After the packaged `PyWebView + FastAPI + React` runtime has completed:

- packaged build success
- packaged process startup success
- root API success
- minimum capture round-trip success

the old Tk desktop UI should no longer remain mixed with the default project entry surface.

## Current Boundary

The following files are still Tk-only or Tk-first:

- `E:\codex\usb_cam_dev\usb_burst_cam_4k25_manual_v1_6_3.py`
- `E:\codex\usb_cam_dev\usb_cam_preview_helpers.py`
- `E:\codex\usb_cam_dev\usb_cam_queue_helpers.py`
- `E:\codex\usb_cam_dev\usb_cam_finalize.py`

These files are still valid as historical reference, but they should no longer live as if they are part of the active default UI entry path.

## Recommended Retirement Steps

Completed:

1. Tk-only entry and helpers were moved into a dedicated legacy folder.
2. Tk-specific tests were temporarily updated to import from the legacy location.
3. New packaged runtime validation passed.
4. Tk-only UI code layer was deleted after packaged validation.

## Do Not Do Yet

- Do not delete backend-neutral modules that are still reused by the new runtime.
