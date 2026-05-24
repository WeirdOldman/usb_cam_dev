# USB_CAM Phase 4 RC Status 2026-05-24

## Scope

This document freezes the current release-candidate validation status after:

- packaged GUI startup closure
- packaged preview validation
- packaged `direct_frames` validation
- packaged `video_then_frames` validation
- stop-flow fix and re-validation
- Chinese/space-path validation
- short multi-run validation
- `5 min + 5 min` long-duration stability validation

## Candidate Build

- Build date: `2026-05-24`
- Commit: `8438c2c`
- Python: `3.11.9`
- PyInstaller: `6.19.0`
- Package type: `onedir`
- Main artifact:
  - [USB_Cam_4K25.exe](/E:/codex/usb_cam_dev/dist/USB_Cam_4K25/USB_Cam_4K25.exe)

## Verified Areas

### 1. Packaged startup and preview

- packaged app cold start: `passed`
- packaged GUI main window visible and responding: `passed`
- preview start: `passed`
- preview stop: `passed`

### 2. Short recording validation

- packaged `direct_frames` short recording: `passed`
- packaged `video_then_frames` short recording: `passed`
- packaged stop flow after stop-button fix: `passed`

Primary evidence:

- [USB_CAM_PHASE4_BUILD_RUN_2026-05-24_R1.md](/E:/codex/usb_cam_dev/docs/USB_CAM_PHASE4_BUILD_RUN_2026-05-24_R1.md)

### 3. Path compatibility

- output path with spaces: `passed`
- output path with Chinese characters: `passed`

Primary evidence:

- [gui_extended_validation.json](/E:/codex/usb_cam_dev/_validation/gui_extended_validation.json)

### 4. Short multi-run validation

- packaged default output round 1: `passed`
- packaged default output round 2: `passed`

Primary evidence:

- [gui_extended_validation.json](/E:/codex/usb_cam_dev/_validation/gui_extended_validation.json)

### 5. Long-duration stability

Primary evidence:

- [long_stability_5min.json](/E:/codex/usb_cam_dev/_validation/long_stability_5min.json)

#### direct_5min

- session:
  - [direct_frames_mjpeg_4k_20260524_120925](/E:/codex/usb_cam_dev/_validation/long_stability/direct_frames_mjpeg_4k_20260524_120925)
- target duration: `300s`
- scenario elapsed: `302.9s`
- capture duration by frames: `299.56s`
- frame count: `7489`
- exit codes:
  - `direct_frames = 0`
- stop-to-finish elapsed: `2.9s`
- result: `passed`

#### video_then_frames_5min

- session:
  - [video_then_frames_mjpeg_4k_20260524_121429](/E:/codex/usb_cam_dev/_validation/long_stability/video_then_frames_mjpeg_4k_20260524_121429)
- target duration: `300s`
- scenario elapsed: `313.5s`
- capture duration by frames: `299.64s`
- frame count: `7491`
- exit codes:
  - `record_video = 0`
  - `extract_frames_copy = 0`
- stop-to-finish elapsed: `13.5s`
- result: `passed`

## RC Conclusion

Current conclusion:

`This packaged Windows build is release-candidate ready for the currently validated scope.`

Meaning:

- packaged startup is closed
- packaged preview is closed
- packaged direct capture is closed
- packaged video-then-frames capture is closed
- packaged stop flow is closed
- path compatibility for Chinese/space output paths is closed
- short multi-run validation is closed
- 5-minute long-duration validation in both modes is closed

## Remaining Non-Blocking Checks

1. Read-only / non-writable output directory UX re-check
2. Optional wider operator checklist replay by a human tester
3. Optional larger-duration soak if product policy requires it

## Release Position

- RC status: `ready`
- Distribution recommendation: `allowed for current validated scope`
