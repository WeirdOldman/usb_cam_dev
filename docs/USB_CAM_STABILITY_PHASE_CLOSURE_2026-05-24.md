# USB_CAM Stability Phase Closure 2026-05-24

## Goal

Summarize the completed stability-hardening work after the packaged Windows
recording closure and define a clean stop state for the current phase.

This document is the close-out view for the current stability slice.

## Baseline

Starting application baseline:

- branch: `main`
- latest upstream baseline:
  - `5b1232a` `v1.6.4`
- packaged validation closure already complete before this slice

Primary baseline records:

- [USB_CAM_PHASE4_RC_STATUS_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_PHASE4_RC_STATUS_2026-05-24.md)
- [USB_CAM_STABILITY_STATUS_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_STABILITY_STATUS_2026-05-24.md)
- [USB_CAM_STABILITY_POLICY.md](/E:/codex/usb_cam_dev/docs/USB_CAM_STABILITY_POLICY.md)

## What This Phase Added

### 1. Runtime health metrics

Added and wired:

- `write_rate_mb_s`
- `estimated_time_left_s`
- `estimated_time_left_text`
- `capture_health`
- `capture_health_reason`

Primary code:

- [usb_cam_capture_state.py](/E:/codex/usb_cam_dev/usb_cam_capture_state.py)
- [usb_cam_ui_state.py](/E:/codex/usb_cam_dev/usb_cam_ui_state.py)
- [usb_cam_capture_helpers.py](/E:/codex/usb_cam_dev/usb_cam_capture_helpers.py)
- [usb_burst_cam_4k25_manual_v1_6_3.py](/E:/codex/usb_cam_dev/usb_burst_cam_4k25_manual_v1_6_3.py)

### 2. AutoStop framework

Added and persisted:

- `auto_stopped`
- `stop_reason`
- `stop_reason_detail`

Primary code:

- [usb_cam_stop_prefs.py](/E:/codex/usb_cam_dev/usb_cam_stop_prefs.py)
- [usb_cam_runtime.py](/E:/codex/usb_cam_dev/usb_cam_runtime.py)
- [usb_cam_session_finalize.py](/E:/codex/usb_cam_dev/usb_cam_session_finalize.py)

### 3. First default AutoStop rule enabled

Enabled by default:

- `min_disk_free_mb_hard = 5120.0`

That is the only default-on stop rule in the current phase.

### 4. Real validation helper expanded

The helper now supports:

- general real-device validation
- disk-floor direct validation
- disk-floor video-then-frames validation
- max-duration validation
- fps-ratio validation
- temporary override inputs
- camera-in-use failure classification
- process-conflict reporting
- wrapper-layer preflight short-circuiting

Primary code:

- [usb_cam_real_validation.py](/E:/codex/usb_cam_dev/usb_cam_real_validation.py)
- [test_usb_cam_real_validation.py](/E:/codex/usb_cam_dev/test_usb_cam_real_validation.py)

## Real Validation Evidence Produced In This Phase

### Disk floor / direct

- record:
  - [USB_CAM_AUTOSTOP_DISK_FLOOR_VALIDATION_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_AUTOSTOP_DISK_FLOOR_VALIDATION_2026-05-24.md)
- session:
  - [direct_frames_disk_floor_validation_20260524_165804](/E:/codex/usb_cam_dev/_validation/auto_stop_real_runs/direct_frames_disk_floor_validation_20260524_165804)

### Disk floor / video_then_frames

- record:
  - [USB_CAM_AUTOSTOP_DISK_FLOOR_VIDEO_THEN_FRAMES_VALIDATION_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_AUTOSTOP_DISK_FLOOR_VIDEO_THEN_FRAMES_VALIDATION_2026-05-24.md)
- session:
  - [video_then_frames_disk_floor_validation_20260524_170358](/E:/codex/usb_cam_dev/_validation/auto_stop_real_runs/video_then_frames_disk_floor_validation_20260524_170358)

### Max duration / direct

- record:
  - [USB_CAM_AUTOSTOP_MAX_DURATION_VALIDATION_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_AUTOSTOP_MAX_DURATION_VALIDATION_2026-05-24.md)
- session:
  - [direct_frames_max_duration_validation_20260524_181235](/E:/codex/usb_cam_dev/_validation/max_duration_real_runs/direct_frames_max_duration_validation_20260524_181235)

### FPS ratio / direct

- record:
  - [USB_CAM_AUTOSTOP_FPS_RATIO_VALIDATION_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_AUTOSTOP_FPS_RATIO_VALIDATION_2026-05-24.md)
- session:
  - [direct_frames_fps_ratio_validation_20260524_182216](/E:/codex/usb_cam_dev/_validation/fps_ratio_real_runs/direct_frames_fps_ratio_validation_20260524_182216)

## Current Policy State

### Default enabled

- disk floor

### Explicitly supported but still opt-in

- `max_duration_s`
- `min_effective_fps_ratio`

Why they remain opt-in:

- no current product requirement for a default recording cap
- no natural real-world degraded-FPS evidence yet
- higher false-positive risk compared with disk-floor stop

## Validation Ergonomics Improved

This phase also improved field-diagnosis quality:

- camera lock conflicts are now a named failure class
  - `failure_reason = camera_in_use`
- dedicated disk-floor wrappers can short-circuit before launch when likely
  capture conflicts already exist
- likely conflict processes are reported back in result payloads

## Current Automated Baseline

Automated baseline at phase close:

- `pytest`: `62 passed`

Covered suites:

- [test_usb_cam_refactor.py](/E:/codex/usb_cam_dev/test_usb_cam_refactor.py)
- [test_usb_cam_real_validation.py](/E:/codex/usb_cam_dev/test_usb_cam_real_validation.py)

## Stop State

This phase should be considered complete if the question is:

`Did we turn the packaged-recording closure into a real stability phase with default disk-floor protection, usable helper tooling, and real evidence for the major stop-rule paths?`

Answer:

`yes`

## What Is Still Open But Non-Blocking

1. Decide whether `max_duration_s` should remain opt-in or become a product requirement
2. Decide whether `min_effective_fps_ratio` should remain opt-in or gain stronger field evidence first
3. Optional `video_then_frames` max-duration validation
4. Optional packaged-app helper for the same failure reporting patterns
5. Optional wider soak after any future default-threshold changes

## Recommended Commit Boundary

This phase now has a coherent commit boundary:

- docs status cleanup
- runtime health metrics
- AutoStop framework
- default disk-floor enablement
- helper validation tooling
- real validation evidence docs

If you want to stop here and ship a single stability phase commit series, this
is a good boundary.

## One-Line Summary

`The 2026-05-24 stability phase converted usb_cam_dev from “recording closure complete” into a documented, test-backed, real-device-validated stability baseline with one default stop rule and two additional proven opt-in stop mechanisms.`
