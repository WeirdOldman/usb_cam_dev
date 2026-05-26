# USB_CAM Phase 4 Task 3.1 首轮打包实战执行说明

> 目标：把 `build.bat` 真正变成一套“拿到仓库就能跑首包”的实战说明。本文只覆盖 **Windows + PyInstaller --onedir + 绿色分发**。不覆盖安装器，不覆盖 `--onefile`。

---

## 1. 适用范围

本文用于以下场景：

- 第一次在 Windows 上运行 `build.bat`
- 第一次产出 `dist/USB_Cam_4K25/` 绿色包
- 第一次验证 `tools/ffmpeg.exe` 随包策略
- 第一次对照 `USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md` 跑最小验收

明确不包含：
- Inno Setup / `installer.iss`
- `PyInstaller --onefile`
- 图标/签名/安装器美化
- 发布页素材整理

---

## 2. 这一步完成后你应该得到什么

理想结果是：

1. Windows 上可以直接运行 `build.bat`
2. 成功生成：
   - `dist/USB_Cam_4K25/`
3. 该目录中存在主程序 EXE
4. 该目录中预留了：
   - `dist/USB_Cam_4K25/tools/`
5. 你把 `ffmpeg.exe` 放进去后，可以进入首轮 GUI / 采集 / 落盘验收

一句话：
**这一刀不是正式发版，而是先把第一包稳定打出来。**

---

## 3. 前置条件

在 Windows 打包机上，至少满足：

### 3.1 Python
- Python 3.10+
- 命令行至少有一个可用：
  - `py -3`
  - 或 `python`

### 3.2 PyInstaller
必须已安装：

```powershell
py -3 -m pip install pyinstaller
```

如果机器上没有 `py`，就用：

```powershell
python -m pip install pyinstaller
```

### 3.3 当前仓库/目录
确保当前目录就是项目根目录，也就是能看到这些文件：

- `build.bat`
- `backend/main.py`
- `build_webview.bat`
- `test_build_packaging.py`
- `test_backend_main.py`
- `test_usb_cam_real_validation.py`
- `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`

---

## 4. 先做打包前最小检查

在 Windows 命令行里，先切到项目目录，再做下面两步。

### 4.1 自动测试基线

```powershell
py -3 -m pytest -q test_build_packaging.py test_backend_main.py test_usb_cam_real_validation.py
```

或：

```powershell
python -m pytest -q test_build_packaging.py test_backend_main.py test_usb_cam_real_validation.py
```

预期：
- 测试通过
- 当前基线应保持和仓库记录一致（当前为 `123 passed`）

### 4.2 主程序语法检查

```powershell
py -3 -m py_compile backend/main.py usb_cam_paths.py usb_cam_preview.py usb_cam_process.py usb_cam_runtime.py usb_cam_ui_state.py usb_cam_session_finalize.py usb_cam_session_writer.py usb_cam_capture.py usb_cam_ffmpeg.py usb_cam_stats.py usb_cam_real_validation.py
```

如果没有报错，说明至少没有明显语法问题。

---

## 5. 首次运行 `build.bat`

### 5.1 最简单跑法
在项目根目录双击也行，但**更推荐命令行跑**，因为能直接看到报错：

```powershell
.\build.bat
```

### 5.2 `build.bat` 会自动做什么
当前脚本会自动：

1. 检查入口文件 `backend/main.py` 是否存在
2. 自动探测 Python：
   - 先试 `py -3`
   - 再试 `python`
3. 检查 `PyInstaller` 是否已安装
4. 先执行 `build_webview.bat` 生成 `ui_dist`
5. 清理旧产物：
   - `build/`
   - `dist/`
6. 执行：
   - `PyInstaller --noconfirm --clean --windowed --onedir`
7. 固定输出目录名：
   - `dist/USB_Cam_4K25/`
8. 自动带入：
   - `ui_dist/`
9. 自动创建：
   - `dist/USB_Cam_4K25/tools/`

---

## 6. 成功后应该检查什么

打包成功后，先看这几件事：

### 6.1 目录是否生成
至少应存在：

- `build/`
- `dist/`
- `dist/USB_Cam_4K25/`
- `dist/USB_Cam_4K25/tools/`

### 6.2 主程序是否在包内
在 `dist/USB_Cam_4K25/` 目录下，应该能看到主 EXE。

名字如果不是你预想中的样子，先别慌，先确认：
- 确实有一个 GUI 主程序 EXE
- 能双击启动

### 6.3 没有明显异常空壳
如果 `dist/USB_Cam_4K25/` 里几乎啥都没有，或者 EXE 小得离谱，那通常说明打包失败或依赖没带全。

---

## 7. FFmpeg 随包策略（这一步很关键）

当前项目默认设计，不应该把“用户机器 PATH 里刚好有 ffmpeg”当主方案。

### 7.1 推荐做法
把 `ffmpeg.exe` 放到：

```text
dist/USB_Cam_4K25/tools/ffmpeg.exe
```

### 7.2 当前查找思路
程序当前会优先尝试：

1. 用户显式指定路径
2. 程序目录下的：
   - `tools/ffmpeg.exe`
   - `ffmpeg.exe`
3. 最后才 fallback 到系统 PATH

### 7.3 实战建议
所以首轮验收时，**直接把 `ffmpeg.exe` 放到 `tools/` 里**，不要先赌 PATH。

这样更贴近后续绿色分发。

---

## 8. 如果 `build.bat` 失败，先看哪几类错误

### 8.1 提示 Python 不存在
说明这台 Windows 机器上：
- 没有 Python
- 或 PATH 没配好

处理：
- 安装 Python 3.10+
- 确认 `py -3` 或 `python` 至少一个能跑

### 8.2 提示 `PyInstaller` 不存在
处理：

```powershell
py -3 -m pip install pyinstaller
```

或：

```powershell
python -m pip install pyinstaller
```

### 8.3 打包途中报缺模块 / 缺依赖
这属于**首轮实战最可能遇到的问题**。

处理原则：
- 先保留完整控制台输出
- 记录缺的是哪个模块
- 再决定要不要补 hidden-import 或资源带入

这类问题不是现在文档能脑补掉的，得靠首轮出包实测来定。

### 8.4 打包成功但启动闪退
处理顺序：
1. 先从命令行启动 EXE 看报错
2. 检查是否缺 `ffmpeg.exe`
3. 检查是否有日志文件生成
4. 再回看 `USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`

---

## 9. 首轮最小验收路径（别一上来跑满清单）

第一次出包，建议按最短路径走：

### Step 1：冷启动
- 双击 EXE
- 确认 GUI 能打开
- 不闪退

### Step 2：FFmpeg 发现
- 先把 `ffmpeg.exe` 放进 `dist/USB_Cam_4K25/tools/`
- 启动程序
- 看是否还能提示找不到 ffmpeg

### Step 3：预览功能
- 开一次预览
- 停一次预览

### Step 4：采集功能
- 跑一次 direct
- 跑一次 video_then_frames

### Step 5：输出落盘
检查是否生成：
- 图片
- `frames.csv`
- `summary.txt`
- `metadata.json`
- 日志（如果有）

### Step 6：路径边界
- 中文目录
- 含空格目录
- 不可写目录（至少验证报错清晰）

---

## 10. 首轮验收时建议你记录这几项

建议在验收时顺手记下：

- Windows 版本
- Python 版本
- PyInstaller 版本
- 构建时间
- 是否放入 `tools/ffmpeg.exe`
- 首次冷启动是否成功
- direct 是否成功
- video_then_frames 是否成功
- 有无日志/错误弹窗

这样一旦首轮失败，后面排障就不会瞎猜。

---

## 11. 和现有 checklist 的关系

这份 Task 3.1 说明，定位是：

- **告诉你怎么跑第一包**
- **告诉你先看哪几个点**

而这个文档：

- `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`

定位是：

- **完整验收清单**
- **更系统、更细的发布前检查表**

简单说：
- Task 3.1 = 实战操作说明
- Packaging checklist = 验收总表

---

## 12. 一句话结论

**现在最正确的动作不是继续聊打包，而是在 Windows 上实际跑一次 `build.bat`，生成 `dist/USB_Cam_4K25/`，把 `ffmpeg.exe` 放进 `tools/`，然后按最短路径做第一轮冷启动与采集验收。**
