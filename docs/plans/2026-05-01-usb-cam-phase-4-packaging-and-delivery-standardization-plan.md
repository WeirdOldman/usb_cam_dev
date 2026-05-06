# USB_CAM Phase 4 Packaging & Delivery Standardization Plan

> **For Hermes:** 这一阶段继续走 vibe 的 execution-first 路线，但只收敛到绿色版打包入口与首轮验收准备；不扩范围到安装器、onefile、PySide6 或产品化美化。

**Goal:** 为 `usb_cam_dev` 落地一个可重复执行的 Windows 绿色版打包入口，固定 `PyInstaller --onedir` 方案、FFmpeg 随包策略、输出目录结构与首轮验收步骤，让项目从“可运行源码”进入“可分发打包准备完成”。

**Architecture:** 保持现有 Tkinter + FFmpeg + 已拆分模块结构不变。Phase 4 只做打包标准化：新增 `build.bat`、明确入口/目录/依赖收口、衔接现有 `USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`。避免一边打包一边继续做 UI 重构或安装器扩展。

**Tech Stack:** Python 3.10+, PyInstaller `--onedir`, Tkinter, FFmpeg, Windows batch (`build.bat`)

---

## 结论先说

当前最该做的不是继续讨论打包，而是先把 **首版 `build.bat`** 落下来。

原因很直接：
- 代码层已经具备基本 frozen 路径兼容
- 打包检查清单已经存在
- 当前真正缺的是“一个固定入口”
- 没有 `build.bat`，后面所有打包验收都只能靠手工临时拼命令

---

## 本阶段范围（锁死）

只做五件事：

1. **补首版 `build.bat`**
   - 固定 GUI 主入口
   - 固定 `PyInstaller --onedir` 参数
   - 固定输出目录结构

2. **明确 FFmpeg 随包策略**
   - 明确 `tools/ffmpeg.exe` 为默认随包位置
   - 保留 `PATH` fallback，但不把它当主分发策略

3. **明确构建目录约定**
   - `build/`
   - `dist/USB_Cam_4K25/`
   - 必要时创建 `dist/USB_Cam_4K25/tools/`

4. **把首轮验收口径接上现有 checklist**
   - 对接 `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`
   - 明确构建后第一轮该怎么验

5. **补最小文档收口**
   - 如需，更新 roadmap / 当前计划文档中的 Phase 4 描述

明确不做：
- 不做 `installer.iss`
- 不做 Inno Setup
- 不做 `--onefile`
- 不加图标美化
- 不迁移 PySide6
- 不扩任何新功能

---

## 当前基线

已知当前事实基线：
- 主入口：`usb_burst_cam_4k25_manual_v1_6_3.py`
- 支撑模块：`usb_cam_paths.py`、`usb_cam_preview.py`、`usb_cam_process.py`、`usb_cam_runtime.py` 等已拆分
- 自动测试基线：`20 passed`
- 已有文档：
  - `USB_CAM_REFACTOR_ROADMAP.md`
  - `docs/USB_CAM_MANUAL_VALIDATION_CHECKLIST.md`
  - `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`
- 当前已落地：
  - `build.bat` 已存在
  - 首轮 Windows EXE 已成功打包
  - EXE 已确认可正常打开
  - `docs/USB_CAM_PHASE4_TASK3_1_FIRST_BUILD_GUIDE.md`
  - `docs/USB_CAM_PHASE4_TASK3_2_FIRST_BUILD_RECORD_TEMPLATE.md`
  - `docs/USB_CAM_PHASE4_TASK3_3_WINDOWS_RUN_PACKAGE.md`
- 当前仍缺：
  - 真实录制实验尚未执行
  - direct 模式最小录制验证
  - video_then_frames 模式最小录制验证
  - 停止流程验证
  - 输出文件完整性检查
  - `*.spec` 不存在
  - `installer.iss` 不存在
  - 仓库内未见 `ffmpeg.exe`
  - 仓库内未见 `.ico`

当前结论：
- Phase 4 的打包入口与文档脚手架已经落地
- 当前准确状态应表述为：**EXE 启动已通过，录制链路待实测**
- 安装器属于后续稳定后补项，不是这一刀主任务

---

## Phase 4 Deliverables

本阶段至少新增/完善以下交付物：

1. `build.bat`
2. 如有必要：`dist/USB_Cam_4K25/tools/` 目录约定说明
3. 如有必要：在文档中补一段 `tools/ffmpeg.exe` 放置规则
4. 一套可直接执行的打包后首轮验收步骤

---

## Recommended execution order

### Task 1：确定打包入口与目录约定

**Objective:** 把构建入口、输出目录、工具目录、清理策略先定死，避免脚本边写边猜。

**Files:**
- Inspect: `usb_burst_cam_4k25_manual_v1_6_3.py`
- Inspect: `usb_cam_paths.py`
- Inspect: `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`
- Reference: `USB_CAM_REFACTOR_ROADMAP.md`

**Steps:**
1. 确认 GUI 主入口文件
2. 确认 `find_ffmpeg()` 的默认查找顺序
3. 固定 onedir 输出目录名
4. 固定 `tools/ffmpeg.exe` 作为主随包位置
5. 固定 `build/` / `dist/` 清理策略

**Verification:**
- 形成明确目录约定
- 不改业务代码，只冻结构建事实

---

### Task 2：新增 `build.bat`

**Objective:** 提供一个 Windows 下可重复运行的首版绿色包构建入口。

**Files:**
- Create: `build.bat`

**必须包含：**
- Python 可执行探测（优先 `py -3`，其次 `python`）
- PyInstaller 可用性检查
- 清理旧 `build/`、`dist/` 产物
- 使用 `usb_burst_cam_4k25_manual_v1_6_3.py` 作为入口
- 采用 `--noconfirm --clean --windowed --onedir`
- 固定输出目录为 `dist/USB_Cam_4K25`
- 预留/创建 `dist/USB_Cam_4K25/tools/`
- 构建结束后输出下一步提示（例如拷贝 `ffmpeg.exe` 到 `tools/`）

**注意：**
- 本任务不要求把 `ffmpeg.exe` 内嵌进 spec
- 先让“构建骨架”跑起来

**Verification:**
- `build.bat` 文件存在
- 内容可读、参数固定、不依赖人工猜路径

---

### Task 3：必要时补打包说明收口

**Objective:** 避免后续使用者看到 `build.bat` 仍不知道 `ffmpeg.exe` 应该放哪。

**Files:**
- Modify: `USB_CAM_REFACTOR_ROADMAP.md`（如需）
- Or Modify: `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`（如需）
- Or add a short note adjacent to `build.bat`

**必须说明：**
- `tools/ffmpeg.exe` 是默认绿色包内路径
- 没有该文件时，程序仍会尝试 PATH fallback
- 分发时建议随包放置，不建议依赖用户机器预装

**Verification:**
- 至少有一处文档把 FFmpeg 随包策略说清楚

---

### Task 4：构建前静态验证

**Objective:** 在真正跑 PyInstaller 前，先确认脚本和主入口没有明显语法/路径错误。

**Files:**
- Verify: `build.bat`
- Verify: `usb_burst_cam_4k25_manual_v1_6_3.py`
- Verify: `usb_cam_paths.py`

**Verification commands:**
```bash
python3 -m py_compile /root/.hermes/workspace/shared_space/usb_cam_dev/usb_burst_cam_4k25_manual_v1_6_3.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_paths.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_preview.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_process.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_runtime.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_ui_state.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_finalize.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_session_finalize.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_session_writer.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_capture.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_ffmpeg.py \
/root/.hermes/workspace/shared_space/usb_cam_dev/usb_cam_stats.py

pytest -q /root/.hermes/workspace/shared_space/usb_cam_dev/test_usb_cam_refactor.py
```

**Done means:**
- 语法无误
- 自动测试基线未退化

---

### Task 5：首轮打包验收准备

**Objective:** 让下一个动作可以直接进入真实 PyInstaller 演练，而不是再做一轮口头规划。

**Files:**
- Reference: `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`

**至少准备好：**
1. 运行 `build.bat`
2. 检查 `dist/USB_Cam_4K25/` 是否生成
3. 若缺 `ffmpeg.exe`，复制到 `dist/USB_Cam_4K25/tools/`
4. 按 checklist 跑最小冷启动 / FFmpeg 发现 / GUI / direct / video_then_frames 检查

**Verification:**
- 明确首轮验收路径
- 后续可直接进入 PyInstaller 实战

---

## Immediate next step

按当前节奏，**现在就该做 Task 2：新增 `build.bat`**。

如果这一刀顺利，下一步就是：

1. 静态验证 `build.bat`
2. 跑首轮 `PyInstaller --onedir`
3. 对照 `USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md` 做第一轮真实验收

---

## 一句话结论

**Phase 4 这一刀的核心不是“把打包全部做完”，而是先把 Windows 绿色版的固定打包入口和 FFmpeg 随包策略钉死。先有 `build.bat`，再谈首轮出包验收。**
