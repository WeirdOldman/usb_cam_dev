# USB_CAM Phase 4 Current Status Note

## Current facts

As of `2026-05-24`, the Windows packaging and packaged-app validation status is:

- `build.bat` now completes successfully on this machine
- `dist/USB_Cam_4K25/` is generated successfully
- packaged `USB_Cam_4K25.exe` cold start is verified
- bundled `tools/ffmpeg.exe` discovery is verified
- packaged GUI preview start/stop is verified
- packaged `direct_frames` short real-device recording is verified
- packaged `video_then_frames` short real-device recording is verified
- packaged stop flow is verified after the `self.proc` timing fix
- output artifacts are verified:
  - images
  - `frames.csv`
  - `summary.txt`
  - `metadata.json`
- path compatibility is verified for:
  - output path containing spaces
  - output path containing Chinese characters
- short multi-run packaged validation is verified

Related evidence:

- build/run record:
  - [USB_CAM_PHASE4_BUILD_RUN_2026-05-24_R1.md](/E:/codex/usb_cam_dev/docs/USB_CAM_PHASE4_BUILD_RUN_2026-05-24_R1.md)
- extended GUI validation:
  - [gui_extended_validation.json](/E:/codex/usb_cam_dev/_validation/gui_extended_validation.json)

## Current conclusion

The previous statement that “real Windows packaged recording validation is still incomplete” is no longer accurate.

The current accurate status is:

`Windows packaged GUI startup, preview, direct capture, video-then-frames capture, stop flow, bundled FFmpeg discovery, Chinese path, space path, and short multi-run validation have all been completed successfully on 2026-05-24.`

## What is still not closed

The remaining unclosed items are no longer core packaging blockers. They are follow-up quality checks:

1. Read-only / non-writable output directory UX re-check
2. Optional wider operator checklist replay by a human tester
3. Optional larger-duration soak if product policy requires it

## New status after long-duration validation

As of `2026-05-24`, an additional long-duration validation has also been completed:

- `direct_frames` packaged long run: `5 min passed`
- `video_then_frames` packaged long run: `5 min passed`

Primary evidence:

- [long_stability_5min.json](/E:/codex/usb_cam_dev/_validation/long_stability_5min.json)
- [USB_CAM_PHASE4_RC_STATUS_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_PHASE4_RC_STATUS_2026-05-24.md)
