# USB_CAM 分阶段重构路线图

> **For Hermes:** 按阶段推进，不要一次性全量重写 UI 框架。先稳采集主链路，再拆结构，再规范打包，最后再评估 PySide6 迁移。

**Goal:** 把当前 `usb_burst_cam_4k25_manual_v1_6_3.py` 从“可用单文件工具”演进成“适合长期维护和正式发布的 Windows 摄像头采集软件”。

**Architecture:** 先保留 Tkinter + FFmpeg 技术路线，优先做稳定性、统计性能、长时间采集保护和代码分层；等后端模块稳定后，再决定是否迁移到 PySide6。这样能避免在主流程刚稳定时同时更换 UI、线程模型和打包方式导致回归。

**Tech Stack:** Python 3.10+, Tkinter（当前阶段保留）, FFmpeg DirectShow, threading + queue, PyInstaller `--onedir`, Inno Setup（后续）, 可选 PySide6（后续阶段评估）

---

## 当前状态摘要

当前项目已经确认：

- 摄像头能力固定为 `3840x2160 @ 25fps`
- 主采集路线固定为 `FFmpeg DirectShow + MJPEG`
- GUI 当前为 Tkinter 单文件实现
- 已支持：预览、开始/停止采集、直接图片序列、先录视频再拆帧、metadata/summary/log 输出
- 已针对长时间采集开始做统计优化：实时统计从高频全量扫描改为低频缓存 + 结束全量校准

当前主要问题：

- 单文件过大，UI / 采集 / 统计 / 输出逻辑混在一起
- 预览链路偏重，后续可能影响长时间运行体验
- 统计逻辑虽然已优化，但仍需要实机验证
- 打包、配置、日志、资源路径仍偏“工具脚本化”，不够正式

---

## Phase 0：冻结技术边界（先别乱扩）

**Objective:** 明确哪些东西短期不动，避免重构过程中把主链路打散。

**边界规定：**

- 先 **不切换 PySide6**
- 先 **不改摄像头模式**（仍固定 4K25）
- 先 **不改 FFmpeg 主采集路线**
- 先 **不做 onefile 打包**
- 先 **不扩展无关功能**（如复杂图表、多摄像头、网络控制）

**本阶段产出：**

- 保留当前主入口文件作为基线参考
- 所有后续改动先在 `usb_cam_dev/` 下推进

---

## Phase 1：稳定性优先（继续把当前版本做稳）

**Objective:** 把“长时间采集可用”放在第一优先级，先稳住主流程。

### 1.1 实时统计稳定化

**目标：** 让长时间采集中 UI 不因目录扫描而越来越卡。

**任务：**

- 保留当前“实时缓存 + 结束全量校准”方案
- 实机验证以下指标是否正常：
  - 运行时间
  - 已生成图片
  - 实时 FPS
  - 已占用空间
  - 估算图片空间
- 若异常，再补：
  - 统计调试日志
  - scan 间隔配置化
  - direct 模式与 video_then_frames 模式区分口径

### 1.2 停止与异常收尾强化

**目标：** 避免长时间采集结束时残留 ffmpeg 进程或输出文件不完整。

**任务：**

- 为 `stop_capture()` 增加更清晰的状态流转
- 为 `run_process()` / `worker_capture()` 增加异常阶段标记
- 在 metadata 中记录：
  - 是正常结束还是手动停止
  - 停在录制阶段还是拆帧阶段
  - 最终退出码

### 1.3 长时间采集保护

**目标：** 提前发现磁盘不足、输出路径问题、异常膨胀等风险。

**任务：**

- 增加输出盘剩余空间检测
- 启动采集前做最小空间提示
- 采集中按阈值预警（例如低于 X GB）
- summary / metadata 中补充磁盘状态

### 1.4 预览链路压载

**目标：** 让预览尽量不影响正式采集和 UI。

**任务：**

- 将预览参数做成集中常量或配置项
- 优先尝试：
  - `PREVIEW_FPS` 从 5 → 3 可选
  - `PREVIEW_WIDTH` 从 640 → 480 可选
- 保证“开始采集自动停预览”的逻辑不变

**Phase 1 验收标准：**

- 连续长时间采集时 UI 不明显恶化
- 停止采集后能稳定收尾
- metadata / summary / frames.csv 一致
- 不引入主流程回归

---

## Phase 2：模块化拆分（不换框架，先拆结构）

**Objective:** 在不改变 Tkinter 外壳的前提下，把单文件拆成可维护结构。

### 2.1 推荐目录结构

```text
usb_cam_app/
├─ main.py
├─ ui/
│  ├─ main_window.py
│  ├─ preview_panel.py
│  ├─ settings_panel.py
│  └─ status_panel.py
├─ backend/
│  ├─ capture_service.py
│  ├─ preview_service.py
│  ├─ ffmpeg_runner.py
│  ├─ session_writer.py
│  ├─ stats_tracker.py
│  ├─ disk_monitor.py
│  └─ paths.py
├─ assets/
│  ├─ icon.ico
│  └─ ...
├─ tools/
│  └─ ffmpeg.exe
├─ tests/
│  ├─ test_paths.py
│  ├─ test_stats_tracker.py
│  ├─ test_session_writer.py
│  └─ ...
├─ build.bat
├─ installer.iss
└─ README.md
```

### 2.2 拆分顺序

**先拆纯后端，最后拆 UI。**

推荐顺序：

1. `paths.py`
   - `app_base_dir()`
   - `candidate_base_dirs()`
   - `find_ffmpeg()`

2. `session_writer.py`
   - `make_session()`
   - `write_metadata()`
   - `write_summary()`
   - `write_frames_csv()`

3. `stats_tracker.py`
   - 缓存帧计数
   - session 大小缓存
   - 实时 fps 计算

4. `ffmpeg_runner.py`
   - 组命令
   - 跑进程
   - 解析 progress / frame 输出

5. `capture_service.py`
   - direct / record / extract 流程控制

6. `preview_service.py`
   - 预览 ffmpeg 进程
   - PNG 帧解析

7. `ui/` 层拆分
   - 只负责控件和回调绑定

### 2.3 拆分原则

- 每拆一层，都先保证行为不变
- 不在拆分时顺手加新功能
- 先抽函数和类，再挪文件
- 每次拆分后都做最小验证

**Phase 2 验收标准：**

- 主功能与当前版本一致
- UI 仍能启动
- 采集流程无回归
- 后端已有最基础测试覆盖

---

## Phase 3：测试与验证体系补齐

**Objective:** 从“手动点点看”升级为“有最小自动验证能力”。

**当前状态：✅ 已完成闭环**

### 3.1 已完成的自动测试补强

已完成的高价值补点：

- `safe_image_prefix()` / 路径与命名边界
- `find_ffmpeg()` 路径策略
- session 目录生成
- metadata / summary / frames.csv 输出契约
- stats tracker 的缓存 / fps 计算 / 0 值边界
- ffmpeg progress 行解析
- `usb_cam_runtime.py` 的 direct / video_then_frames / fallback / 删除视频分支
- `usb_cam_process.py` 的停止与回调路径
- `usb_cam_ui_state.py` 的扫描、显示文案与消息分发路径

### 3.2 已完成的手工验证清单

已新增：

- `docs/USB_CAM_MANUAL_VALIDATION_CHECKLIST.md`

覆盖内容：

- 启动 GUI
- 启动/停止预览
- direct 模式采集
- video_then_frames 模式采集
- 手动停止
- 检查输出目录文件完整性
- 检查长时间采集统计是否持续变化
- 中文路径 / 空格路径 / 不可写路径检查

### 3.3 已完成的 Windows / 打包验证清单

已新增：

- `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`

覆盖内容：

- 无 Python 环境启动
- `tools/ffmpeg.exe` 或等效 ffmpeg 路径识别
- 中文路径输出正常
- 桌面 GUI 启动验证
- 日志和输出目录可写
- direct / video_then_frames 两种模式最小验证
- onefile `_MEI` / 资源路径风险检查

**Phase 3 当前验收标准：**

- 自动测试基线：`20 passed`
- 纯后端关键逻辑具备自动测试
- 手工验证清单固定下来
- 打包前后验证标准统一
- Tkinter + FFmpeg 主链路保持不变

---

## Phase 4：打包与交付标准化

**Objective:** 把“开发脚本工具”变成“可分发软件”。

**当前状态：🟡 工程基线已稳定，Windows 真实录制验收待补**

当前已确认：

- `build.bat` 已落地
- Windows EXE 已成功打包
- EXE 可正常打开，基础启动链路正常
- `test_usb_cam_refactor.py` 自动测试基线已推进到 **31 passed**
- GitHub Actions 双平台（ubuntu / windows）当前为绿色
- 已完成一轮最小运行期韧性增强：
  - 启动前磁盘空间软提示
  - 低磁盘空间 warning 接入状态/日志路径
  - 对应 CI 回归问题已修复
- 当前**尚未进行真实 Windows 录制实验**

这意味着：

- 打包层面已经通过“能出包、能启动、GUI 能起来、自动测试和双平台 CI 正常”这一层
- 但还**不能宣称 Phase 4 验收闭环完成**
- 当前仍缺少最关键的功能侧验证：
  - direct 模式录制
  - video_then_frames 模式录制
  - 停止流程
  - 输出文件落盘检查

### 4.1 绿色版优先

先做：

```text
PyInstaller --onedir
```

发布物建议：

```text
USB_Cam_4K25_Portable_vX.Y.Z.zip
```

目录大致：

```text
dist/
└─ USB_Cam_4K25/
   ├─ USB_Cam_4K25.exe
   ├─ tools/
   │  └─ ffmpeg.exe
   ├─ assets/
   └─ ...
```

### 4.2 安装包

稳定后再补：

- `installer.iss`
- 桌面快捷方式
- 开始菜单快捷方式
- 卸载入口

发布物：

```text
USB_Cam_4K25_Setup_vX.Y.Z.exe
```

### 4.3 路径规范

正式化后建议：

- 安装目录：程序自身
- 用户输出目录：用户自选
- 配置：`AppData/Roaming/...`
- 日志：`AppData/Local/...` 或 session 内运行日志

**Phase 4 当前最小结论：**

- 绿色版 EXE 已可打包并正常启动
- FFmpeg 随包策略已明确为 `tools/ffmpeg.exe` 优先
- 当前状态应表述为：**启动已验证，录制待实测**

**Phase 4 完整验收仍需补齐：**

- direct 模式最小录制验证
- video_then_frames 模式最小录制验证
- 停止流程验证
- `frames.csv` / `summary.txt` / `metadata.json` / 图片输出检查

**Phase 4 完整验收标准：**

- 绿色版可在无 Python 的 Windows 机器上直接运行
- FFmpeg 路径自动识别稳定
- direct / video_then_frames 两种模式至少各通过一轮真实录制
- 输出文件完整且可读
- 安装包可正常安装/卸载（后续阶段）

---

## Phase 5：产品化体验增强

**Objective:** 把软件从“工程工具”提升到“正式桌面应用”。

可选增强：

- 软件图标 / 版本信息 / 关于页
- 更清晰的错误提示
- 导出诊断包（log + metadata + summary）
- 自动保存上次输出目录与参数
- 首次运行检查 FFmpeg
- 更紧凑/更专业的界面布局
- 多页签设置页

这一阶段仍可以继续保留 Tkinter；如果 Tkinter 开始明显限制体验，再进入下一阶段。

---

## Phase 6：是否迁移 PySide6（单独立项，不混做）

**Objective:** 只在“需求和后端都稳定后”再评估 UI 框架迁移。

### 迁移前提

只有满足以下条件，才建议启动 PySide6 迁移：

- 后端模块化已经完成
- 采集/预览/统计逻辑已经稳定
- 打包发布流程已经固定
- 需要更专业的复杂桌面 UI
- 用户确认该软件会长期演进

### 迁移策略

不是“边修 bug 边迁 UI”，而是：

1. 保留现有 Tkinter 稳定版
2. 后端模块复用
3. 单开 `pyside_ui/` 或新分支做新前端
4. 仅替换界面壳，不重写采集核心

### 迁移后建议栈

```text
PySide6 + Python backend + PyInstaller --onedir + Inno Setup
```

也就是你发来的那份方案，但它应该属于 **Phase 6**，不是 **Phase 1**。

**Phase 6 验收标准：**

- 后端零重写或极少重写
- UI 迁移不破坏采集主链路
- 打包与发布可延续之前流程

---

## 推荐执行顺序（最实际版）

### 第一批（马上做）

1. 稳定长时间采集统计
2. 增加空间预警 / 收尾强化
3. 压低预览负载

### 第二批（结构化）

4. 拆 `paths.py`
5. 拆 `session_writer.py`
6. 拆 `stats_tracker.py`
7. 拆 `ffmpeg_runner.py`

### 第三批（可发布）

8. 做 `PyInstaller --onedir` 绿色版
9. 补 Windows 验证清单
10. 做 Inno Setup 安装包

### 第四批（再决定）

11. 评估是否迁 PySide6

---

## 一句话结论

**当前项目最优路线不是立刻重写成 PySide6，而是：先稳住 Tkinter + FFmpeg 主链路，先模块化、测试化、标准化打包，等后端成熟后再把 PySide6 作为第二阶段产品化升级。**
