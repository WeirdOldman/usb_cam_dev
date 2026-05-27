# 当前项目结构

## 当前主线

当前默认桌面主线已经固定为：

- `PySide6 + RuntimeController + FFmpeg DirectShow`
- 默认桌面入口：`desktop/main.py`
- 控制层 owner：`controller/runtime_controller.py`
- 正式包构建入口：`build.bat`

这个仓库当前已经不再把 `PyWebView + FastAPI + React` 视为有效运行主线。

## 版本库中应保留的核心源码

### 桌面入口

- `desktop/main.py`
  - PySide6 主窗口
  - 预览区、控制区、路径/设置区
  - 桌面自动化 CLI 入口

- `desktop/automation.py`
  - packaged runtime 自动化驱动 helper

### 控制层

- `controller/contracts.py`
  - 运行时 dataclass contract

- `controller/runtime_controller.py`
  - 配置、预览、采集、快照、事件与错误 owner

### Python 采集与运行时模块

- `usb_cam_capture.py`
  - 采集 / 录制 / 拆帧命令构建
- `usb_cam_capture_context.py`
  - 当前会话上下文
- `usb_cam_capture_helpers.py`
  - 采集流程辅助逻辑
- `usb_cam_capture_state.py`
  - 采集状态缓存
- `usb_cam_ffmpeg.py`
  - FFmpeg 命令辅助
- `usb_cam_paths.py`
  - 路径与文件名辅助
- `usb_cam_preview.py`
  - 预览命令、帧解析与预览进程控制
- `usb_cam_process.py`
  - FFmpeg 进程执行、停止与进度解析
- `usb_cam_runtime.py`
  - 两种采集模式的运行时编排
- `usb_cam_session_finalize.py`
  - 会话收尾与产物补全
- `usb_cam_session_writer.py`
  - `metadata.json` / `summary.txt` / `frames.csv`
- `usb_cam_stats.py`
  - 空间与统计辅助
- `usb_cam_stop_prefs.py`
  - AutoStop 默认策略
- `usb_cam_ui_state.py`
  - 运行时指标与状态计算
- `usb_cam_real_validation.py`
  - 正式包 smoke / release / summary 验证入口
- `usb_cam_validation_capture.py`
  - capture / autostop 验证 owner
- `usb_cam_validation_packaged.py`
  - packaged runtime 验证 owner
- `usb_cam_validation_reports.py`
  - report / manifest / history / checklist owner

## 当前测试入口

- `test_build_packaging.py`
  - 打包脚本、依赖、工作流与退役约束
- `test_runtime_controller.py`
  - 控制层 contract 与动作逻辑
- `test_desktop_main.py`
  - PySide6 主窗口与桌面自动化入口
- `test_usb_cam_real_validation.py`
  - 正式包与真实验证逻辑

## 当前权威文档

- `README.md`
  - 项目概览、运行方式、构建与测试入口
- `docs/CURRENT_PROJECT_STRUCTURE.md`
  - 当前源码与目录边界
- `docs/USB_CAM_PROJECT_HANDOFF.md`
  - 当前接力上下文
- `docs/USB_CAM_STABILITY_POLICY.md`
  - 当前稳定性与验证边界
- `docs/USB_CAM_PACKAGED_RUNTIME_PLAYBOOK.md`
  - packaged runtime 操作口径
- `docs/requirements/PACKAGED_RUNTIME_QUICKSTART.md`
  - packaged runtime 快速验证口径
- `docs/requirements/PACKAGED_RUNTIME_FINAL_VALIDATION_2026-05-26.md`
  - 最新正式包验证记录

## 本地依赖边界

`tools/` 目录属于本地运行依赖边界。
当前约束：

- `tools/` 用于放本地 `ffmpeg.exe`
- 它不受版本控制
- 它不是源码 owner，也不应被当作仓库内长期演进的代码结构

## 不应提交的生成物

以下目录或文件属于可重建产物，不应作为源码保留：

- `build/`
- `dist/`
- `capture_output/`
- `outputs/`
- `_validation/`
- `tools/`
- `__pycache__/`
- `.pytest_cache/`
- `*.log`

这些内容用于本地构建、调试或验证，清理后可按当前脚本重新生成。
