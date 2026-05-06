# USB_CAM Phase 3 Execution Plan

> **For Hermes:** 这一阶段走 vibe 的 planning-first 路线，先补测试与验证体系，不扩范围到 PySide6 迁移或安装包美化。

**Goal:** 把当前 USB 摄像头工具从“已有局部重构和零散验证”推进到“有固定自动验证 + 手工验收清单 + 打包前验证口径”的下一阶段。

**Architecture:** 保持现有 Tkinter + FFmpeg + 已拆分模块结构不变。Phase 3 只做验证体系建设：补纯后端测试、整理手工验收脚本、沉淀打包前/打包后验证清单。避免一边补测试一边继续大改主流程。

**Tech Stack:** Python 3.10+, pytest, Tkinter, FFmpeg, PyInstaller `--onedir`（先做验证准备，不要求本阶段完成发布物）

---

## 结论先说

下一阶段建议正式进入 **Phase 3：测试与验证体系补齐**，而不是继续拆代码。

原因很直接：
- Phase 2 模块化已经够用了
- 当前最缺的是“怎么稳定证明它没坏”
- 继续拆边角收益低，先把验证基线做实更划算

---

## 本阶段范围（锁死）

只做三件事：

1. **补自动测试**
   - 继续覆盖纯函数 / 纯模块逻辑
   - 不碰真实摄像头
   - 不做 GUI 自动化

2. **补手工验证清单**
   - 固定预览 / 采集 / 停止 / 输出检查步骤
   - 后续每次改动都能照着跑

3. **补打包验证清单**
   - 为后面 Phase 4 的 `PyInstaller --onedir` 做验收口径准备

明确不做：
- 不迁移 PySide6
- 不继续大拆 UI
- 不做安装包
- 不扩新功能

---

## 当前基线

已知当前验证基线：
- 主文件：`usb_burst_cam_4k25_manual_v1_6_3.py`
- 支撑模块：11 个
- 当前自动测试：`test_usb_cam_refactor.py`
- 当前通过状态：`20 passed`

当前已补齐：
- `usb_cam_runtime.py` 的非 direct 分支、fallback 与删除视频分支测试
- `usb_cam_session_writer.py` / `usb_cam_finalize.py` / `usb_cam_session_finalize.py` 的输出与收尾契约测试
- `usb_cam_capture.py` / `usb_cam_stats.py` / `usb_cam_process.py` / `usb_cam_ui_state.py` 的关键边界与回调分支测试
- 固定手工验收清单文档
- 固定打包验收清单文档

当前结论：
- Phase 3 已经从“重构护栏”推进到“自动测试 + 手工验收 + 打包验收”三件套闭环
- 当前更适合进入 Phase 3 收尾归档，而不是继续扩零散测试

---

## Phase 3 Deliverables

本阶段结束时，仓库里至少应新增/完善以下交付物：

1. `test_usb_cam_refactor.py` 持续扩充
2. `docs/USB_CAM_MANUAL_VALIDATION_CHECKLIST.md`
3. `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`
4. 如有必要：新增 1~2 个面向纯模块的测试文件

---

## Recommended execution order

### Task 1：盘点现有测试覆盖缺口

**Objective:** 明确哪些模块已经有测试，哪些还只有代码没有护栏。

**Files:**
- Inspect: `test_usb_cam_refactor.py`
- Inspect: `usb_cam_paths.py`
- Inspect: `usb_cam_session_writer.py`
- Inspect: `usb_cam_stats.py`
- Inspect: `usb_cam_ffmpeg.py`
- Inspect: `usb_cam_preview.py`
- Inspect: `usb_cam_capture.py`
- Inspect: `usb_cam_process.py`
- Inspect: `usb_cam_runtime.py`
- Inspect: `usb_cam_ui_state.py`
- Inspect: `usb_cam_finalize.py`
- Inspect: `usb_cam_session_finalize.py`

**Steps:**
1. 列出每个模块当前已有测试点
2. 标记“纯逻辑但未覆盖”的函数
3. 优先级排序：先测纯函数，再测轻量 orchestration
4. 形成一份缺口清单再继续

**Verification:**
- 产出覆盖缺口清单
- 不改代码，只做事实调查

---

### Task 2：补 `usb_cam_paths.py` / `usb_cam_stats.py` 边界测试

**Objective:** 把路径/统计类纯函数护栏补厚，先拿最稳的一批。

**Files:**
- Modify: `test_usb_cam_refactor.py` 或新增 `test_usb_cam_paths.py`
- Test target: `usb_cam_paths.py`
- Test target: `usb_cam_stats.py`

**推荐补点：**
- `safe_image_prefix()` 的空值 / 特殊字符 / 长度边界
- `bytes_to_mb()` 的 0 / 小数格式口径
- `frame_metrics()` 的 0 帧 / 正常帧数 / 时间边界

**TDD cadence:**
1. 先写失败测试
2. 单测失败验证
3. 若逻辑已存在，仅确认测试变绿
4. 全量回归

**Verification commands:**
- `pytest -q /root/.hermes/workspace/shared_space/usb_cam_dev/test_usb_cam_refactor.py`

---

### Task 3：补 `usb_cam_session_writer.py` / `usb_cam_session_finalize.py` 输出一致性测试

**Objective:** 锁住 session 收尾输出文件的一致性。

**Files:**
- Modify: `test_usb_cam_refactor.py` 或新增 `test_usb_cam_session_outputs.py`
- Test target: `usb_cam_session_writer.py`
- Test target: `usb_cam_session_finalize.py`

**推荐补点：**
- `write_frames_csv()` 输出列结构
- `write_metadata()` 生成内容包含关键字段
- `write_summary()` 内容存在关键摘要字段
- `finalize_session()` 对 session 总大小字段的补写

**Verification commands:**
- `pytest -q /root/.hermes/workspace/shared_space/usb_cam_dev/test_usb_cam_refactor.py`

---

### Task 4：补 `usb_cam_process.py` / `usb_cam_finalize.py` 状态收尾测试

**Objective:** 锁住停止/收尾路径的关键统计行为。

**Files:**
- Modify: `test_usb_cam_refactor.py`
- Test target: `usb_cam_process.py`
- Test target: `usb_cam_finalize.py`

**推荐补点：**
- `parse_ffmpeg_progress_line()` 的异常输入
- `finalize_capture_done_state()` 在有 frame/session 文件时的统计值
- 空目录 / 缺目录 / 单文件目录边界

**Verification commands:**
- `pytest -q /root/.hermes/workspace/shared_space/usb_cam_dev/test_usb_cam_refactor.py`

---

### Task 5：写手工验证清单

**Objective:** 固定一份每次改完都能重复执行的人工验收流程。

**Files:**
- Create: `docs/USB_CAM_MANUAL_VALIDATION_CHECKLIST.md`

**必须覆盖：**
- 启动 GUI
- 检测 FFmpeg
- 启动预览
- 停止预览
- direct 模式采集 10 秒
- video_then_frames 模式采集 10 秒
- 手动停止流程
- 检查 `metadata` / `summary` / `frames.csv`
- 检查 UI 统计字段是否持续变化

**交付要求：**
- 每一步写“操作 / 预期结果 / 失败现象”
- 不写空话，按实际点点点流程写

---

### Task 6：写打包验证清单

**Objective:** 为 Phase 4 提前准备发布验收标准。

**Files:**
- Create: `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`

**必须覆盖：**
- 无 Python Windows 环境启动
- `tools/ffmpeg.exe` 自动识别
- 中文路径输出
- 输出目录写权限
- 日志文件生成
- direct / video_then_frames 两种模式最小验证
- 安装包阶段预留：安装 / 卸载 / 快捷方式（先列 checklist，不要求本阶段完成）

---

### Task 7：阶段回归封板

**Objective:** 用统一命令确认本阶段新增护栏没有破坏现有基线。

**Files:**
- Verify all touched test/docs files

**Verification commands:**
```bash
python3 -m py_compile /root/.hermes/workspace/shared_space/usb_cam_dev/usb_burst_cam_4k25_manual_v1_6_3.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_finalize.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_session_finalize.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_ui_state.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_runtime.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_process.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_capture.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_preview.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_ffmpeg.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_stats.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_session_writer.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_paths.py

pytest -q /root/.hermes/workspace/shared_space/usb_cam_dev/test_usb_cam_refactor.py
```

**Phase 3 done means:**
- 自动测试覆盖比现在更厚
- 有固定手工验证清单
- 有固定打包验证清单
- 仍然保持 Tkinter + FFmpeg 主链路不变

---

## Immediate next step

按当前 vibe 节奏，**Phase 3 已完成，下一步不再是补零散测试**。

建议直接进入两选一：

1. **Phase 3 收尾归档（当前已执行）**
   - 更新 roadmap / plan 文档
   - 固化 `20 passed` 自动测试基线
   - 固化手工与打包验收口径

2. **进入 Phase 4：打包与交付标准化**
   - 先做绿色版/`PyInstaller --onedir` 实战验证
   - 再补 build 脚本、发布说明、安装器材料

当前推荐：**直接进入 Phase 4。**

---

## 一句话结论

**下一阶段不是继续拆代码，而是进入 Phase 3：把这个工具的自动测试、手工验收、打包验证三套护栏补齐。**
