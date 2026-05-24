# USB_CAM Phase 4 Build Run 2026-05-24 R1

## 1. Build Batch Info

- Build round: `R1`
- Build date: `2026-05-24`
- Builder: `Codex`
- Build machine: `DESKTOP-2AAPSKB`
- Windows version: `Microsoft Windows NT 10.0.26100.0`
- Python version: `3.11.9`
- PyInstaller version: `6.19.0`
- Packaging mode: `onedir`
- Current goal: `Windows packaged GUI validation and real-device recording closure`
- Git commit: `8438c2c`

## 2. Input Baseline

- `build.bat` exists
- Entry script confirmed: `usb_burst_cam_4k25_manual_v1_6_3.py`
- `pytest -q test_usb_cam_refactor.py test_usb_cam_real_validation.py`: `35 passed`
- `py_compile` passed
- Current repo-local validation helper added:
  - `usb_cam_real_validation.py`
  - `test_usb_cam_real_validation.py`

## 3. Build Execution

- Command:

```powershell
.\build.bat
```

- Result: `passed`
- Key outcome:
  - `dist/USB_Cam_4K25/` generated
  - `_tkinter.pyd`, `tcl86t.dll`, `tk86t.dll`, `_tcl_data`, `_tk_data` included
  - `tools/ffmpeg.exe` copied into package after build

## 4. Packaged App Startup Validation

- Cold start of `dist/USB_Cam_4K25/USB_Cam_4K25.exe`: `passed`
- Main window title observed:
  - `USB 摄像头 4K25 手动连拍 - v1.6.3`
- Packaged GUI remained alive and responding after startup check

## 5. FFmpeg Validation

- Strategy: bundled `tools/ffmpeg.exe`
- Bundled FFmpeg path:
  - `dist/USB_Cam_4K25/tools/ffmpeg.exe`
- App FFmpeg discovery: `passed`

## 6. Functional Validation

### 6.1 Preview

- Manual preview start: `passed`
- Manual preview stop: `passed`

### 6.2 Direct Mode

- Manual run before stop fix:
  - session: [direct_frames_mjpeg_4k_20260524_025328](/E:/codex/usb_cam_dev/dist/USB_Cam_4K25/capture_output/direct_frames_mjpeg_4k_20260524_025328)
  - result: `failed`
  - symptom: stop clicked, recording kept running
  - evidence: `direct_frames` exit code `3221225786`

- Manual run after stop fix:
  - session: [direct_frames_mjpeg_4k_20260524_031317](/E:/codex/usb_cam_dev/dist/USB_Cam_4K25/capture_output/direct_frames_mjpeg_4k_20260524_031317)
  - result: `passed`
  - exit code: `0`
  - frame count: `91`
  - total process duration: `5.354s`
  - capture duration by frames: `3.640s`

### 6.3 Video-Then-Frames Mode

- Manual run before stop fix:
  - session: [video_then_frames_mjpeg_4k_20260524_025411](/E:/codex/usb_cam_dev/dist/USB_Cam_4K25/capture_output/video_then_frames_mjpeg_4k_20260524_025411)
  - result: `failed`
  - symptom: stop clicked, recording kept running
  - evidence:
    - `record_video` exit code `3221225786`
    - `extract_frames_copy` exit code `0`

- Manual run after stop fix:
  - session: [video_then_frames_mjpeg_4k_20260524_031327](/E:/codex/usb_cam_dev/dist/USB_Cam_4K25/capture_output/video_then_frames_mjpeg_4k_20260524_031327)
  - result: `passed`
  - exit codes:
    - `record_video = 0`
    - `extract_frames_copy = 0`
  - frame count: `103`
  - total process duration: `5.698s`
  - capture duration by frames: `4.120s`

## 7. Output Artifacts

- `frames.csv`: present
- `summary.txt`: present
- `metadata.json`: present
- image output: present
- video artifact in `video_then_frames`: present

## 8. Path Boundary Validation

Evidence source: [gui_extended_validation.json](/E:/codex/usb_cam_dev/_validation/gui_extended_validation.json)

- Space path:
  - session: [direct_frames_mjpeg_4k_20260524_115534](/E:/codex/usb_cam_dev/_validation/空格%20路径/direct_frames_mjpeg_4k_20260524_115534)
  - result: `passed`
  - exit code: `0`
  - frame count: `38`

- Chinese path:
  - session: [video_then_frames_mjpeg_4k_20260524_115538](/E:/codex/usb_cam_dev/_validation/中文路径/video_then_frames_mjpeg_4k_20260524_115538)
  - result: `passed`
  - exit codes:
    - `record_video = 0`
    - `extract_frames_copy = 0`
  - frame count: `51`

## 9. Multi-Run Stability

Evidence source: [gui_extended_validation.json](/E:/codex/usb_cam_dev/_validation/gui_extended_validation.json)

- Round 1 default output:
  - session: [direct_frames_mjpeg_4k_20260524_115542](/E:/codex/usb_cam_dev/dist/USB_Cam_4K25/capture_output/direct_frames_mjpeg_4k_20260524_115542)
  - result: `passed`
  - exit code: `0`

- Round 2 default output:
  - session: [video_then_frames_mjpeg_4k_20260524_115545](/E:/codex/usb_cam_dev/dist/USB_Cam_4K25/capture_output/video_then_frames_mjpeg_4k_20260524_115545)
  - result: `passed`
  - exit codes:
    - `record_video = 0`
    - `extract_frames_copy = 0`

## 10. Issues Found

### Blocking issues fixed in this round

1. Packaged app stop button could not stop capture because `self.proc` was not assigned until FFmpeg had already exited.
2. `build.bat` Python detection relied on `where python`, which failed in this Windows environment.

### Non-blocking remaining items

1. Long-duration stability has not yet been validated.
2. Read-only output directory UX has not yet been re-checked after packaged flow closure.

## 11. Conclusion

- Verdict: `passed`
- Distribution permission: `yes, for current short-run packaged validation scope`

One-line summary:

`Windows packaged GUI startup, preview, direct capture, video-then-frames capture, stop flow, bundled FFmpeg discovery, Chinese path, space path, and multi-run short-session validation all passed on 2026-05-24.`

## 12. Next Step

- Recommended next step:
  - run one longer stability session (`5-10 min`) in both modes
  - re-check read-only path error handling
  - then freeze a release candidate record
