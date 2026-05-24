# USB_CAM 项目接力说明

> 更新日期：2026-05-24
> 目的：让下次回来继续做的人，可以在 5 分钟内重新进入上下文。

## 1. 这个项目现在是什么

这是一个面向 Windows 的 USB 摄像头采集工具，当前主线固定为：

- Tkinter UI
- FFmpeg DirectShow 采集
- PyInstaller `--onedir` 打包

当前目标不是做通用相机平台，而是把一条稳定可交付的固定链路做稳：

- 输入能力：`3840x2160 @ 25fps`
- 采集链路：`FFmpeg + MJPEG`
- 输出形态：图片序列，或先录视频再拆帧

## 2. 当前真实状态

截至 2026-05-24，本地仓库状态与代码基线如下：

- 本地路径：`E:\codex\usb_cam_dev`
- 分支：`main`
- 最近一次本地验证：
  - `python -m pytest -q test_usb_cam_refactor.py test_usb_cam_real_validation.py`
  - 结果：`35 passed`
  - `python -m py_compile ...` 通过

工程层面已经稳定，`2026-05-24` 已完成 packaged GUI、preview、`direct_frames`、`video_then_frames`、stop flow、中文/空格路径、短多轮与 5 分钟双模式稳定性验证。

换句话说，项目现在的准确表述应是：

**Phase 4 packaged 录制闭环已完成，下一阶段进入稳定性增强。**

## 3. 现在不要做什么

短期内明确不要扩到这些方向：

- 不迁移到 PySide6
- 不转 C#
- 不改主采集路线
- 不做 onefile
- 不在已验证主线上贸然引入高风险重构

这个项目下一刀最值钱的工作，不是“再拆几个文件”，而是提升长时间采集时的可观测性、自动保护和磁盘韧性。

## 4. 入口文件和关键模块

### 主入口

- `usb_burst_cam_4k25_manual_v1_6_3.py`

这个文件现在主要负责：

- Tkinter 窗口和控件
- 用户操作入口
- 线程启动
- 预览与采集流程的调度
- UI 定时刷新
- 收尾时把各模块拼起来

### 支撑模块

- `usb_cam_paths.py`
  - 应用根目录判断
  - FFmpeg 查找策略
  - 文件名前缀清洗

- `usb_cam_session_writer.py`
  - session 目录创建
  - `frames.csv`
  - `metadata.json`
  - `summary.txt`

- `usb_cam_stats.py`
  - 目录大小统计
  - MB 换算
  - 帧统计
  - 磁盘剩余空间预警

- `usb_cam_ffmpeg.py`
  - FFmpeg 命令片段拼装
  - preview / record 相关命令格式化

- `usb_cam_capture.py`
  - 采集与拆帧命令构建
  - `direct_frames`
  - `record_video`
  - `extract_frames`

- `usb_cam_preview.py`
  - 预览命令
  - PNG 帧流解析
  - preview 进程启停

- `usb_cam_process.py`
  - FFmpeg 进程执行
  - 进度行解析
  - 手动停止请求

- `usb_cam_runtime.py`
  - 采集元数据骨架
  - 两种录制模式的运行时编排

- `usb_cam_ui_state.py`
  - UI 统计值计算
  - queue 消息翻译为 UI action

- `usb_cam_finalize.py`
  - `capture_done` 后刷新最终帧数和空间占用

- `usb_cam_session_finalize.py`
  - session 收尾
  - 写最终 metadata / summary / csv

- `usb_cam_capture_helpers.py`
  - 把主文件里与采集相关的胶水逻辑继续外移

- `usb_cam_preview_helpers.py`
  - 预览相关的 UI 胶水逻辑

- `usb_cam_queue_helpers.py`
  - queue 单次消费与 action 分发

### 状态对象

- `usb_cam_capture_state.py`
  - 运行期状态缓存
  - 包含帧数、FPS、扫描时间、session 大小缓存、低磁盘日志标记

- `usb_cam_capture_context.py`
  - 当前 session 的上下文
  - 包含 `current_session` / `current_frames_dir` / `current_video_dir`
  - 包含 `current_meta` 与 `log_writer`

## 5. 主流程怎么走

### 预览流程

1. `App.start_preview()`
2. `find_ffmpeg()` 找 FFmpeg
3. `prepare_preview_start()` 生成 preview 命令
4. `start_preview_process()` 启动 preview 进程
5. `preview_reader()` 读取 stdout PNG 流
6. `preview_stderr_reader()` 读取 stderr 状态文本
7. 两类消息进入 `ui_queue`
8. `process_queue()` 周期消费消息并刷新 UI

### 采集流程

1. `App.start_capture()`
2. 若预览还在跑，先停预览
3. `prepare_capture_session()` 创建 session 目录、日志写入器、基础 metadata
4. 启动 worker 线程 `worker_capture()`
5. `execute_capture_pipeline()` 根据模式进入运行时编排

### 采集模式 A：`direct_frames`

执行顺序：

1. 构建 FFmpeg 直出图片命令
2. `run_process()` 执行
3. FFmpeg 进度通过 stdout 进入帧计数
4. 停止时请求 FFmpeg 收尾
5. 结束后 `finish_session()`

### 采集模式 B：`video_then_frames`

执行顺序：

1. 先录到 `video/capture_4k25_mjpeg.avi`
2. 如果视频文件存在且大小大于 0，执行拆帧
3. 先尝试 copy 模式拆帧
4. 若拆帧后帧目录仍为空，再回退到 `q=2` 模式拆帧
5. 若勾选“拆帧后删除中间视频”且已成功产出帧，则删除 AVI
6. 最后 `finish_session()`

### 收尾流程

1. `finalize_session()`
2. 写 `frames.csv`
3. 计算帧数、平均大小、估算每分钟空间
4. 写 `metadata.json`
5. 写 `summary.txt`
6. 刷新 session 总大小
7. worker 结束后通过 queue 发 `capture_done`
8. UI 线程执行最终状态刷新

## 6. UI 消息流

线程边界是这个项目最需要记住的东西之一。

### 后台线程会往 `ui_queue` 放的消息

- `preview_frame`
- `preview_status`
- `preview_stopped`
- `ffmpeg_frame`
- `capture_done`

### UI 线程消费方式

- `App.process_queue()` 每 100ms 跑一次
- `usb_cam_queue_helpers.process_queue_once()` 单次消费
- `usb_cam_ui_state.process_ui_message()` 把消息翻译成 UI action
- `App.dispatch_ui_action()` 再把 action 打到真实控件更新

这意味着：

- UI 刷新尽量不要直接从 worker 线程碰控件
- 如果后面继续改功能，优先延续 queue + action 这条边界

## 7. session 产物长什么样

每次采集都会创建一个 session 目录，里面至少会有：

- `frames/`
- `video/`
- `run_log.txt`
- `frames.csv`
- `metadata.json`
- `summary.txt`

如果是 `direct_frames`，核心产物在 `frames/`。
如果是 `video_then_frames`，会先产出 `video/capture_4k25_mjpeg.avi`，再拆帧。

## 8. 当前测试覆盖到了什么

`test_usb_cam_refactor.py` 已经覆盖的重点，主要是纯后端和胶水层逻辑：

- FFmpeg 路径查找
- session 目录创建
- metadata / summary / csv 输出契约
- 统计逻辑
- FFmpeg progress 解析
- runtime 模式编排
- 停止与回调路径
- UI 消息分发与状态计算

它已经足够保护“重构不把主逻辑拆坏”，但仍不能完全替代更大范围现场环境验证：

- 没覆盖真实 DirectShow 设备差异
- 没覆盖真实 Windows EXE 录制行为
- 没覆盖实际磁盘与路径环境差异

## 9. 下次回来第一步该做什么

按这个顺序最稳：

1. `git status`
2. `python -m pytest -q test_usb_cam_refactor.py`
3. 读取以下文档：
   - `docs/USB_CAM_PHASE4_CURRENT_STATUS_NOTE.md`
   - `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`
   - `docs/USB_CAM_MANUAL_VALIDATION_CHECKLIST.md`
   - 本文档
4. 对照最新 RC 文档确认当前验证范围
5. 在触及长录制逻辑后补跑定向 packaged/manual replay

## 10. 真正值得继续推进的下一刀

如果目标是让项目继续向“可交付”前进，优先级建议如下：

### P1

在已通过主线上继续补稳定性护栏：

- 更完整的运行时健康指标
- 自动停机条件
- 长录制磁盘策略

### P2

只有在增强后复测发现真实问题，再做针对性修补：

- 停止收尾不完整
- FFmpeg 路径识别异常
- 打包后资源定位问题
- 低磁盘提示文案或阈值调整

### P3

P1、P2 之后再考虑：

- 文档补齐
- 发布说明
- 安装包
- UI 升级路线评估

## 11. 推荐把哪些文件当成“第一层上下文”

如果只想快速重新进入项目，不要一上来读全仓库，先读这几份：

- `README.md`
- `USB_CAM_REFACTOR_ROADMAP.md`
- `USB_CAM_REFACTOR_STRUCTURE.md`
- `docs/USB_CAM_PHASE4_CURRENT_STATUS_NOTE.md`
- `docs/USB_CAM_DEV_PAUSE_CHECKPOINT_2026-05-07.md`
- `docs/USB_CAM_PROJECT_HANDOFF.md`

## 12. 一句话结论

**这个项目现在最合理的接力方式，不是继续重构，而是在已验证的 `v1.6.4` 主线之上补齐“看得见风险、到阈值能安全停”的稳定性护栏。**
