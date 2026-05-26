# USB_CAM 项目接力说明

> 更新日期：2026-05-26
> 目的：让下次回来继续做的人，可以在 5 分钟内重新进入当前真实状态，而不是误读旧 Tk 主线信息。

## 1. 这个项目现在是什么

这是一个面向 Windows 的 USB 摄像头采集工具，当前默认桌面主线已经固定为：

- PyWebView UI shell
- FastAPI backend bridge
- React/Vite frontend
- FFmpeg DirectShow 采集
- PyInstaller `--onedir` 打包

当前目标不是做通用相机平台，而是把一条稳定可交付的固定链路做稳：

- 输入能力：`3840x2160 @ 25fps`
- 采集链路：`FFmpeg + MJPEG`
- 输出形态：图片序列，或先录视频再拆帧

## 2. 当前真实状态

截至 2026-05-26，本地仓库基线与最新验证结论如下：

- 本地路径：`E:\codex\usb_cam_dev`
- 分支：`main`
- 默认桌面入口：`backend/main.py`
- 前端静态资源构建入口：`build_webview.bat`
- 正式包构建入口：`build.bat`

最新自动测试：

- `python -m pytest -q test_build_packaging.py test_backend_main.py test_usb_cam_real_validation.py`
- 结果：`123 passed`

最新正式包验证：

- `validate_packaged_runtime.bat`：通过
- `--packaged-runtime-smoke-only`：通过
- `--packaged-release-validation-only`：通过
- `--packaged-validation-summary-only`：通过
- 最新 summary release gate：`ready`

最新正式包验证证据：

- 最新 one-shot run：
  - `E:\codex\usb_cam_dev\outputs\packaged_runtime\2026-05-26_084944\packaged_validation_summary_report.json`
- 最新 packaged validation index：
  - `E:\codex\usb_cam_dev\outputs\packaged_runtime\latest_packaged_validation.json`
- 最新独立 summary 报告：
  - `E:\codex\outputs\packaged_runtime\packaged_validation_summary_report.json`
- 最新 release 产物目录：
  - `E:\codex\outputs\packaged_release\direct_frames_mjpeg_4k_20260526_085200`

换句话说，项目现在的准确表述应是：

**PyWebView/FastAPI/React 正式包链路已再次通过完整验证，当前重点从“证明能跑”转到“整理提交边界并准备交付”。**

## 3. 现在不要做什么

短期内明确不要扩到这些方向：

- 不迁移到 PySide6
- 不转 C#
- 不改主采集路线
- 不做 onefile
- 不在已验证主线上贸然引入高风险重构

当前最值钱的工作不是继续改 UI，而是：

1. 把这轮新桌面主线代码和文档整理成清晰可提交范围
2. 确认 legacy Tk 残留不再出现在默认入口与默认测试口径里
3. 在交付提交完成后，再决定是否继续做 Tk 旧层彻底退役

## 4. 当前入口与关键模块

### 默认桌面入口

- `backend/main.py`

这个入口当前负责：

- PyWebView 窗口创建
- 前端静态资源定位
- FastAPI 路由与 WebSocket
- 预览 / 采集控制 API
- 运行态快照与 UI 可观测性

### 当前关键模块

- `usb_cam_capture.py`
  - 采集 / 录制 / 拆帧命令构建

- `usb_cam_preview.py`
  - 预览命令、帧流解析、preview 进程启停

- `usb_cam_process.py`
  - FFmpeg 进程执行、停止请求、进度解析

- `usb_cam_runtime.py`
  - 两种采集模式的运行时编排

- `usb_cam_session_writer.py`
  - session 目录创建
  - `frames.csv`
  - `metadata.json`
  - `summary.txt`

- `usb_cam_session_finalize.py`
  - session 收尾与产物落盘

- `usb_cam_real_validation.py`
  - 正式包 smoke / release / summary 验证
  - packaged validation report / manifest / checklist 输出

- `usb_cam_capture_helpers.py`
  - 采集辅助胶水逻辑

- `usb_cam_capture_state.py`
  - 运行期状态缓存

- `usb_cam_capture_context.py`
  - 当前 session 上下文

- `usb_cam_ui_state.py`
  - UI 指标与 action 翻译

### 当前测试入口

- `test_build_packaging.py`
  - 打包脚本 / quickstart / 验证入口约束

- `test_backend_main.py`
  - WebView/FastAPI 主入口与 API 契约

- `test_usb_cam_real_validation.py`
  - 正式包验证与真实采集验证逻辑

## 5. 正式包验证口径

当前推荐只用新的 packaged validation 口径，不再回退到旧 Tk 的打包与手工口径。

### 构建

- `build.bat`

作用：

1. 构建 `E:\codex\ui`
2. 同步静态资源到 `E:\codex\usb_cam_dev\ui_dist`
3. 使用 PyInstaller 打包 `backend/main.py`

### One-shot packaged validation

- `validate_packaged_runtime.bat`

作用：

1. 先重打正式包
2. 再跑 packaged validation summary
3. 输出 run dir / report / manifest / checklist / release gate

### 独立 CLI 验证

- smoke：
  - `python usb_cam_real_validation.py --packaged-runtime-smoke-only ...`
- release：
  - `python usb_cam_real_validation.py --packaged-release-validation-only ...`
- summary：
  - `python usb_cam_real_validation.py --packaged-validation-summary-only ...`

## 6. 当前提交边界

现在最需要记住的是：**生成物和源码要严格分开。**

应该进入版本库的东西：

- `backend/`
- `build.bat`
- `build_webview.bat`
- `USB_Cam_4K25.spec`
- `requirements-pywebview.txt`
- `test_build_packaging.py`
- `test_backend_main.py`
- `test_usb_cam_real_validation.py`
- `usb_cam_real_validation.py`
- `README.md`
- `docs/requirements/*.md`
- 其他本轮真实源码与文档修改

不应该进入版本库的东西：

- `dist/`
- `build/`
- `outputs/`
- `capture_output/`
- `ui_dist/`
- `tools/`
- `*.log`

当前 `.gitignore` 已经按这个方向收口。

## 7. Tk legacy 现状

当前默认桌面入口已经不再依赖 Tk。

这轮工作树里，以下 Tk-only 文件已经从当前主线中移除：

- `usb_burst_cam_4k25_manual_v1_6_3.py`
- `usb_cam_preview_helpers.py`
- `usb_cam_queue_helpers.py`
- `usb_cam_finalize.py`
- `test_usb_cam_refactor.py`

这说明“Tk 不再是默认主线”已经不仅是口头状态，而是工作树级别的实际变更。

但要注意：

- 仓库里仍然有不少历史文档引用旧 Tk 入口和旧测试文件
- 如果下一步继续演进，优先做的是清理这些历史文档口径，而不是重新引入 Tk 逻辑

## 8. 下次回来第一步该做什么

按这个顺序最稳：

1. `git status`
2. `python -m pytest -q test_build_packaging.py test_backend_main.py test_usb_cam_real_validation.py`
3. 读取以下文件：
   - `README.md`
   - `docs/requirements/WEBVIEW_PACKAGED_RUNTIME_QUICKSTART.md`
   - `docs/requirements/WEBVIEW_PACKAGED_RUNTIME_FINAL_VALIDATION_2026-05-26.md`
   - `docs/requirements/TK_LEGACY_RETIREMENT_PLAN_2026-05-25.md`
   - 本文档
4. 检查 `latest_packaged_validation.json` 和最新 run dir
5. 再决定是进入交付提交，还是继续做 legacy Tk 清退

## 9. 真正值得继续推进的下一刀

如果目标是交付：

1. 整理并提交当前源码与文档
2. 复查是否还需要补发布说明
3. 再考虑 tag / push / release

如果目标是继续演进：

1. 先清理历史文档里的旧 Tk 口径
2. 对照 `TK_LEGACY_RETIREMENT_PLAN_2026-05-25.md` 核对剩余 legacy 清理项
3. 继续增强长时间采集稳定性、运行期护栏和交付可观测性

## 10. 一句话结论

**这个项目现在最合理的接力方式，不是回到 Tk 主线，而是基于已经验证通过的 PyWebView/FastAPI/React 正式包主线，先完成提交与交付，再决定是否继续做 Tk legacy 彻底清退。**
