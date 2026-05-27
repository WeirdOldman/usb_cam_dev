# USB Cam 4K25

Windows USB 摄像头采集工具，当前默认桌面主线为 **PySide6 + RuntimeController + FFmpeg DirectShow + PyInstaller onedir**。
这个仓库的目标不是通用相机平台，而是稳定交付 `3840x2160 @ 25fps` 采集链路，并保持预览、开始/停止采集、两种输出模式、打包与真实验证都可维护。

## 当前能力

- 固定输入能力：`3840x2160 @ 25fps`
- 固定主采集链路：`FFmpeg DirectShow + MJPEG`
- 支持预览
- 支持开始 / 停止采集
- 支持两种采集模式：
  - `direct_frames`
  - `video_then_frames`
- 支持 session 产物输出：
  - `metadata.json`
  - `summary.txt`
  - `frames.csv`
- 支持 packaged runtime 验证、summary、manifest、history 与 checklist

## 当前技术边界

当前阶段刻意不做这些事：

- 不回退到 Tk
- 不保留 PyWebView / FastAPI / React 双主线
- 不改动 `4K25` 主采集能力
- 不改动 `FFmpeg DirectShow` 主链路
- 不做 PyInstaller onefile
- 不顺手扩展多摄像头、复杂图表或网络控制

## 主要入口

- 桌面入口：`desktop/main.py`
- 控制层 owner：`controller/runtime_controller.py`
- 打包 / 构建测试：`test_build_packaging.py`
- 控制层 / 桌面壳测试：`test_runtime_controller.py`、`test_desktop_main.py`
- 正式包与真实验证测试：`test_usb_cam_real_validation.py`

## 主要模块

- `controller/contracts.py`：运行时 dataclass contract
- `controller/runtime_controller.py`：采集、预览、配置、事件、快照与控制编排
- `desktop/main.py`：PySide6 主窗口与桌面自动化入口
- `desktop/automation.py`：打包后自动化驱动 helper
- `usb_cam_capture.py`：采集 / 录制 / 拆帧命令构建
- `usb_cam_preview.py`：预览命令、帧解析与预览进程
- `usb_cam_process.py`：FFmpeg 进程执行、停止与进度解析
- `usb_cam_runtime.py`：采集 metadata 与模式编排
- `usb_cam_capture_helpers.py`：采集流程辅助逻辑
- `usb_cam_session_writer.py`：`frames.csv` / `metadata.json` / `summary.txt`
- `usb_cam_session_finalize.py`：session 收尾与产物补全
- `usb_cam_ui_state.py`：采集指标与运行时状态计算
- `usb_cam_real_validation.py`：headless / packaged 验证入口

更多结构说明见：

- `docs/CURRENT_PROJECT_STRUCTURE.md`
- `docs/USB_CAM_PROJECT_HANDOFF.md`
- `docs/USB_CAM_STABILITY_POLICY.md`

## 运行要求

- Python 3.10+
- Windows
- 可用的 FFmpeg（DirectShow）
- 目标 USB 摄像头支持 `3840x2160 @ 25fps`

## 本地开发

### 运行测试

在仓库根目录执行：

```powershell
python -m py_compile `
  desktop/main.py `
  desktop/automation.py `
  controller/contracts.py `
  controller/runtime_controller.py `
  usb_cam_capture.py `
  usb_cam_capture_context.py `
  usb_cam_capture_helpers.py `
  usb_cam_capture_state.py `
  usb_cam_ffmpeg.py `
  usb_cam_paths.py `
  usb_cam_preview.py `
  usb_cam_process.py `
  usb_cam_real_validation.py `
  usb_cam_runtime.py `
  usb_cam_session_finalize.py `
  usb_cam_session_writer.py `
  usb_cam_stats.py `
  usb_cam_stop_prefs.py `
  usb_cam_ui_state.py `
  usb_cam_validation_capture.py `
  usb_cam_validation_packaged.py `
  usb_cam_validation_reports.py `
  test_build_packaging.py `
  test_runtime_controller.py `
  test_desktop_main.py `
  test_usb_cam_real_validation.py

python -m pytest -q test_build_packaging.py test_runtime_controller.py test_desktop_main.py test_usb_cam_real_validation.py
```

## 打包

当前只支持：

- **PyInstaller `--onedir`**
- **Windows**
- **桌面入口 `desktop/main.py`**

### Windows 打包入口

```bat
build.bat
```

### 打包关键点

- App 名称：`USB_Cam_4K25`
- 主入口：`desktop/main.py`
- 打包输出目录：`dist/USB_Cam_4K25/`
- 便携 FFmpeg 自动复制到：
  - `dist/USB_Cam_4K25/tools/ffmpeg.exe`

### 打包后验证

参考：

- `docs/requirements/WEBVIEW_PACKAGED_RUNTIME_QUICKSTART.md`
- `docs/requirements/WEBVIEW_PACKAGED_RUNTIME_FINAL_VALIDATION_2026-05-26.md`
- `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`
- `docs/USB_CAM_PACKAGED_RUNTIME_PLAYBOOK.md`

### 本地 `tools/` 边界

`tools/` 目录用于放本机运行依赖，例如 `tools/ffmpeg.exe`。
它的定位是：

- 本地运行依赖目录
- 不受版本控制
- 可按机器环境单独准备

真实打包或真实采集验证时，优先准备：

- `tools/ffmpeg.exe`

## 当前维护重点

当前更值得继续做的是：

1. 继续压缩 `controller/runtime_controller.py` 内的 owner 边界
2. 继续拆分 `usb_cam_real_validation.py` 的 packaged / capture / summary owner
3. 保持 packaged runtime 回归与交付口径稳定
4. 清理不再需要的历史文档与旧验证痕迹

## 开发原则

- 新桌面主线优先：PySide6 + RuntimeController
- 不回退到旧 Tk 主线
- 先稳采集链路，再做结构整理
- 小步重构，每一步都要能回归验证
- 不在结构整理时顺手扩功能

## 仓库地址

- GitHub: https://github.com/WeirdOldman/usb_cam_dev
