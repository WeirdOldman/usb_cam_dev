# USB_CAM Stability Optimization Plan

**Goal:** 在 `v1.6.4` / `2026-05-24` 已完成真实 Windows 打包录制闭环的基线之上，为 `usb_cam_dev` 增加下一轮稳定性护栏，重点提升长时间采集的可观测性、自动停机安全性和长录制磁盘韧性，而不改变当前 `Tkinter + FFmpeg + PyInstaller --onedir` 主线。

**Architecture:** 保持现有主入口 `usb_burst_cam_4k25_manual_v1_6_3.py` 与已拆分模块结构不变。优先沿当前边界扩展：

- `usb_cam_capture_state.py` 维护运行期缓存与状态快照
- `usb_cam_ui_state.py` 负责指标计算与 UI-facing 文案
- `usb_cam_capture_helpers.py` / `usb_cam_runtime.py` 负责采集编排与 stop policy
- `test_usb_cam_refactor.py` 继续承担纯 Python 基线保护

本轮不引入新的桌面框架，不改采集主路线，不重写为音视频同步系统，只做“产品级稳定性增强”。

**Tech Stack:** Python 3.11, Tkinter, FFmpeg DirectShow, pytest, PyInstaller `--onedir`, Windows packaged validation baseline

**Baseline / Authority Refs:**

- [docs/USB_CAM_PHASE4_CURRENT_STATUS_NOTE.md](/E:/codex/usb_cam_dev/docs/USB_CAM_PHASE4_CURRENT_STATUS_NOTE.md)
- [docs/USB_CAM_PHASE4_BUILD_RUN_2026-05-24_R1.md](/E:/codex/usb_cam_dev/docs/USB_CAM_PHASE4_BUILD_RUN_2026-05-24_R1.md)
- [docs/USB_CAM_PHASE4_RC_STATUS_2026-05-24.md](/E:/codex/usb_cam_dev/docs/USB_CAM_PHASE4_RC_STATUS_2026-05-24.md)
- [usb_cam_capture_state.py](/E:/codex/usb_cam_dev/usb_cam_capture_state.py)
- [usb_cam_ui_state.py](/E:/codex/usb_cam_dev/usb_cam_ui_state.py)
- [usb_cam_capture_helpers.py](/E:/codex/usb_cam_dev/usb_cam_capture_helpers.py)
- [usb_cam_runtime.py](/E:/codex/usb_cam_dev/usb_cam_runtime.py)
- [usb_cam_real_validation.py](/E:/codex/usb_cam_dev/usb_cam_real_validation.py)

**Compatibility Boundary:**

- 保持现有两种工作模式：
  - `direct_frames`
  - `video_then_frames`
- 保持现有 session 目录与产物契约：
  - `frames/`
  - `video/`
  - `frames.csv`
  - `metadata.json`
  - `summary.txt`
  - `run_log.txt`
- 保持现有 `build.bat`、`USB_Cam_4K25.exe`、`tools/ffmpeg.exe` 路径策略不变
- 所有新增稳定性功能都必须默认“保守、不破坏当前通过的验收路径”
- 若新增配置项，必须提供安全默认值，保证现有手工操作不需要立刻学习新流程

**Verification:**

- `python -m pytest -q test_usb_cam_refactor.py test_usb_cam_real_validation.py`
- `python -m py_compile usb_burst_cam_4k25_manual_v1_6_3.py usb_cam_capture_helpers.py usb_cam_preview_helpers.py usb_cam_queue_helpers.py usb_cam_capture_state.py usb_cam_capture_context.py usb_cam_ui_state.py usb_cam_finalize.py usb_cam_session_finalize.py usb_cam_runtime.py usb_cam_process.py usb_cam_capture.py usb_cam_preview.py usb_cam_ffmpeg.py usb_cam_stats.py usb_cam_session_writer.py usb_cam_paths.py usb_cam_real_validation.py test_usb_cam_refactor.py test_usb_cam_real_validation.py`
- 受影响功能的定向 packaged/manual replay：
  - short direct
  - short video_then_frames
  - stop flow
  - optional longer soak for touched behavior

---

## Plan Basis

当前基线已经不是“待真机验收”的旧状态，而是：

- `v1.6.4`
- 最近主线提交：`5b1232a` `Hide FFmpeg console windows in packaged app`
- `test_usb_cam_refactor.py` 当前通过
- `test_usb_cam_real_validation.py` 当前通过
- `2026-05-24` Windows packaged preview / direct / video_then_frames / stop-flow / 中文与空格路径 / 5 分钟双模式稳定性验证均已完成

这意味着下一轮工作不该继续围绕“能不能录”，而应该围绕：

1. 能不能更早发现异常
2. 能不能在风险出现时更安全地停
3. 能不能在长录制时更稳地管磁盘与落盘策略

---

## Files

本计划主要涉及这些文件：

### Existing code

- [usb_cam_capture_state.py](/E:/codex/usb_cam_dev/usb_cam_capture_state.py)
- [usb_cam_ui_state.py](/E:/codex/usb_cam_dev/usb_cam_ui_state.py)
- [usb_cam_capture_helpers.py](/E:/codex/usb_cam_dev/usb_cam_capture_helpers.py)
- [usb_cam_runtime.py](/E:/codex/usb_cam_dev/usb_cam_runtime.py)
- [usb_cam_session_finalize.py](/E:/codex/usb_cam_dev/usb_cam_session_finalize.py)
- [usb_cam_stats.py](/E:/codex/usb_cam_dev/usb_cam_stats.py)
- [usb_burst_cam_4k25_manual_v1_6_3.py](/E:/codex/usb_cam_dev/usb_burst_cam_4k25_manual_v1_6_3.py)
- [test_usb_cam_refactor.py](/E:/codex/usb_cam_dev/test_usb_cam_refactor.py)

### Existing docs to update

- [README.md](/E:/codex/usb_cam_dev/README.md)
- [USB_CAM_REFACTOR_ROADMAP.md](/E:/codex/usb_cam_dev/USB_CAM_REFACTOR_ROADMAP.md)
- [docs/USB_CAM_PROJECT_HANDOFF.md](/E:/codex/usb_cam_dev/docs/USB_CAM_PROJECT_HANDOFF.md)

### Potential new code/docs

- [usb_cam_stop_prefs.py](/E:/codex/usb_cam_dev/usb_cam_stop_prefs.py)
- [docs/USB_CAM_STABILITY_POLICY.md](/E:/codex/usb_cam_dev/docs/USB_CAM_STABILITY_POLICY.md)

---

## Risks

- 当前 packaged 验收已通过，任何“稳定性增强”如果默认开启得太激进，反而可能把原本可用的录制路径打断
- `video_then_frames` 的“分段录制”如果做得太深，会引入更复杂的拆帧与汇总语义，超出本轮可控范围
- UI 上如果一次性加入太多状态文字，会让现在相对清晰的界面变得嘈杂
- 当前 docs 里还存在旧状态口径，如果不先统一，后续执行容易被旧描述误导

---

## Retirement

本轮不是重写，也不是退役当前主线。要退役的是“Phase 4 仍未闭环”的旧叙述，而不是现有代码路径。

需要逐步退休的旧表述：

- “真实 Windows packaged recording validation is still incomplete”
- “当前最重要的未闭环项是 Windows 真机最小录制验收”

这些话在新基线下已不再准确，应改为“Phase 4 已完成闭环，下一步进入稳定性增强与后续质量护栏”。

---

## Task 0: 统一仓库状态口径

**Why:** 当前代码和验证基线已经进入 RC-ready，但 README / handoff / roadmap 里仍残留一部分“待真机验收”的旧说法。先统一状态口径，后续所有稳定性工作才不会围绕错误前提展开。

**Files:**

- Modify [README.md](/E:/codex/usb_cam_dev/README.md)
- Modify [USB_CAM_REFACTOR_ROADMAP.md](/E:/codex/usb_cam_dev/USB_CAM_REFACTOR_ROADMAP.md)
- Modify [docs/USB_CAM_PROJECT_HANDOFF.md](/E:/codex/usb_cam_dev/docs/USB_CAM_PROJECT_HANDOFF.md)

**Impact / Compatibility:** 文档更新不改运行时行为，但会改变项目对外和对内的“当前状态”描述，应严格以 `2026-05-24` 的验证证据为准。

**Verification:**

- `rg -n "待补|未闭环|still incomplete|最重要的未闭环项|真机最小录制验收" README.md USB_CAM_REFACTOR_ROADMAP.md docs/USB_CAM_PROJECT_HANDOFF.md docs/USB_CAM_PHASE4_CURRENT_STATUS_NOTE.md`

**Steps:**

- [ ] Write the failing documentation audit
  - 在变更前运行：
    - `rg -n "待补|未闭环|still incomplete|最重要的未闭环项|真机最小录制验收" README.md USB_CAM_REFACTOR_ROADMAP.md docs/USB_CAM_PROJECT_HANDOFF.md`
  - 记录哪些旧句子仍与 `docs/USB_CAM_PHASE4_CURRENT_STATUS_NOTE.md` 冲突。

- [ ] Verify RED
  - 预期看到至少以下旧口径命中：
    - `README.md`
    - `USB_CAM_REFACTOR_ROADMAP.md`
    - `docs/USB_CAM_PROJECT_HANDOFF.md`

- [ ] Minimal code
  - 将这些文件中的当前状态改为：
    - Phase 4 packaged validation 已闭环
    - `2026-05-24` 已完成 packaged preview / direct / video_then_frames / stop-flow / path-compat / multi-run / 5-minute-long-run 验证
    - 下一阶段转为 stability hardening，而不是继续补 Phase 4 核心闭环

- [ ] Verify GREEN
  - 再次运行：
    - `rg -n "待补|未闭环|still incomplete|最重要的未闭环项|真机最小录制验收" README.md USB_CAM_REFACTOR_ROADMAP.md docs/USB_CAM_PROJECT_HANDOFF.md`
  - 预期旧口径消失或仅剩明确历史记录上下文。

- [ ] Commit
  - `git add README.md USB_CAM_REFACTOR_ROADMAP.md docs/USB_CAM_PROJECT_HANDOFF.md`
  - `git commit -m "docs: update project status after phase 4 rc closure"`

---

## Task 1: 扩展运行时健康指标

**Why:** 当前 UI 只有 elapsed / frame count / used size / estimate / fps。对于长时间录制，用户还需要更直接的健康信号：磁盘余量、预计还能录多久、当前写盘速度、当前健康等级。

**Files:**

- Modify [usb_cam_capture_state.py](/E:/codex/usb_cam_dev/usb_cam_capture_state.py)
- Modify [usb_cam_ui_state.py](/E:/codex/usb_cam_dev/usb_cam_ui_state.py)
- Modify [usb_cam_capture_helpers.py](/E:/codex/usb_cam_dev/usb_cam_capture_helpers.py)
- Modify [usb_burst_cam_4k25_manual_v1_6_3.py](/E:/codex/usb_cam_dev/usb_burst_cam_4k25_manual_v1_6_3.py)
- Modify [test_usb_cam_refactor.py](/E:/codex/usb_cam_dev/test_usb_cam_refactor.py)

**Impact / Compatibility:** 只扩展状态与显示，不改变采集主链路。默认 UI 可以先只更新 `status_var` 和日志，不强制新增大量可见控件；如果要显示新字段，优先加在现有统计区，不重排主界面。

**Verification:**

- `python -m pytest -q test_usb_cam_refactor.py -k "metrics or timer or disk_warning"`

**Steps:**

- [ ] Write the failing test
  - 在 [test_usb_cam_refactor.py](/E:/codex/usb_cam_dev/test_usb_cam_refactor.py) 新增测试，覆盖：
    - `estimated_time_left_s`
    - `estimated_time_left_text`
    - `write_rate_mb_s`
    - `capture_health`
    - `capture_health_reason`
  - 覆盖三种状态：
    - 正常
    - 低磁盘 warning
    - 已有 session 体积但尚无图片统计

- [ ] Verify RED
  - 运行：
    - `python -m pytest -q test_usb_cam_refactor.py -k "metrics or timer or disk_warning"`
  - 预期因缺字段断言失败。

- [ ] Minimal code
  - 在 [usb_cam_capture_state.py](/E:/codex/usb_cam_dev/usb_cam_capture_state.py) 增加缓存位：
    - `last_health_status`
    - `last_write_rate_mb_s`
    - `last_estimated_time_left_s`
  - 在 [usb_cam_ui_state.py](/E:/codex/usb_cam_dev/usb_cam_ui_state.py) 计算：
    - `write_rate_mb_s = cached_session_size / elapsed_float / 1024 / 1024`
    - 当 `per_min > 0` 且 `disk_free_bytes > 0` 时估算剩余时长
    - `capture_health` 先做三级：
      - `ok`
      - `warning`
      - `unknown`
    - `warning` 条件先只包含：
      - 低磁盘
      - 实时 FPS 显著低于目标 FPS 的阈值（例如低于目标的 70%）
  - 在 [usb_cam_capture_helpers.py](/E:/codex/usb_cam_dev/usb_cam_capture_helpers.py) 与主文件中，先把这些新字段用于：
    - status/log 文案
    - 可选 UI 显示

- [ ] Verify GREEN
  - 运行：
    - `python -m pytest -q test_usb_cam_refactor.py -k "metrics or timer or disk_warning"`
  - 预期全部通过。

- [ ] Commit
  - `git add usb_cam_capture_state.py usb_cam_ui_state.py usb_cam_capture_helpers.py usb_burst_cam_4k25_manual_v1_6_3.py test_usb_cam_refactor.py`
  - `git commit -m "feat: add capture health metrics"`

---

## Task 2: 引入 AutoStopPrefs

**Why:** 当前项目已经有软警告，但还缺少“达到危险阈值时自动停并尽量优雅收尾”的机制。VirtualDub2 最值得借的一点，就是 stop policy 不是单一条件，而是一组可控护栏。

**Files:**

- Create [usb_cam_stop_prefs.py](/E:/codex/usb_cam_dev/usb_cam_stop_prefs.py)
- Modify [usb_cam_capture_state.py](/E:/codex/usb_cam_dev/usb_cam_capture_state.py)
- Modify [usb_cam_capture_helpers.py](/E:/codex/usb_cam_dev/usb_cam_capture_helpers.py)
- Modify [usb_cam_ui_state.py](/E:/codex/usb_cam_dev/usb_cam_ui_state.py)
- Modify [usb_burst_cam_4k25_manual_v1_6_3.py](/E:/codex/usb_cam_dev/usb_burst_cam_4k25_manual_v1_6_3.py)
- Modify [usb_cam_runtime.py](/E:/codex/usb_cam_dev/usb_cam_runtime.py)
- Modify [usb_cam_session_finalize.py](/E:/codex/usb_cam_dev/usb_cam_session_finalize.py)
- Modify [test_usb_cam_refactor.py](/E:/codex/usb_cam_dev/test_usb_cam_refactor.py)

**Impact / Compatibility:** 默认值必须保持“相当于当前行为”，即不开启就不拦截。第一轮不要求做复杂 GUI 设置面板，可以先内置默认配置并写入 metadata。

**Verification:**

- `python -m pytest -q test_usb_cam_refactor.py -k "stop or auto or finalize or runtime"`

**Steps:**

- [ ] Write the failing test
  - 为以下情形新增测试：
    - 达到最大录制时长时触发 auto-stop
    - 剩余磁盘低于 hard threshold 时触发 auto-stop
    - 连续低 FPS / 疑似掉速时触发 auto-stop
    - auto-stop 只触发一次
    - auto-stop 原因写入 metadata / summary

- [ ] Verify RED
  - 运行：
    - `python -m pytest -q test_usb_cam_refactor.py -k "stop or auto or finalize or runtime"`
  - 预期失败，因为当前没有 `AutoStopPrefs` 语义。

- [ ] Minimal code
  - 新建 [usb_cam_stop_prefs.py](/E:/codex/usb_cam_dev/usb_cam_stop_prefs.py)，定义：
    - `AutoStopPrefs`
    - `AutoStopDecision`
    - `evaluate_auto_stop(metrics, now, state, prefs)`
  - 第一轮只支持三项：
    - `max_duration_s`
    - `min_disk_free_mb_hard`
    - `min_effective_fps_ratio`
  - 在 [usb_cam_capture_helpers.py](/E:/codex/usb_cam_dev/usb_cam_capture_helpers.py) 的 `update_capture_timer_tick` 或主线程 timer 路径中调用决策函数
  - 命中时执行：
    - `status_var` 改为明确文案
    - 写一条 `[auto-stop] ...` 到 `run_log.txt`
    - 调用现有 stop 流程
  - 在 [usb_cam_session_finalize.py](/E:/codex/usb_cam_dev/usb_cam_session_finalize.py) / metadata 中写入：
    - `stop_reason`
    - `stop_reason_detail`
    - `auto_stopped`

- [ ] Verify GREEN
  - 运行：
    - `python -m pytest -q test_usb_cam_refactor.py -k "stop or auto or finalize or runtime"`
  - 预期新增 stop-policy 测试通过，旧 stop-flow 测试不回归。

- [ ] Commit
  - `git add usb_cam_stop_prefs.py usb_cam_capture_state.py usb_cam_capture_helpers.py usb_cam_ui_state.py usb_burst_cam_4k25_manual_v1_6_3.py usb_cam_runtime.py usb_cam_session_finalize.py test_usb_cam_refactor.py`
  - `git commit -m "feat: add auto stop safety policies"`

---

## Task 3: 为 `video_then_frames` 设计保守版分段录制

**Why:** 当前 `video_then_frames` 长时间录制仍绑定单个 AVI。虽然 5 分钟验证已通过，但如果未来录制更长，单文件仍是风险点。VirtualDub2 的 spill mode 可以借思路，但不需要一上来实现跨盘复杂版本。

**Files:**

- Modify [usb_cam_runtime.py](/E:/codex/usb_cam_dev/usb_cam_runtime.py)
- Modify [usb_cam_capture.py](/E:/codex/usb_cam_dev/usb_cam_capture.py)
- Modify [usb_cam_session_finalize.py](/E:/codex/usb_cam_dev/usb_cam_session_finalize.py)
- Modify [test_usb_cam_refactor.py](/E:/codex/usb_cam_dev/test_usb_cam_refactor.py)
- Create [docs/USB_CAM_STABILITY_POLICY.md](/E:/codex/usb_cam_dev/docs/USB_CAM_STABILITY_POLICY.md)

**Impact / Compatibility:** 第一轮不是做真正的“多盘 spill system”，而是做“单目录内可选分段视频录制”的设计与最小实现预备，必须默认关闭，避免影响当前通过的 `video_then_frames` 基线。

**Verification:**

- `python -m pytest -q test_usb_cam_refactor.py -k "video_then_frames or extract or runtime"`

**Steps:**

- [ ] Write the failing test
  - 为 `video_then_frames` 增加分支测试：
    - 默认行为仍是单个 `capture_4k25_mjpeg.avi`
    - 开启 segmented policy 时，运行时接受多个视频片段路径
    - finalize 阶段能在 metadata 中记录多个 segment
  - 当前先不要求真实 FFmpeg segment 命令跑通，只要求 runtime 与 metadata 契约先成立。

- [ ] Verify RED
  - 运行：
    - `python -m pytest -q test_usb_cam_refactor.py -k "video_then_frames or extract or runtime"`
  - 预期新增 segment 契约测试失败。

- [ ] Minimal code
  - 在 [usb_cam_runtime.py](/E:/codex/usb_cam_dev/usb_cam_runtime.py) 为 `video_then_frames` 增加可扩展数据结构：
    - `video_segments`
    - `segment_mode`
  - 先支持两层：
    - `single_file` 默认
    - `planned_segmented` 占位但不默认启用
  - 若你决定第一轮就落最小可运行 segment：
    - 在 [usb_cam_capture.py](/E:/codex/usb_cam_dev/usb_cam_capture.py) 增加一个 FFmpeg segment 命令 builder
    - 只用于 `video_then_frames`
    - 输出片段命名固定、落在 `video/`
    - finalize / extract 逐段处理并汇总
  - 若第一轮不落真实分段执行，也至少把 metadata / contract / docs 钉住，为下一轮实现做边界准备。

- [ ] Verify GREEN
  - 运行：
    - `python -m pytest -q test_usb_cam_refactor.py -k "video_then_frames or extract or runtime"`
  - 预期当前单文件行为不回归，segment 契约测试通过。

- [ ] Commit
  - `git add usb_cam_runtime.py usb_cam_capture.py usb_cam_session_finalize.py test_usb_cam_refactor.py docs/USB_CAM_STABILITY_POLICY.md`
  - `git commit -m "design: prepare segmented video capture path"`

---

## Task 4: 把稳定性策略写成仓库内可复用说明

**Why:** 当项目从“能用”进入“可稳定交付”阶段，很多行为不再是代码细节，而是产品策略。把规则写进文档能避免下次又回到“这个阈值为什么这么定”的口头状态。

**Files:**

- Create [docs/USB_CAM_STABILITY_POLICY.md](/E:/codex/usb_cam_dev/docs/USB_CAM_STABILITY_POLICY.md)
- Modify [README.md](/E:/codex/usb_cam_dev/README.md)

**Impact / Compatibility:** 只补文档，不改运行时。文档要以当前 RC 已通过为前提，说明下一阶段的 hardening 方向。

**Verification:**

- `rg -n "AutoStop|capture health|segmented|stability policy|5-minute" README.md docs/USB_CAM_STABILITY_POLICY.md`

**Steps:**

- [ ] Write the failing documentation outline
  - 先列出文档需要覆盖的 5 个点：
    - 当前验证基线
    - 健康指标定义
    - auto-stop 规则
    - segment 策略边界
    - 何时需要再跑 packaged soak

- [ ] Verify RED
  - 确认当前仓库还没有一份专门的 stability policy 文档。

- [ ] Minimal code
  - 写 [docs/USB_CAM_STABILITY_POLICY.md](/E:/codex/usb_cam_dev/docs/USB_CAM_STABILITY_POLICY.md)，明确：
    - 当前已验证 scope
    - 下一阶段稳定性目标
    - health / auto-stop / segment 术语
    - 哪些是默认行为，哪些是可选增强
  - 在 [README.md](/E:/codex/usb_cam_dev/README.md) 增加链接。

- [ ] Verify GREEN
  - 运行：
    - `rg -n "AutoStop|capture health|segmented|stability policy|5-minute" README.md docs/USB_CAM_STABILITY_POLICY.md`
  - 预期命中新增内容。

- [ ] Commit
  - `git add README.md docs/USB_CAM_STABILITY_POLICY.md`
  - `git commit -m "docs: add stability policy"`

---

## Recommended Execution Order

1. Task 0：统一状态口径
2. Task 1：扩展健康指标
3. Task 2：引入 AutoStopPrefs
4. Task 4：沉淀稳定性策略文档
5. Task 3：分段录制设计 / 最小实现预备

说明：

- `Task 3` 刻意放后，是因为它的风险最大
- `Task 1` 和 `Task 2` 是最适合立刻提升长期录制韧性的两刀
- 在当前 `2026-05-24` RC 已通过的背景下，最值钱的是“观测 + 自动保护”，不是先碰更复杂的分段落盘

---

## One-Line Recommendation

**当前最合适的下一轮优化，不是继续扩打包或换框架，而是在 `v1.6.4` 已验证主线之上，先补齐“看得见风险、到阈值能自动安全停”的稳定性护栏。**
