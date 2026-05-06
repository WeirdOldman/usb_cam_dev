# USB_CAM Phase 3 Task 1 Coverage Gap Audit

## Audit scope
- Test file inspected: `test_usb_cam_refactor.py`
- Modules inspected:
  - `usb_cam_paths.py`
  - `usb_cam_session_writer.py`
  - `usb_cam_stats.py`
  - `usb_cam_ffmpeg.py`
  - `usb_cam_preview.py`
  - `usb_cam_capture.py`
  - `usb_cam_process.py`
  - `usb_cam_runtime.py`
  - `usb_cam_ui_state.py`
  - `usb_cam_finalize.py`
  - `usb_cam_session_finalize.py`

## Current covered behaviors

### Covered now
- Main-module compatibility export: `sanitize_windows_filename`
- `find_ffmpeg()` happy path via local `tools/ffmpeg.exe`
- `frame_metrics()` normal-value summary math
- `preview_cmd()` expected preview arguments
- `find_png_end()` + `read_preview_frames()` basic PNG frame extraction
- capture command builders basic shape
- `parse_ffmpeg_progress_line()` basic `frame=` and `out_time_ms=` parsing
- `build_capture_meta()` baseline metadata shape
- `run_capture_pipeline()` direct mode happy path
- `update_capture_metrics()` basic display/fps text behavior
- `process_ui_message()` basic ffmpeg/preview dispatch behavior
- `finalize_capture_done_state()` empty-path case
- `finalize_session()` minimal one-frame success case

## Coverage gaps by module

### 1. `usb_cam_paths.py`
**Covered:**
- `find_ffmpeg()` local bundled binary path
- `sanitize_windows_filename()` basic cleanup and default fallback

**Missing:**
- `candidate_base_dirs()` uniqueness/order contract
- `find_ffmpeg(user_value=...)` explicit user path override
- `find_ffmpeg()` PATH fallback via `shutil.which`
- `safe_image_prefix()` empty / invalid-char behavior
- `sanitize_windows_filename()` trailing dot/space edge preservation contract beyond current two tests

**Priority:** High
**Reason:** pure logic, tiny tests, high stability value

---

### 2. `usb_cam_session_writer.py`
**Covered:**
- indirect coverage via `finalize_session()`

**Missing:**
- `now_str(clock)` deterministic formatting
- `make_session()` directory creation contract
- `count_frame_files()` sorting behavior
- `write_frames_csv()` header and row content
- `write_metadata()` actual JSON content
- `write_summary()` critical human-readable fields

**Priority:** High
**Reason:** this module defines the artifact contract users actually inspect

---

### 3. `usb_cam_stats.py`
**Covered:**
- `frame_metrics()` nominal values

**Missing:**
- `folder_size()` nested files and missing path behavior
- `bytes_to_mb()` zero / small-value behavior
- `frame_metrics()` zero-frame and zero-duration edge cases

**Priority:** High
**Reason:** pure logic and directly tied to displayed/exported stats

---

### 4. `usb_cam_ffmpeg.py`
**Covered:**
- `preview_cmd()` basic pipe-preview arguments

**Missing:**
- `quote_cmd()` quoting behavior for spaced vs unspaced args
- `record_direct_frames_cmd()` exact output shape
- `record_video_cmd()` exact output shape

**Priority:** Medium
**Reason:** low complexity, useful as command-contract guardrails

---

### 5. `usb_cam_preview.py`
**Covered:**
- `find_png_end()` basic success case
- `read_preview_frames()` split-chunk PNG reassembly

**Missing:**
- `build_preview_cmd()` wrapper contract
- `find_png_end()` incomplete/truncated PNG returns `None`
- `read_preview_frames()` no-PNG noise-only behavior
- `stop_preview_process()` graceful stop / terminate fallback behavior

**Priority:** Medium
**Reason:** logic is isolated but process interactions need light fakes

---

### 6. `usb_cam_capture.py`
**Covered:**
- `build_direct_cmd()` / `build_record_cmd()` / `build_extract_cmd()` basic shape

**Missing:**
- `base_input_args()` exact shared input contract
- `image_output_args()` copy vs q2 branches
- `ffmpeg_progress_args()` exact progress prefix contract
- `build_extract_cmd(fallback_q2=True)` branch

**Priority:** High
**Reason:** pure builders, easy wins, directly protect capture pipeline assumptions

---

### 7. `usb_cam_process.py`
**Covered:**
- `parse_ffmpeg_progress_line()` basic recognized lines

**Missing:**
- malformed numeric lines
- duplicate/odd frame line variants
- `request_stop_process()` stdin-write success path
- `request_stop_process()` terminate fallback path
- `run_ffmpeg_process()` frame callback/log callback integration with fake proc

**Priority:** Medium-High
**Reason:** very relevant to runtime correctness, but tests require lightweight monkeypatch/fake proc

---

### 8. `usb_cam_runtime.py`
**Covered:**
- `build_capture_meta()` baseline structure
- `run_capture_pipeline()` direct mode success path

**Missing:**
- video-then-frames happy path
- extract fallback-to-q2 branch when copy extraction yields zero frames
- delete-video-after-extract branch
- video delete error capture branch
- `build_capture_meta()` boolean/path detail fields beyond baseline

**Priority:** Highest
**Reason:** this is the main orchestration contract and currently only one mode is guarded

---

### 9. `usb_cam_ui_state.py`
**Covered:**
- one nominal metric update pass
- `ffmpeg_frame` and `preview_status` dispatch behavior

**Missing:**
- frame-scan refresh branch
- session-size refresh branch
- estimate text branches (`录制中...` / `约 0 MB/分钟`)
- `preview_frame` / `preview_stopped` / `capture_done` action returns
- invalid `ffmpeg_frame` data handling

**Priority:** Medium
**Reason:** still pure and easy, but lower business risk than runtime/session contracts

---

### 10. `usb_cam_finalize.py`
**Covered:**
- empty-path case

**Missing:**
- populated frames/session directories
- frame count text contract
- used-size text formatting
- partial case: only frames or only session exists

**Priority:** High
**Reason:** end-state UI values are user-visible and cheap to test

---

### 11. `usb_cam_session_finalize.py`
**Covered:**
- minimal one-frame success case

**Missing:**
- zero-frame case
- session size fields actually written to `current_meta`
- metadata/summary rewrite side effects
- `manual_stop_time` presence
- `frame_metrics()` integration details reflected in resulting meta

**Priority:** High
**Reason:** artifact finalization is critical and currently only lightly guarded

## Highest-value next tests to write

### Batch A — do next
1. `usb_cam_runtime.py`
   - video-then-frames happy path
   - q2 fallback branch
   - delete-video-after-extract branch

2. `usb_cam_session_writer.py`
   - `write_frames_csv()` output contract
   - `write_summary()` key text contract
   - `count_frame_files()` sorting

3. `usb_cam_finalize.py`
   - populated directory case
   - partial frames/session cases

### Batch B — immediately after
4. `usb_cam_capture.py`
   - `fallback_q2=True`
   - `image_output_args()` branches
   - `ffmpeg_progress_args()` prefix

5. `usb_cam_stats.py`
   - zero-frame / zero-duration paths
   - `folder_size()` nested sum

### Batch C — after that
6. `usb_cam_process.py`
   - `request_stop_process()` branches
   - fake-proc `run_ffmpeg_process()` callback behavior

7. `usb_cam_ui_state.py`
   - remaining text/action branches

## Recommended next move
Start Phase 3 Task 2 from the **highest-value slice**, not by spreading effort thin.

Best next slice:
- add tests for `usb_cam_runtime.py` non-direct branches first
- then move to `usb_cam_session_writer.py` artifact contract tests

## One-line conclusion
Current tests are good as a refactor safety net, but the biggest uncovered area is still **runtime orchestration + output artifact contract**.
