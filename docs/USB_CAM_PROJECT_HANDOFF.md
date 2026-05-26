# USB_CAM 项目接力说明

> 更新日期：2026-05-26
> 目的：让后续继续维护这个仓库的人，直接站在当前有效主线上工作，而不是误读旧 Tk 阶段材料。

## 1. 当前项目定义

这是一个面向 Windows 的 USB 摄像头采集工具，当前默认桌面主线固定为：

- `PyWebView + FastAPI + React + FFmpeg DirectShow`
- 默认桌面入口：`backend/main.py`
- 前端源码目录：`ui/`
- 前端打包输出目录：`ui_dist/`
- 正式包构建入口：`build.bat`
- packaged runtime 一键验证入口：`validate_packaged_runtime.bat`

目标不是做通用相机平台，而是把固定能力链路做稳并保持可交付：

- 输入能力：`3840x2160 @ 25fps`
- 主采集链路：`FFmpeg + MJPEG`
- 输出形态：图片序列，或先录视频再拆帧

## 2. 当前基线

截至本次仓库整理，当前源码与验证基线如下：

- 本地路径：`E:\codex\usb_cam_dev`
- 分支：`main`
- 当前主测试：
  - `python -m pytest -q test_build_packaging.py test_backend_main.py test_usb_cam_real_validation.py`
  - 结果：`135 passed`
- 前端补充验证：
  - `node --test ui/src/app/components/monitoring/monitorRuntimeState.test.mjs`
  - 结果：`5 passed`
- 前端构建：
  - `npm run build`
  - 结果：通过

当前仓库应被理解为：

**默认桌面主线已稳定在 PyWebView/FastAPI/React packaged runtime，上游整理工作的重点是收口源码边界、保持验证闭环、避免再引入旧 Tk 口径。**

## 3. 当前关键入口

### 桌面入口

- `backend/main.py`

负责：

- PyWebView 窗口创建
- FastAPI 路由与 WebSocket
- 预览 / 采集控制 API
- 运行态快照与前端监控数据

### 关键模块

- `usb_cam_capture.py`
  - 采集 / 录制 / 拆帧命令构建
- `usb_cam_preview.py`
  - 预览命令、帧解析、preview 进程启停
- `usb_cam_process.py`
  - FFmpeg 进程执行、停止请求、进度解析
- `usb_cam_runtime.py`
  - 两种采集模式的编排
- `usb_cam_capture_helpers.py`
  - 采集流程辅助逻辑
- `usb_cam_session_writer.py`
  - `frames.csv` / `metadata.json` / `summary.txt`
- `usb_cam_session_finalize.py`
  - 会话收尾与产物补写
- `usb_cam_ui_state.py`
  - UI 指标与状态翻译
- `usb_cam_real_validation.py`
  - packaged smoke / release / summary 验证

### 当前测试入口

- `test_build_packaging.py`
  - 构建脚本、前端结构、当前文档边界
- `test_backend_main.py`
  - FastAPI / PyWebView 主入口契约
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

- `backend/`
- `ui/src/`
- `build.bat`
- `build_webview.bat`
- `requirements-pywebview.txt`
- `test_build_packaging.py`
- `test_backend_main.py`
- `test_usb_cam_real_validation.py`
- `usb_cam_*.py`
- 当前有效的 `README.md` 与 `docs/`

不应该作为源码提交的内容：

- `build/`
- `dist/`
- `ui/dist/`
- `ui_dist/`
- `outputs/`
- `_validation/`
- `capture_output/`
- `tools/`
- `__pycache__/`
- `.pytest_cache/`
- `*.log`

## 6. 当前仓库状态结论

本轮整理之后，以下事实成立：

- 前端模板残留目录 `ui/src/app/components/ui/` 已删除
- Figma 模板残留目录 `ui/src/app/components/figma/` 已删除
- 前端依赖已从模板工程依赖集收缩到当前实际使用集合
- 根目录旧 Tk 结构文档已移除
- 当前结构说明已迁移到 `docs/CURRENT_PROJECT_STRUCTURE.md`
- 运行态监控不再伪造随机 CPU / 码率 / 加速状态

## 7. 下次回来建议顺序

1. `git status`
2. `python -m pytest -q test_build_packaging.py test_backend_main.py test_usb_cam_real_validation.py`
3. `node --test ui/src/app/components/monitoring/monitorRuntimeState.test.mjs`
4. `npm run build`
5. 阅读 `README.md`、`docs/CURRENT_PROJECT_STRUCTURE.md`、`docs/USB_CAM_STABILITY_POLICY.md`、`docs/USB_CAM_PACKAGED_RUNTIME_PLAYBOOK.md`
6. 再决定是继续增强稳定性，还是准备提交 / 发布

## 8. 当前最值得继续做的事

如果目标是继续清理：

1. 继续归档或删除剩余历史阶段文档
2. 继续拆分 `backend/main.py` 与 `usb_cam_real_validation.py` 这两个大文件

如果目标是继续交付：

1. 整理当前变更提交范围
2. 重跑一次 packaged runtime 实机验证
3. 再决定 tag / push / release

## 9. 一句话结论

**这个仓库现在应该只围绕当前 WebView packaged runtime 主线理解和维护，不应该再把旧 Tk 阶段文件或模板前端残留当成活跃结构的一部分。**
