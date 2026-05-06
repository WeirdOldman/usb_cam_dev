# USB_CAM 开发暂停检查点（2026-05-07）

## 本次暂停时的客观状态

### 工程基线
- 主仓库分支：`main`
- 当前最新提交：以暂停时工作区为准，恢复时先执行 `git log --oneline -5`
- 自动测试基线：`test_usb_cam_refactor.py` **31 passed**
- 当前 GitHub Actions：ubuntu / windows 双平台绿色

### 近期已完成事项
1. 大单文件 Tkinter/FFmpeg 项目已完成多轮小刀式重构，核心 helper 与运行期职责已拆分到独立模块
2. Phase 3 自动测试、手工验证、打包验证文档已基本成形
3. Phase 4 已完成：
   - `build.bat` 打包链路落地
   - Windows EXE 启动验证
   - 运行期韧性增强最小切口（磁盘空间预警链路）
4. 最近一次 CI 红灯根因已确认并修复：
   - 原因：测试 `test_start_capture_prep_helpers` 隐式依赖宿主机可找到 ffmpeg
   - 修复：测试中显式 stub `find_ffmpeg`
5. 为排障临时加入的 CI 诊断增强已回收，workflow 已恢复简洁稳定版

## 当前未闭环项

### Phase 4 仍待补的高价值事项
- Windows 实机 direct 最小录制验收
- Windows 实机 video_then_frames 最小录制验收
- 停止流程验收
- `frames.csv` / `summary.txt` / `metadata.json` / 图片落盘验收

### 为什么现在停在这里是合理的
- 代码基线稳定
- 自动测试与双平台 CI 绿色
- 现场硬件/Windows 录制验证属于下一阶段最自然的恢复点
- 再继续做纯代码层重构，边际收益已明显下降

## 恢复开发时建议的第一动作

按顺序执行，不要跳：

1. `git pull`
2. `pytest -q test_usb_cam_refactor.py`
3. 查看最新 CI：`gh run list --limit 5`
4. 重读文档：
   - `docs/USB_CAM_PHASE4_CURRENT_STATUS_NOTE.md`
   - `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`
   - 本文件
5. 直接进入 Windows 实机最小录制验收

## 恢复时的优先级建议

### 优先级 P1（最该先做）
- 补齐 Windows 真实录制验收闭环

### 优先级 P2（验收后再做）
- 若现场发现问题，再针对性补：
  - 停止/收尾链路
  - 磁盘预警文案或阈值
  - 打包产物路径/资源查找问题

### 优先级 P3（不要抢跑）
- 不要在恢复第一刀就继续大规模重构
- 不要现在就切 PySide6
- 不要在没有现场验证前扩展无关功能

## 证据索引

### 关键文档
- `USB_CAM_REFACTOR_ROADMAP.md`
- `docs/USB_CAM_PHASE4_CURRENT_STATUS_NOTE.md`
- `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`
- `docs/USB_CAM_MANUAL_VALIDATION_CHECKLIST.md`

### 关键事实
- 测试基线：31 passed
- CI：ubuntu / windows 绿色
- Phase 4 当前准确表述：**工程基线与启动验证已通过，Windows 真实录制验收待补**

## 一句话恢复提示

**下次回来不要先重构，先做 Windows 实机最小录制验收，把 Phase 4 真正闭环。**
