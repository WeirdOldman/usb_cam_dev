# USB_CAM 项目交接说明

> 更新日期：2026-05-27
> 目的：让后续维护这个仓库的人直接站在当前有效主线上工作，而不是误读已经退休的 WebView 前端阶段。

## 1. 当前项目定义

这是一个面向 Windows 的 USB 摄像头采集工具，当前默认桌面主线固定为：

- `PySide6 + RuntimeController + FFmpeg DirectShow`
- 默认桌面入口：`desktop/main.py`
- 控制层 owner：`controller/runtime_controller.py`
- packaged runtime 一键验证入口：`validate_packaged_runtime.bat`

当前窗口分层约定：

- `PySide6` 负责标准桌面窗口与控件布局
- `RuntimeController` 负责配置、预览、采集、事件、快照与错误编排
- UI 不再通过 HTTP / WebSocket 驱动控制层

目标不是做通用相机平台，而是把固定能力链路做稳并保持可交付：

- 输入能力：`3840x2160 @ 25fps`
- 主采集链路：`FFmpeg + MJPEG`
- 输出形态：图片序列，或先录视频再拆帧

## 2. 当前基线

当前源码与验证基线如下：

- 本地路径：`E:\codex\usb_cam_dev`
- 分支：`main`
- 当前主测试：
  - `python -m pytest -q test_build_packaging.py test_runtime_controller.py test_desktop_main.py test_usb_cam_real_validation.py`
- 当前首批新增测试：
  - `test_runtime_controller.py`：控制层 contract 与动作逻辑
  - `test_desktop_main.py`：PySide6 主窗口与 automation 入口

当前仓库应被理解为：

**默认桌面主线已经切到 PySide6/controller packaged runtime，后续整理工作的重点是收口 owner、保持验证闭环，并彻底退休旧 WebView/FastAPI/React 口径。**

## 3. 当前关键入口

### 桌面入口

- `desktop/main.py`

负责：

- PySide6 主窗口创建
- 预览区 / 控制区 / 路径设置区
- packaged runtime automation CLI

### 控制层

- `controller/runtime_controller.py`

负责：

- 运行时状态
- 预览启停
- 采集开始 / 停止
- 配置更新
- 事件流与错误
- 快照生成

### 当前验证入口

- `test_build_packaging.py`
  - 打包脚本、依赖、工作流与退役约束
- `test_runtime_controller.py`
  - 控制层行为
- `test_desktop_main.py`
  - 桌面壳与 automation
- `test_usb_cam_real_validation.py`
  - 正式包验证逻辑

## 4. 当前文档权威边界

优先阅读这些当前文档：

1. `README.md`
2. `docs/CURRENT_PROJECT_STRUCTURE.md`
3. `docs/USB_CAM_STABILITY_POLICY.md`
4. `docs/requirements/WEBVIEW_PACKAGED_RUNTIME_QUICKSTART.md`
5. `docs/requirements/WEBVIEW_PACKAGED_RUNTIME_FINAL_VALIDATION_2026-05-26.md`
6. `docs/USB_CAM_PACKAGED_RUNTIME_PLAYBOOK.md`
7. 本文档

这些文档共同定义当前有效主线、构建方式、验证口径和目录边界。

## 5. 当前提交边界

应该进入版本库的内容：

- `desktop/`
- `controller/`
- `build.bat`
- `requirements-desktop.txt`
- `test_build_packaging.py`
- `test_runtime_controller.py`
- `test_desktop_main.py`
- `test_usb_cam_real_validation.py`
- `usb_cam_*.py`
- 当前有效的 `README.md` 与 `docs/`

不应作为源码提交的内容：

- `build/`
- `dist/`
- `outputs/`
- `_validation/`
- `capture_output/`
- `tools/`
- `__pycache__/`
- `.pytest_cache/`
- `*.log`

## 6. 当前仓库状态结论

本轮迁移之后，以下事实成立：

- `RuntimeController` 已成为唯一控制 owner
- 新桌面入口已切到 `desktop/main.py`
- packaged validation 已不再依赖 HTTP / WebSocket
- 旧 `ui/`、`build_webview.bat`、`requirements-pywebview.txt`、`backend/runtime_api.py`、`backend/main.py` 应视为已退休对象

## 7. 下次回来建议顺序

1. `git status`
2. `python -m pytest -q test_build_packaging.py test_runtime_controller.py test_desktop_main.py test_usb_cam_real_validation.py`
3. 阅读 `README.md`、`docs/CURRENT_PROJECT_STRUCTURE.md`、`docs/USB_CAM_STABILITY_POLICY.md`、`docs/USB_CAM_PACKAGED_RUNTIME_PLAYBOOK.md`
4. 再决定是继续压缩 owner，还是准备提交 / 发布

## 8. 当前最值得继续做的事

如果目标是继续清理：

1. 继续拆分 `controller/runtime_controller.py` 的剩余 owner
2. 继续拆分 `usb_cam_real_validation.py` 的 packaged / report / capture owner

如果目标是继续交付：

1. 整理当前变更提交范围
2. 重跑一轮 packaged runtime 实机验证
3. 再决定 tag / push / release

## 9. 一句话结论

**这个仓库现在应该只围绕当前 PySide6 packaged runtime 主线理解和维护，不应再把 WebView/FastAPI/React 阶段文件或前端残留当成活跃结构的一部分。**
