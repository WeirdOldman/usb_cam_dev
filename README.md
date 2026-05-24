# USB Cam 4K25

Windows USB 摄像头采集工具，当前技术路线固定为 **Tkinter + FFmpeg DirectShow + PyInstaller onedir**。

目标不是做一个通用相机框架，而是把现有 `3840x2160 @ 25fps` 采集流程稳定下来，并逐步从单文件工具演进成可维护、可打包、可交付的桌面应用。

## 当前能力

- 固定摄像头能力：`3840x2160 @ 25fps`
- 固定主采集路线：`FFmpeg DirectShow + MJPEG`
- 支持预览
- 支持开始 / 停止采集
- 支持两种采集模式：
  - 直接输出图片序列
  - 先录视频再拆帧
- 支持 session 产物输出：
  - metadata
  - summary
  - frames.csv
- 已有针对长时间采集的统计优化与回归测试

## 当前技术边界

当前阶段刻意**不做**这些事：

- 不迁移到 PySide6
- 不修改 4K25 摄像头主能力
- 不修改 FFmpeg 主采集路线
- 不做 PyInstaller onefile
- 不扩展无关功能（多摄像头、复杂图表、网络控制等）

如果要继续迭代，优先做稳定性增强、运行期护栏、长时间采集韧性和交付口径统一。

## 主要文件

### 入口与测试

- 主入口：`usb_burst_cam_4k25_manual_v1_6_3.py`
- 回归测试：`test_usb_cam_refactor.py`

### 当前模块结构

- `usb_cam_paths.py`：路径与文件名辅助
- `usb_cam_session_writer.py`：session 产物写入
- `usb_cam_stats.py`：尺寸 / FPS / 统计
- `usb_cam_ffmpeg.py`：FFmpeg 命令拼装
- `usb_cam_preview.py`：预览链路与帧处理
- `usb_cam_capture.py`：采集 / 拆帧命令构建
- `usb_cam_process.py`：FFmpeg 进程执行与停止
- `usb_cam_runtime.py`：采集流程编排
- `usb_cam_ui_state.py`：UI 指标与 queue action
- `usb_cam_finalize.py`：capture_done 状态收尾
- `usb_cam_session_finalize.py`：session 结束时产物收尾
- `usb_cam_capture_helpers.py` / `usb_cam_preview_helpers.py` / `usb_cam_queue_helpers.py`：当前主类外移的辅助逻辑

更详细的结构说明见：

- `USB_CAM_REFACTOR_STRUCTURE.md`
- `USB_CAM_REFACTOR_ROADMAP.md`
- `docs/USB_CAM_STABILITY_POLICY.md`

## 运行要求

建议环境：

- Python 3.10+
- Windows
- 可用的 FFmpeg（DirectShow）
- 目标 USB 摄像头支持 `3840x2160 @ 25fps`

> 说明：当前仓库是在 Linux/Hermes 环境里做代码整理与测试回归，但应用目标仍然是 Windows 桌面采集场景。

## 本地开发

### 运行测试

在仓库根目录执行：

```bash
python3 -m py_compile \
  usb_burst_cam_4k25_manual_v1_6_3.py \
  usb_cam_capture_helpers.py \
  usb_cam_preview_helpers.py \
  usb_cam_queue_helpers.py \
  usb_cam_capture_state.py \
  usb_cam_capture_context.py \
  usb_cam_ui_state.py \
  usb_cam_finalize.py \
  usb_cam_session_finalize.py \
  usb_cam_runtime.py \
  usb_cam_process.py \
  usb_cam_capture.py \
  usb_cam_preview.py \
  usb_cam_ffmpeg.py \
  usb_cam_stats.py \
  usb_cam_session_writer.py \
  usb_cam_paths.py \
  usb_cam_stop_prefs.py \
  usb_cam_real_validation.py \
  test_usb_cam_refactor.py \
  test_usb_cam_real_validation.py

pytest -q test_usb_cam_refactor.py test_usb_cam_real_validation.py
```

## 打包

当前只支持：

- **PyInstaller `--onedir`**
- **无 installer**
- **无 onefile**

### Windows 打包入口

```bat
build.bat
```

### 打包关键点

- App 名称：`USB_Cam_4K25`
- 主入口：`usb_burst_cam_4k25_manual_v1_6_3.py`
- spec 文件：`USB_Cam_4K25.spec`
- 打包输出目录默认：`dist/USB_Cam_4K25/`
- 如果要随包分发便携 FFmpeg，放到：
  - `dist/USB_Cam_4K25/tools/ffmpeg.exe`

### 打包后验证

参考：

- `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`
- `docs/USB_CAM_MANUAL_VALIDATION_CHECKLIST.md`
- `docs/USB_CAM_PHASE4_TASK3_1_FIRST_BUILD_GUIDE.md`
- `docs/USB_CAM_PHASE4_TASK3_2_FIRST_BUILD_RECORD_TEMPLATE.md`
- `docs/USB_CAM_PHASE4_TASK3_3_WINDOWS_RUN_PACKAGE.md`

## 当前项目状态

这个仓库已经完成：

- 项目目录清理
- git 初始化
- `main` 分支建立
- GitHub 托管接通
- 核心逻辑完成一轮渐进式模块化拆分
- 自动回归测试可运行

当前更适合继续做的是：

1. README / 文档口径统一
2. 长时间采集稳定性增强
3. 打包回归验证与后续 soak
4. 后续 issue 化管理

## 开发原则

这个项目当前遵循的原则：

- 先保留 Tkinter + FFmpeg 路线
- 先稳主链路，再谈 UI 框架迁移
- 先拆纯后端，再拆 UI 壳层
- 小步重构，每一步都要能回归验证
- 不在结构整理时顺手扩功能

## 仓库地址

- GitHub: https://github.com/WeirdOldman/usb_cam_dev
