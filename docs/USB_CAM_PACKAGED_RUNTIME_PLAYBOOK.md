# USB_CAM Packaged Runtime Playbook

## 目的

这份文档取代旧的 `USB_CAM_PHASE4_TASK3_1_FIRST_BUILD_GUIDE.md`、
`USB_CAM_PHASE4_TASK3_2_FIRST_BUILD_RECORD_TEMPLATE.md` 和
`USB_CAM_PHASE4_TASK3_3_WINDOWS_RUN_PACKAGE.md`。

它只服务当前主线：

- `PyWebView + FastAPI + React`
- `backend/main.py`
- `PyInstaller --onedir`

## 本地依赖边界

当前仓库中的 `tools/` 目录属于**本地运行依赖边界**，不是版本控制边界。

含义很明确：

- `tools/` 可以放本机要用的 `ffmpeg.exe`
- 它用于本地构建、真实采集和 packaged runtime 验证
- 它不应作为源码提交
- 不同机器可以有不同的本地 `tools/` 内容

如果你要跑真实验证，优先准备：

- `E:\codex\usb_cam_dev\tools\ffmpeg.exe`

`build.bat` 会在构建时尝试把它复制到：

- `dist/USB_Cam_4K25/tools/ffmpeg.exe`

## 最短执行顺序

### 1. 先跑源码回归

```powershell
python -m pytest -q test_build_packaging.py test_backend_main.py test_usb_cam_real_validation.py
```

### 2. 构建前端静态资源

```powershell
build_webview.bat
```

### 3. 构建正式包

```powershell
build.bat
```

构建成功后应至少得到：

- `dist/USB_Cam_4K25/`
- `dist/USB_Cam_4K25/USB_Cam_4K25.exe`
- `dist/USB_Cam_4K25/_internal/ui_dist/`
- `dist/USB_Cam_4K25/tools/`

### 4. 跑 packaged runtime 一键验证

```powershell
validate_packaged_runtime.bat
```

默认会：

1. 重新构建正式包
2. 执行 packaged validation summary
3. 输出 report / manifest / checklist / latest index / history index

## 最小人工检查

自动验证之外，至少补这几项人工确认：

1. EXE 冷启动能打开窗口
2. FFmpeg 已被检测到
3. 预览可启停
4. `direct_frames` 可完成一轮
5. `video_then_frames` 可完成一轮
6. `frames.csv` / `summary.txt` / `metadata.json` 已生成

## 建议记录字段

如果要保留一轮构建记录，至少记这些：

- 构建日期
- Windows 版本
- Python 版本
- 是否使用本地 `tools/ffmpeg.exe`
- `validate_packaged_runtime.bat` 是否通过
- 最新 report 路径
- 最新 release gate
- 若失败，失败阶段和原始报错

## 失败分流

### 构建前失败

常见原因：

- Python 不可用
- 依赖没装
- 测试或 `py_compile` 已经失败

### 构建阶段失败

常见原因：

- PyInstaller 依赖缺失
- 前端构建失败
- 本地 `ffmpeg.exe` 不存在但你又要做真实验证

### 包启动后失败

常见原因：

- packaged runtime 子进程残留
- FFmpeg 路径不通
- 前端静态资源未正确进入 `_internal/ui_dist`

## 当前推荐口径

当前仓库只推荐下面这组文档作为 packaged runtime 权威口径：

- `docs/requirements/WEBVIEW_PACKAGED_RUNTIME_QUICKSTART.md`
- `docs/requirements/WEBVIEW_PACKAGED_RUNTIME_FINAL_VALIDATION_2026-05-26.md`
- `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`
- 本文档

一句话总结：

**现在的打包与验证边界应理解为：源码在版本库里，本地 `tools/` 在机器上，`build.bat` 和 `validate_packaged_runtime.bat` 负责把两者接到当前 packaged runtime 主线。**
