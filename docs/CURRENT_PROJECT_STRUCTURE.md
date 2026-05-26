# 当前项目结构

## 当前主线

当前默认桌面主线已经固定为：

- `PyWebView + FastAPI + React + FFmpeg DirectShow`
- 默认桌面入口：`backend/main.py`
- 前端源码目录：`ui/`
- 前端打包输出目录：`ui_dist/`
- 正式包构建入口：`build.bat`
- 前端静态资源构建入口：`build_webview.bat`

这个仓库当前已经不再以 Tk 单文件入口作为默认运行或验证口径。

## 版本库中应保留的核心源码

### 后端入口

- `backend/main.py`
  - PyWebView 窗口创建
  - FastAPI 路由
  - WebSocket 监控推送
  - 预览 / 采集控制 API

### Python 采集与运行时模块

- `usb_cam_capture.py`
  - 采集 / 录制 / 拆帧命令拼装
- `usb_cam_capture_context.py`
  - 当前会话上下文
- `usb_cam_capture_helpers.py`
  - 采集流程辅助逻辑
- `usb_cam_capture_state.py`
  - 采集状态缓存
- `usb_cam_ffmpeg.py`
  - FFmpeg 命令辅助函数
- `usb_cam_paths.py`
  - 路径与文件名辅助
- `usb_cam_preview.py`
  - 预览命令与预览进程控制
- `usb_cam_process.py`
  - FFmpeg 进程执行、停止与进度解析
- `usb_cam_runtime.py`
  - 两种采集模式的运行时编排
- `usb_cam_session_finalize.py`
  - 会话收尾与产物补写
- `usb_cam_session_writer.py`
  - `metadata.json` / `summary.txt` / `frames.csv`
- `usb_cam_stats.py`
  - 空间与统计辅助
- `usb_cam_stop_prefs.py`
  - AutoStop 默认策略
- `usb_cam_ui_state.py`
  - UI 指标与 UI action 翻译
- `usb_cam_real_validation.py`
  - 正式包 smoke / release / summary 验证

### 前端源码

- `ui/src/main.tsx`
  - 前端启动入口
- `ui/src/app/App.tsx`
  - 应用壳
- `ui/src/app/components/WinTitleBar.tsx`
  - 窗口标题栏
- `ui/src/app/components/MonitoringInterface.tsx`
  - 主界面装配
- `ui/src/app/components/monitoring/`
  - 当前监控页的实际组件与运行时 hook

前端模板残留目录 `ui/src/app/components/ui/` 与 `ui/src/app/components/figma/` 已清理，不再属于当前项目结构。

## 当前测试入口

- `test_build_packaging.py`
  - 打包脚本、前端结构与关键文档约束
- `test_backend_main.py`
  - FastAPI / PyWebView 主入口契约
- `test_usb_cam_real_validation.py`
  - 正式包验证逻辑
- `ui/src/app/components/monitoring/monitorRuntimeState.test.mjs`
  - 前端运行时文本与状态归一化

## 当前权威文档

- `README.md`
  - 项目概览、运行方式、构建与测试入口
- `docs/CURRENT_PROJECT_STRUCTURE.md`
  - 当前源码与目录边界
- `docs/USB_CAM_PROJECT_HANDOFF.md`
  - 当前接力上下文
- `docs/USB_CAM_STABILITY_POLICY.md`
  - 当前稳定性与 AutoStop 策略
- `docs/USB_CAM_PACKAGED_RUNTIME_PLAYBOOK.md`
  - 当前 packaged runtime 操作口径
- `docs/requirements/WEBVIEW_PACKAGED_RUNTIME_QUICKSTART.md`
  - packaged runtime 快速验证口径
- `docs/requirements/WEBVIEW_PACKAGED_RUNTIME_FINAL_VALIDATION_2026-05-26.md`
  - 最新正式包验证结论

## 本地依赖边界

`tools/` 目录属于本地运行依赖边界。

当前约束：

- `tools/` 用于放本地 `ffmpeg.exe`
- 它不受版本控制
- 它可以按机器环境单独准备
- 它不是源码 owner，也不应被当作仓库内长期演进的代码结构

## 不应提交的生成物

以下目录或文件属于可重建产物，不应作为源码保留：

- `build/`
- `dist/`
- `ui_dist/`
- `ui/dist/`
- `capture_output/`
- `outputs/`
- `_validation/`
- `tools/`
- `__pycache__/`
- `.pytest_cache/`
- `*.log`

这些内容用于本地构建、调试或验证，清理后可按当前脚本重新生成。
