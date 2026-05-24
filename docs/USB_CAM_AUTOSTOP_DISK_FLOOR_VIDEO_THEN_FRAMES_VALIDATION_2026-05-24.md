# USB_CAM AutoStop Disk Floor Video-Then-Frames Validation 2026-05-24

## Goal

Validate that the disk-floor AutoStop path also works for the
`video_then_frames` mode in a real-device environment.

## Method

Validation used the dedicated repo-local helper mode:

```powershell
python usb_cam_real_validation.py --ffmpeg E:\codex\usb_cam_dev\tools\ffmpeg.exe --camera-name "imx678' UVC " --output-root E:\codex\usb_cam_dev\_validation\auto_stop_real_runs --disk-floor-override-mb 341000 --video-then-frames-disk-floor-autostop-only
```

Why this override was used:

- the production default remains `5 GB`
- the machine had much more than `5 GB` free
- a temporary override is the safest way to exercise the real stop path

## Environment

- Date: `2026-05-24`
- Camera: `imx678' UVC`
- Mode: `video_then_frames`
- FFmpeg: [tools/ffmpeg.exe](/E:/codex/usb_cam_dev/tools/ffmpeg.exe)
- Validation output root:
  - [auto_stop_real_runs](/E:/codex/usb_cam_dev/_validation/auto_stop_real_runs)

## Result

- Validation verdict: `passed`
- AutoStop triggered: `yes`
- Stop reason: `disk_low_space`
- Stop reason detail:
  - `free_mb=328297.8 threshold=341000.0`

Primary session evidence:

- [video_then_frames_disk_floor_validation_20260524_170358](/E:/codex/usb_cam_dev/_validation/auto_stop_real_runs/video_then_frames_disk_floor_validation_20260524_170358)

Key observed outputs:

- `metadata.json`: present
- `summary.txt`: present
- `frames.csv`: present
- video artifact: present
- extracted frames: `0`

## Interpretation

This result is still a successful disk-floor AutoStop validation.

Why:

- the stop happened during the recording stage
- `metadata.json` recorded:
  - `auto_stopped = true`
  - `stop_reason = disk_low_space`
  - `stop_reason_detail`
- an intermediate AVI file was created, which is expected for this mode

Zero extracted frames here is not a failure of the AutoStop path.
It simply reflects that the stop happened before the later extract stage.

## One-Line Conclusion

`The disk-floor AutoStop path has now been validated end-to-end for video_then_frames on 2026-05-24 using a real camera, real ffmpeg, a temporary override threshold, and recorded session artifacts.`
