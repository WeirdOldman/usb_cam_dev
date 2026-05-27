# USB_CAM Packaging Validation Checklist

- [ ] `python -m pytest -q test_build_packaging.py test_runtime_controller.py test_desktop_main.py test_usb_cam_real_validation.py` 通过
- [ ] `build.bat` 成功输出 `dist/USB_Cam_4K25/USB_Cam_4K25.exe`
- [ ] `dist/USB_Cam_4K25/tools/ffmpeg.exe` 存在
- [ ] 当前默认桌面入口 `desktop/main.py` 可正常启动 packaged runtime
- [ ] packaged preview start / stop 验证通过
- [ ] packaged `direct_frames` 验证通过
- [ ] packaged `video_then_frames` 验证通过
- [ ] stop-flow closure 验证通过
- [ ] 中文路径验证通过
- [ ] 空格路径验证通过
- [ ] `packaged_validation_summary_report.json` 已生成
- [ ] `packaged_validation_manifest.json` 已生成
- [ ] `packaged_release_checklist.md` 已生成
