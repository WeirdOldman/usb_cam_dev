# USB_CAM Stability Policy

## 范围

本文档描述 `usb_cam_dev` 当前默认桌面主线的稳定性策略，适用范围是：

- `PyWebView + FastAPI + React`
- `backend/main.py` 作为默认桌面入口
- `FFmpeg DirectShow + MJPEG`
- `PyInstaller --onedir`

本文档不讨论旧 Tk 入口的保留策略；当前仓库的稳定性口径已经切到现行 WebView runtime。

## 当前稳定性目标

当前阶段的目标不是扩功能，而是让已经验证通过的采集链路更稳、更可观测、更容易交付。

默认仍保留这些产品边界：

- 固定 `3840x2160 @ 25fps`
- 固定 `FFmpeg DirectShow + MJPEG`
- 保留 `direct_frames` 与 `video_then_frames`
- 保留 `PyInstaller --onedir`
- 不引入 onefile / 多摄像头 / 复杂可视化

## 当前已验证基线

当前基线以新的 packaged runtime 为准，关键证据见：

- `docs/requirements/WEBVIEW_PACKAGED_RUNTIME_QUICKSTART.md`
- `docs/requirements/WEBVIEW_PACKAGED_RUNTIME_FINAL_VALIDATION_2026-05-26.md`
- `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`

现行验证口径覆盖：

- packaged GUI 启动
- packaged preview start / stop
- packaged `direct_frames`
- packaged `video_then_frames`
- packaged stop-flow closure
- 中文路径与空格路径
- packaged validation summary / manifest / checklist

## 当前稳定性 owner

当前稳定性相关逻辑主要分布在这些文件：

- `backend/main.py`
  - 运行时入口、控制 API、WebSocket 推送
- `usb_cam_capture_helpers.py`
  - 采集执行中的日志、异常和 timer tick
- `usb_cam_stop_prefs.py`
  - AutoStop 默认参数
- `usb_cam_runtime.py`
  - 采集 metadata 与模式编排
- `usb_cam_session_finalize.py`
  - 结束收尾与产物落盘
- `usb_cam_ui_state.py`
  - UI 侧运行态指标
- `usb_cam_real_validation.py`
  - smoke / release / summary 验证

## AutoStop 策略

当前 AutoStop 目标很保守：不是追求“聪明”，而是避免长时间采集在明显风险出现后继续静默运行。

当前默认启用的保护规则：

- `enabled = True`
- `min_disk_free_mb_hard = 5120.0`

当前仍未默认启用：

- `max_duration_s`
- `min_effective_fps_ratio`

原因很简单：

- 磁盘硬阈值是最稳定、最容易解释的安全信号
- 时长上限与 FPS 阈值更容易误伤真实业务录制
- 它们需要更强的真实设备证据，才能升级成默认规则

## 运行时可观测性要求

任何稳定性改动，都不应削弱这些基础可观测性：

- 当前阶段与状态文本能从 UI 读到
- 最新事件流能从 WebSocket 和事件列表读到
- `metadata.json`、`summary.txt`、`frames.csv` 能落盘
- packaged validation report / manifest / checklist 能输出

如果改动让错误更隐蔽、让日志更少、或者让失败更难复现，就不算稳定性改进。

## 何时必须重跑验证

以下改动至少需要重跑定向验证：

- stop-flow 行为变化
- metadata / summary 合同变化
- AutoStop 默认值变化
- preview / capture 时序变化
- `video_then_frames` 输出语义变化
- packaged runtime 构建脚本变化
- 前端监控状态字段变化

最低重放口径：

- 一轮 `direct_frames`
- 一轮 `video_then_frames`
- 一轮 stop-flow 检查

如果改动触及默认 AutoStop 阈值，还要额外补：

- 一轮故意触发该阈值的验证
- 一轮正常录制，证明阈值不会过早误触发

## 当前原则

当前项目的稳定性原则保持为：

1. 先让现行 WebView runtime 更可观测
2. 再增加简单、明确、可解释的安全停机
3. 最后才考虑更重的结构或存储策略变化

一句话总结：

**当前稳定性策略是：保持已验证的 `backend/main.py` 主线不漂移，优先增强可观测性，并且只在证据充足时才扩大自动停机默认规则。**
