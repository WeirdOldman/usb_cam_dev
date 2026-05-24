# USB_CAM AutoStop Max Duration Validation 2026-05-24

## Goal

Validate that the `max_duration_s` AutoStop path works in a real-device
environment for `direct_frames`, without changing the current default policy.

## Method

Validation used the dedicated repo-local helper mode:

```powershell
python usb_cam_real_validation.py --ffmpeg E:\codex\usb_cam_dev\tools\ffmpeg.exe --camera-name "imx678' UVC " --output-root E:\codex\usb_cam_dev\_validation\max_duration_real_runs --max-duration-s 3 --max-duration-autostop-only
```

Why this validation mode was used:

- the current product policy does not enable `max_duration_s` by default
- a small explicit value is the safest way to exercise the stop path
- this proves the capability without changing user-facing defaults

## Environment

- Date: `2026-05-24`
- Camera: `imx678' UVC`
- Mode: `direct_frames`
- FFmpeg: [tools/ffmpeg.exe](/E:/codex/usb_cam_dev/tools/ffmpeg.exe)
- Validation output root:
  - [max_duration_real_runs](/E:/codex/usb_cam_dev/_validation/max_duration_real_runs)

## Result

- Validation verdict: `passed`
- AutoStop triggered: `yes`
- Stop reason: `max_duration`
- Stop reason detail:
  - `elapsed=3.1s limit=3.0s`

Primary session evidence:

- [direct_frames_max_duration_validation_20260524_181235](/E:/codex/usb_cam_dev/_validation/max_duration_real_runs/direct_frames_max_duration_validation_20260524_181235)

Key observed outputs:

- `frame_count`: `78`
- `frames.csv`: present
- `summary.txt`: present
- `metadata.json`: present
- image output: present

## Interpretation

This validation proves that:

- the `max_duration_s` stop path works in a real-device run
- metadata persistence works:
  - `auto_stopped = true`
  - `stop_reason = max_duration`
  - `stop_reason_detail`
- current behavior can be exercised safely as an opt-in rule

It does **not** imply that `max_duration_s` should now be enabled by default.

## One-Line Conclusion

`The max-duration AutoStop path has now been validated end-to-end on 2026-05-24 for direct_frames using a real camera, real ffmpeg, and a small explicit duration limit.`
