# USB_CAM Stability Status 2026-05-24

## Scope

This document summarizes the stability-hardening work completed after the
`2026-05-24` packaged Windows release-candidate closure.

It sits one layer above:

- [USB_CAM_PHASE4_RC_STATUS_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_PHASE4_RC_STATUS_2026-05-24.md)
- [USB_CAM_STABILITY_POLICY.md](/E:/codex/usb_cam_dev/docs/USB_CAM_STABILITY_POLICY.md)

Use this file as the short status baseline for “what stability work is already
done” before starting the next round.

## Current Position

Current position can be stated as:

`The packaged Windows recording flow is validated, the first default AutoStop rule is enabled, and the disk-floor AutoStop path has been validated end-to-end in both capture modes.`

## What Is Already Complete

### 1. Project status wording has been updated

The repo no longer treats Phase 4 as “recording not yet closed.”

Relevant docs updated:

- [README.md](/E:/codex/usb_cam_dev/README.md)
- [USB_CAM_REFACTOR_ROADMAP.md](/E:/codex/usb_cam_dev/USB_CAM_REFACTOR_ROADMAP.md)
- [USB_CAM_PROJECT_HANDOFF.md](/E:/codex/usb_cam_dev/docs/USB_CAM_PROJECT_HANDOFF.md)

### 2. Runtime capture-health metrics exist

The runtime now carries:

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

### 3. AutoStop framework exists in production code

The app now supports AutoStop decision plumbing, metadata persistence, and log
recording.

Primary code:

- [usb_cam_stop_prefs.py](/E:/codex/usb_cam_dev/usb_cam_stop_prefs.py)
- [usb_cam_runtime.py](/E:/codex/usb_cam_dev/usb_cam_runtime.py)
- [usb_cam_session_finalize.py](/E:/codex/usb_cam_dev/usb_cam_session_finalize.py)
- [usb_burst_cam_4k25_manual_v1_6_3.py](/E:/codex/usb_cam_dev/usb_burst_cam_4k25_manual_v1_6_3.py)

Session metadata now reserves:

- `auto_stopped`
- `stop_reason`
- `stop_reason_detail`

### 4. First default AutoStop rule is enabled

The first active default rule is:

- `min_disk_free_mb_hard = 5120.0`

This means a hard disk-floor stop is active by default.

Not yet active by default:

- `max_duration_s`
- `min_effective_fps_ratio`

Current note:

- `max_duration_s` override support is present
- default enablement is intentionally deferred until there is an explicit product rule for operator-visible recording caps
- `max_duration_s` now also has direct real-device validation evidence in `direct_frames`
- `min_effective_fps_ratio` now also has direct helper-path validation evidence in `direct_frames`

### 5. Validation helper now supports stable AutoStop testing

The helper can now:

- run general real-device validation
- run `direct_frames` disk-floor AutoStop-only validation
- run `video_then_frames` disk-floor AutoStop-only validation
- temporarily override the disk-floor threshold
- classify `camera_in_use` style failures
- short-circuit preflight failures before starting ffmpeg in dedicated disk-floor validation modes
- report process conflicts involving:
  - `ffmpeg.exe`
  - `USB_Cam_4K25.exe`

Primary code:

- [usb_cam_real_validation.py](/E:/codex/usb_cam_dev/usb_cam_real_validation.py)
- [test_usb_cam_real_validation.py](/E:/codex/usb_cam_dev/test_usb_cam_real_validation.py)

## Real Validation Evidence

### Direct mode disk-floor AutoStop

Evidence summary:

- status: `passed`
- stop reason: `disk_low_space`
- stop detail:
  - `free_mb=328320.0 threshold=341000.0`

Primary record:

- [USB_CAM_AUTOSTOP_DISK_FLOOR_VALIDATION_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_AUTOSTOP_DISK_FLOOR_VALIDATION_2026-05-24.md)

Primary session:

- [direct_frames_disk_floor_validation_20260524_165804](/E:/codex/usb_cam_dev/_validation/auto_stop_real_runs/direct_frames_disk_floor_validation_20260524_165804)

### Video-then-frames disk-floor AutoStop

Evidence summary:

- status: `passed`
- stop reason: `disk_low_space`
- stop detail:
  - `free_mb=328297.8 threshold=341000.0`

Primary record:

- [USB_CAM_AUTOSTOP_DISK_FLOOR_VIDEO_THEN_FRAMES_VALIDATION_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_AUTOSTOP_DISK_FLOOR_VIDEO_THEN_FRAMES_VALIDATION_2026-05-24.md)

Primary session:

- [video_then_frames_disk_floor_validation_20260524_170358](/E:/codex/usb_cam_dev/_validation/auto_stop_real_runs/video_then_frames_disk_floor_validation_20260524_170358)

### Direct mode max-duration AutoStop

Evidence summary:

- status: `passed`
- stop reason: `max_duration`
- stop detail:
  - `elapsed=3.1s limit=3.0s`

Primary record:

- [USB_CAM_AUTOSTOP_MAX_DURATION_VALIDATION_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_AUTOSTOP_MAX_DURATION_VALIDATION_2026-05-24.md)

Primary session:

- [direct_frames_max_duration_validation_20260524_181235](/E:/codex/usb_cam_dev/_validation/max_duration_real_runs/direct_frames_max_duration_validation_20260524_181235)

### Direct mode FPS-ratio AutoStop

Evidence summary:

- status: `passed`
- stop reason: `fps_below_threshold`
- stop detail:
  - `fps=5.00 threshold=17.50`

Primary record:

- [USB_CAM_AUTOSTOP_FPS_RATIO_VALIDATION_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_AUTOSTOP_FPS_RATIO_VALIDATION_2026-05-24.md)

Primary session:

- [direct_frames_fps_ratio_validation_20260524_182216](/E:/codex/usb_cam_dev/_validation/fps_ratio_real_runs/direct_frames_fps_ratio_validation_20260524_182216)

## Important Operational Note

One real-world failure mode has already been observed:

- a leftover `ffmpeg` process can hold the camera device open
- that causes validation to fail before AutoStop logic even gets a chance to run

This is now a known class, not a mystery failure.

The helper has started to classify this path as:

- `failure_reason = camera_in_use`

The helper can also now surface this as a wrapper-level preflight result:

- `preflight_failed = true`
- `failure_reason = camera_in_use`
- `process_conflicts = [...]`

## Current Tested Baseline

Current automated baseline after the latest stability work:

- `pytest`: `56 passed`

That includes:

- [test_usb_cam_refactor.py](/E:/codex/usb_cam_dev/test_usb_cam_refactor.py)
- [test_usb_cam_real_validation.py](/E:/codex/usb_cam_dev/test_usb_cam_real_validation.py)

## What Is Still Open

The following items are still open and reasonable next steps:

1. `max_duration_s` policy evaluation
2. `video_then_frames` max-duration validation, if duration policy becomes more likely
3. Real degraded-condition evidence for `min_effective_fps_ratio`, if default enablement is ever considered
4. Optional packaged-app validation helper for the same failure-class reporting
5. Optional wider soak after any future default-threshold changes

## Recommended Next Step

The best next step is:

`Decide whether max_duration_s should remain opt-in or be promoted to a product requirement before enabling it by default.`

Reason:

- the first default rule is already active
- both modes already have real end-to-end evidence
- helper preflight is now clearer when the camera is already locked
- there is still no evidence that operators want a default recording cap
- but there is now real evidence that the `max_duration_s` mechanism itself works when explicitly enabled

## One-Line Summary

`By the end of 2026-05-24, usb_cam_dev has moved from packaged-recording closure to a real stability phase with active disk-floor AutoStop, health metrics, dedicated validation helpers, and real-camera evidence in both capture modes.`
