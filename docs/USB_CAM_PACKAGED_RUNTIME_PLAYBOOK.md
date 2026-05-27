# USB_CAM Packaged Runtime Playbook

## 当前主线

- `PySide6 + RuntimeController`
- `desktop/main.py`
- `build.bat`
- `validate_packaged_runtime.bat`

## 标准本地流程

### 1. 先跑测试

```powershell
python -m pytest -q test_build_packaging.py test_runtime_controller.py test_desktop_main.py test_usb_cam_real_validation.py
```

### 2. 构建 packaged runtime

```bat
build.bat
```

### 3. 跑 packaged validation

```bat
validate_packaged_runtime.bat
```

## 打包产物

- EXE：`dist/USB_Cam_4K25/USB_Cam_4K25.exe`
- FFmpeg：`dist/USB_Cam_4K25/tools/ffmpeg.exe`
- ZIP：`dist/USB_Cam_4K25-win64.zip`

## packaged validation 输出

- summary report：`outputs/packaged_runtime/<run_id>/packaged_validation_summary_report.json`
- markdown report：`outputs/packaged_runtime/<run_id>/packaged_validation_summary_report.md`
- manifest：`outputs/packaged_runtime/<run_id>/packaged_validation_manifest.json`
- checklist：`outputs/packaged_runtime/<run_id>/packaged_release_checklist.md`
- latest index：`outputs/packaged_runtime/latest_packaged_validation.json`
- history index：`outputs/packaged_runtime/packaged_validation_history.json`

## 当前验证动作

packaged validation 当前验证：

- 窗口可启动
- controller config 可加载
- 设备列表可读
- 预览可启动 / 可停止
- 采集可开始 / 可停止
- session 产物可落盘
- summary / metadata / frames.csv 可收集

## 常见问题

- 构建前先关闭正在运行的 `USB_Cam_4K25.exe`
- `tools/ffmpeg.exe` 缺失时，采集与预览不会正常工作
- 如果 packaged validation 失败，优先看：
  - summary report
  - manifest
  - checklist
  - latest / history index
