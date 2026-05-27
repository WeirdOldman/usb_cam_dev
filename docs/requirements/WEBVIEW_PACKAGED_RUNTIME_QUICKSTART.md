# Packaged Runtime Quickstart

虽然文件名沿用历史命名，但当前内容只描述 **PySide6 + RuntimeController** packaged runtime。

## 最小验证链

1. 安装依赖：
   - `requirements-desktop.txt`
2. 构建：
   - `build.bat`
3. packaged validation：
   - `validate_packaged_runtime.bat`

## 当前 packaged runtime 形态

- 桌面窗口由 `PySide6` 提供
- 不再存在 WebView / FastAPI / React 前端
- 预览、配置、采集与快照都通过进程内 controller 驱动

## 关键命令

```powershell
python -m pytest -q test_build_packaging.py test_runtime_controller.py test_desktop_main.py test_usb_cam_real_validation.py
```

```bat
build.bat
validate_packaged_runtime.bat
```

## 输出索引

- `latest_packaged_validation.json`
- `packaged_validation_history.json`

这些索引会记录：

- root ready seconds
- frame count
- total frame size bytes
- delta
- baseline run
- skipped runs

## 当前边界

- 不需要 Node
- 不需要 `ui_dist`
- 不需要 `build_webview.bat`
- 不需要 `requirements-pywebview.txt`
