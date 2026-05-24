# USB_CAM Stability Policy

## Scope

This document defines the current stability-hardening policy for `usb_cam_dev`
after the `2026-05-24` packaged Windows validation closure.

It does **not** change the core product direction:

- Tkinter UI stays
- FFmpeg DirectShow capture stays
- PyInstaller `--onedir` stays
- `direct_frames` and `video_then_frames` both stay

Its purpose is to explain how the project now thinks about:

- capture health
- safety stop policies
- long-duration recording risk
- when to re-run packaged/manual stability verification

## Current Validated Baseline

As of `2026-05-24`, the validated packaged scope includes:

- packaged GUI startup
- packaged preview start/stop
- packaged `direct_frames`
- packaged `video_then_frames`
- packaged stop-flow closure
- Chinese / space-path compatibility
- short multi-run replay
- `5 min + 5 min` long-duration validation

Primary evidence:

- [USB_CAM_PHASE4_CURRENT_STATUS_NOTE.md](/E:/codex/usb_cam_dev/docs/USB_CAM_PHASE4_CURRENT_STATUS_NOTE.md)
- [USB_CAM_PHASE4_BUILD_RUN_2026-05-24_R1.md](/E:/codex/usb_cam_dev/docs/USB_CAM_PHASE4_BUILD_RUN_2026-05-24_R1.md)
- [USB_CAM_PHASE4_RC_STATUS_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_PHASE4_RC_STATUS_2026-05-24.md)

This means the next phase is no longer “prove it records at all.”
It is “make long-running capture safer and easier to trust.”

## Capture Health Terms

The current runtime health model is intentionally small and conservative.

### Health fields

- `write_rate_mb_s`
  - Current observed session write speed in MB/s.
- `estimated_time_left_s`
  - Estimated remaining duration based on current image-space rate and free disk.
- `estimated_time_left_text`
  - Human-readable rendering of the same estimate.
- `capture_health`
  - One of:
    - `ok`
    - `warning`
    - `unknown`
- `capture_health_reason`
  - Current reasons:
    - `stable`
    - `disk_low_space`
    - `fps_below_threshold`
    - `insufficient_data`

### Current interpretation

- `ok`
  - Enough runtime evidence exists and no current warning rule is hit.
- `warning`
  - A known risk threshold is currently violated.
- `unknown`
  - The session has not yet produced enough evidence to classify confidently.

## AutoStop Policy

### Why AutoStop exists

The goal of AutoStop is not to be “smart.”
The goal is to prevent a long-running session from continuing blindly once a
clear safety threshold is crossed.

### Current implementation status

The AutoStop framework is now present in code:

- decision helper:
  - [usb_cam_stop_prefs.py](/E:/codex/usb_cam_dev/usb_cam_stop_prefs.py)
- timer integration:
  - [usb_cam_capture_helpers.py](/E:/codex/usb_cam_dev/usb_cam_capture_helpers.py)
  - [usb_burst_cam_4k25_manual_v1_6_3.py](/E:/codex/usb_cam_dev/usb_burst_cam_4k25_manual_v1_6_3.py)
- metadata persistence:
  - [usb_cam_runtime.py](/E:/codex/usb_cam_dev/usb_cam_runtime.py)
  - [usb_cam_session_finalize.py](/E:/codex/usb_cam_dev/usb_cam_session_finalize.py)

Session metadata now reserves:

- `auto_stopped`
- `stop_reason`
- `stop_reason_detail`

### Current supported rule types

- `max_duration_s`
- `min_disk_free_mb_hard`
- `min_effective_fps_ratio`

### Current default behavior

Important:

**The AutoStop framework is wired in, and the first conservative default rule is now active.**

Current default timer wiring passes:

- `enabled = True`
- `max_duration_s = None`
- `min_disk_free_mb_hard = 5120.0`
- `min_effective_fps_ratio = None`

That means:

- the decision path is exercised
- metadata/log plumbing is exercised
- a hard disk-floor stop is now active by default
- duration and FPS-based auto-stop are still disabled by default

This is deliberate.

## Policy for Enabling Real AutoStop Thresholds

Before any additional threshold becomes active by default, it should satisfy all of these:

1. It is simple enough to explain in one sentence.
2. It is unlikely to fire during a currently validated normal session.
3. It fails safe rather than fail noisy.
4. It has a regression test.
5. It has at least one targeted packaged/manual replay after activation.

### Practical validation note

The default hard disk floor is now `5 GB`.

In many development environments, there is no safe or convenient way to
actually push the system disk down to `5 GB` free just to validate the rule.

For validation, the app now supports a temporary environment override:

- environment variable:
  - `USB_CAM_AUTOSTOP_DISK_MB`

Example validation approach:

1. launch the app from a terminal with:
   - `set USB_CAM_AUTOSTOP_DISK_MB=128`
   - or run the repo helper directly:
     - `python usb_cam_real_validation.py --ffmpeg dist/USB_Cam_4K25/tools/ffmpeg.exe --disk-floor-override-mb 128 --disk-floor-autostop-only`
2. choose an output directory on a disk whose free space is comfortably above
   the real default but below the temporary override, or use a temporary value
   that your machine can safely cross during a short validation setup
3. start a short capture
4. confirm:
   - auto-stop triggers
   - `run_log.txt` contains `[auto-stop] ...`
   - `metadata.json` contains:
     - `auto_stopped = true`
     - `stop_reason = disk_low_space`
     - `stop_reason_detail`

This override is intended for validation only.
It is not meant to replace the production default.

### Preflight conflict behavior

The real-validation helper now performs a lightweight preflight before the
dedicated disk-floor AutoStop runs.

Current preflight behavior:

- if likely capture-related processes are already running, the helper can
  return early instead of blindly starting ffmpeg
- current conflict candidates include:
  - `ffmpeg.exe`
  - `USB_Cam_4K25.exe`

In that case, validation can return:

- `ok = false`
- `preflight_failed = true`
- `failure_reason = camera_in_use`
- `process_conflicts = [...]`

This is intentionally conservative.
It is better to fail clearly before capture starts than to misread a device-lock
problem as an AutoStop or capture regression.

### Recommended activation order

1. Hard disk floor
   - status: active by default
2. Max duration
3. FPS degradation threshold

Reason:

- disk floor is the least ambiguous safety signal
- max duration is deterministic and easy to explain
- FPS degradation is the noisiest and most environment-sensitive signal

### Current decision on max duration

Current decision:

- `max_duration_s` support exists
- `max_duration_s` can be enabled deliberately through environment override
- `max_duration_s` is **not** enabled by default yet
- a dedicated real-device validation path now exists for `direct_frames`

Reason:

- current packaged evidence proves stable operation for `5 min + 5 min`
- there is no product requirement yet that says sessions must be capped by default
- turning on a default duration cap without a product rule would risk surprising operators during legitimate long captures

Primary evidence:

- [USB_CAM_AUTOSTOP_MAX_DURATION_VALIDATION_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_AUTOSTOP_MAX_DURATION_VALIDATION_2026-05-24.md)

### Current decision on FPS-based stopping

Current decision:

- `min_effective_fps_ratio` support exists
- a dedicated real-device helper path now exists for `direct_frames`
- `min_effective_fps_ratio` is **not** enabled by default yet

Reason:

- the current validation proves helper-path correctness, not a naturally observed field degradation event
- FPS-based stopping has the highest false-positive risk of the three major stop rules
- default enablement would require stronger confidence in how real degraded capture conditions are measured

Primary evidence:

- [USB_CAM_AUTOSTOP_FPS_RATIO_VALIDATION_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_AUTOSTOP_FPS_RATIO_VALIDATION_2026-05-24.md)

## Segment Strategy Boundary

Long-duration safety and segmented recording are related, but they are not the
same problem.

Current policy:

- segment support is a future hardening track
- it must not be mixed into current validated defaults casually
- the first safe version should be:
  - optional
  - `video_then_frames` only
  - single output directory
  - deterministic naming

This project is **not** trying to reproduce VirtualDub2’s full spill-drive
system right now.

## When to Re-Run Stability Verification

Any of these changes should trigger at least targeted replay:

- stop-flow behavior changes
- metadata stop-reason contract changes
- disk warning or disk stop logic changes
- health metric formulas change
- preview/capture timing behavior changes
- `video_then_frames` output semantics change

### Minimum replay after such a change

- one short `direct_frames`
- one short `video_then_frames`
- one stop-flow check

### Stronger replay needed when defaults change

If a default AutoStop threshold is turned on or materially changed, also run:

- one packaged/manual replay that intentionally crosses that threshold
- one normal replay proving the threshold does not trigger too early

### Optional soak

Run a longer soak when:

- long-duration logic changed
- threshold defaults changed
- product policy requires stronger release confidence

## Practical Rule

When in doubt:

- prefer better observation first
- then add explicit safety stops
- only then consider more complex storage strategy changes

## One-Line Policy

**The current stability strategy is: preserve the validated `v1.6.4` capture path, improve observability, and only enable automatic stopping rules when they are proven safer than continuing silently.**
