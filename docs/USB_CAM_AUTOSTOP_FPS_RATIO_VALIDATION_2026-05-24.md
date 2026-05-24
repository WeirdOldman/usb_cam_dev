# USB_CAM AutoStop FPS Ratio Validation 2026-05-24

## Goal

Validate that the `min_effective_fps_ratio` AutoStop path works through the
real validation helper in a real-device environment for `direct_frames`.

## Important Scope Note

This validation proves the helper path and metadata/log contract for the
FPS-based stop rule.

It does **not** prove that a natural real-world FPS degradation event was
observed on this machine.

The current helper intentionally injects a low effective FPS condition so the
rule can be exercised deterministically without waiting for a real performance
collapse.

## Method

Validation used the dedicated repo-local helper mode:

```powershell
python usb_cam_real_validation.py --ffmpeg E:\codex\usb_cam_dev\tools\ffmpeg.exe --camera-name "imx678' UVC " --output-root E:\codex\usb_cam_dev\_validation\fps_ratio_real_runs --min-effective-fps-ratio 0.7 --fps-ratio-autostop-only
```

## Environment

- Date: `2026-05-24`
- Camera: `imx678' UVC`
- Mode: `direct_frames`
- FFmpeg: [tools/ffmpeg.exe](/E:/codex/usb_cam_dev/tools/ffmpeg.exe)
- Validation output root:
  - [fps_ratio_real_runs](/E:/codex/usb_cam_dev/_validation/fps_ratio_real_runs)

## Result

- Validation verdict: `passed`
- AutoStop triggered: `yes`
- Stop reason: `fps_below_threshold`
- Stop reason detail:
  - `fps=5.00 threshold=17.50`

Primary session evidence:

- [direct_frames_fps_ratio_validation_20260524_182216](/E:/codex/usb_cam_dev/_validation/fps_ratio_real_runs/direct_frames_fps_ratio_validation_20260524_182216)

Key observed outputs:

- `frame_count`: `26`
- `frames.csv`: present
- `summary.txt`: present
- `metadata.json`: present
- image output: present

## Interpretation

This result proves:

- the FPS-based AutoStop path is wired correctly through the helper
- metadata persistence works:
  - `auto_stopped = true`
  - `stop_reason = fps_below_threshold`
  - `stop_reason_detail`
- the rule can be exercised safely as an explicit validation path

This result alone does **not** justify enabling the FPS-based rule by default.

That later decision still depends on product tolerance for false positives and
the ability to measure real degraded capture conditions robustly.

## One-Line Conclusion

`The FPS-based AutoStop helper path has now been validated end-to-end on 2026-05-24 for direct_frames using a real camera, real ffmpeg, and a deterministic low-FPS trigger condition.`
