# USB Camera Refactor Structure

## Current entrypoint
- Main UI shell: `usb_burst_cam_4k25_manual_v1_6_3.py`
- Test file: `test_usb_cam_refactor.py`

## Refactored support modules

### 1. `usb_cam_paths.py`
Responsible for path and filename helpers.
- `app_base_dir`
- `candidate_base_dirs`
- `find_ffmpeg`
- `safe_image_prefix`
- `sanitize_windows_filename`

### 2. `usb_cam_session_writer.py`
Responsible for writing session artifacts.
- `make_session`
- `count_frame_files`
- `write_frames_csv`
- `write_metadata`
- `write_summary`

### 3. `usb_cam_stats.py`
Responsible for size/fps/statistics helpers.
- `folder_size`
- `bytes_to_mb`
- `frame_metrics`

### 4. `usb_cam_ffmpeg.py`
Responsible for shared FFmpeg command formatting helpers.
- `quote_cmd`
- `preview_cmd`
- `record_direct_frames_cmd`
- `record_video_cmd`

### 5. `usb_cam_preview.py`
Responsible for preview command building and preview process/frame handling.
- `build_preview_cmd`
- `find_png_end`
- `read_preview_frames`
- `start_preview_process`
- `stop_preview_process`

### 6. `usb_cam_capture.py`
Responsible for capture/extract command construction.
- `base_input_args`
- `image_output_args`
- `ffmpeg_progress_args`
- `build_direct_cmd`
- `build_record_cmd`
- `build_extract_cmd`

### 7. `usb_cam_process.py`
Responsible for FFmpeg process execution and stop behavior.
- `parse_ffmpeg_progress_line`
- `run_ffmpeg_process`
- `request_stop_process`

### 8. `usb_cam_runtime.py`
Responsible for runtime capture orchestration.
- `build_capture_meta`
- `run_capture_pipeline`

### 9. `usb_cam_ui_state.py`
Responsible for UI-facing metric calculation and queue action dispatch.
- `update_capture_metrics`
- `process_ui_message`

### 10. `usb_cam_finalize.py`
Responsible for `capture_done` final counters/state refresh.
- `finalize_capture_done_state`

### 11. `usb_cam_session_finalize.py`
Responsible for end-of-session artifact finalization.
- `finalize_session`

## Main file remaining responsibilities
`usb_burst_cam_4k25_manual_v1_6_3.py` should now mainly hold:
- Tkinter widget creation and layout
- button/event entrypoints
- thin wrappers that collect UI state and delegate to support modules
- log writer lifecycle
- OS integration helpers like open-folder / close-window behavior

## Practical boundary rule
When adding new behavior, prefer this order:
1. pure helper logic goes into a support module
2. UI shell gathers values and calls that helper
3. tests target the helper/module first, then verify main-file adoption

## Status snapshot
- Refactor direction kept: **Tkinter + FFmpeg**
- No PySide6 migration in this phase
- Current verification baseline: `12 passed` in `test_usb_cam_refactor.py`
