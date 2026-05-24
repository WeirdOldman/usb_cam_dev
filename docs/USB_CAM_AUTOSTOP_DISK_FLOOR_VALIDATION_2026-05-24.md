# USB_CAM AutoStop Disk Floor Validation 2026-05-24

## Goal

Validate that the newly enabled default disk-floor AutoStop mechanism can be
triggered safely in a real environment without actually reducing the machine to
 the production default `5 GB` free-space level.

## Method

Validation used the repo-local real-device helper with a temporary override:

```powershell
python usb_cam_real_validation.py --ffmpeg E:\codex\usb_cam_dev\tools\ffmpeg.exe --camera-name "imx678' UVC " --output-root E:\codex\usb_cam_dev\_validation\auto_stop_real_runs --disk-floor-override-mb 341000 --disk-floor-autostop-only
```

Why this override was used:

- the current machine had much more than `5 GB` free
- reducing the disk to `5 GB` free for validation was unnecessary and unsafe
- the override exercises the same AutoStop path while preserving the production default

## Environment

- Date: `2026-05-24`
- Camera: `imx678' UVC`
- FFmpeg: [tools/ffmpeg.exe](/E:/codex/usb_cam_dev/tools/ffmpeg.exe)
- Validation output root:
  - [auto_stop_real_runs](/E:/codex/usb_cam_dev/_validation/auto_stop_real_runs)

## Result

- Validation verdict: `passed`
- AutoStop triggered: `yes`
- Stop reason: `disk_low_space`
- Stop reason detail:
  - `free_mb=328320.0 threshold=341000.0`

Primary session evidence:

- [direct_frames_disk_floor_validation_20260524_165804](/E:/codex/usb_cam_dev/_validation/auto_stop_real_runs/direct_frames_disk_floor_validation_20260524_165804)

Key observed outputs:

- `frame_count`: `26`
- `frames.csv`: present
- `summary.txt`: present
- `metadata.json`: present
- image output: present

## Notes

- One earlier attempt failed because a leftover `ffmpeg` process was still holding the camera device.
- After terminating the leftover process and re-running, the AutoStop validation passed cleanly.
- This validation proves the disk-floor AutoStop path in a real-device environment.
- It does **not** change the production default threshold, which remains `5 GB`.

## One-Line Conclusion

`The disk-floor AutoStop path has now been validated end-to-end on 2026-05-24 using a real camera, real ffmpeg, a temporary override threshold, and recorded session artifacts.`
