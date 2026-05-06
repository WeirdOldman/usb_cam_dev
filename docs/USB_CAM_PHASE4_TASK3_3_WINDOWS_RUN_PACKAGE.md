# USB_CAM Phase 4 Task 3.3 Windows 实机执行包说明

> 目标：把 Phase 4 首轮 Windows `build.bat` 实机执行，收口成一套**最短落地动作包**。这份文档不再讲抽象原则，只讲你在 Windows 机器上现在该怎么跑、跑完怎么记、炸了怎么分流。

---

## 1. 这一刀要做什么

Task 3.3 的目标只有一句话：

**在 Windows 实机上真实执行一次 `build.bat`，生成第一版 `dist/USB_Cam_4K25/`，并把结果按模板留痕。**

不是继续补计划。
不是继续聊打包策略。
就是实际跑一遍。

---

## 2. 执行前你手边该准备好什么

在 Windows 机器上，确认你已经拿到整个项目目录，并且至少能看到：

- `build.bat`
- `usb_burst_cam_4k25_manual_v1_6_3.py`
- `test_usb_cam_refactor.py`
- `docs/USB_CAM_PHASE4_TASK3_1_FIRST_BUILD_GUIDE.md`
- `docs/USB_CAM_PHASE4_TASK3_2_FIRST_BUILD_RECORD_TEMPLATE.md`
- `docs/USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md`

另外准备：
- 一份可用的 `ffmpeg.exe`
- 一个 Windows 命令行（推荐 PowerShell）
- 一份 3.2 模板副本，用来记录本轮结果

---

## 3. Windows 实机最短执行顺序

按这个顺序走，别自己改流程。

### Step 1：复制一份本轮记录模板
先复制：

`docs/USB_CAM_PHASE4_TASK3_2_FIRST_BUILD_RECORD_TEMPLATE.md`

建议命名成：

`docs/USB_CAM_PHASE4_BUILD_RUN_YYYY-MM-DD_R1.md`

例如：

`docs/USB_CAM_PHASE4_BUILD_RUN_2026-05-01_R1.md`

这一步的意义很简单：
**别等跑炸了再回忆。边跑边记。**

---

### Step 2：打开 PowerShell 并切到项目目录
例如：

```powershell
cd D:\path\to\usb_cam_dev
```

先确认文件在不在：

```powershell
Get-ChildItem .\build.bat
Get-ChildItem .\docs\USB_CAM_PHASE4_TASK3_1_FIRST_BUILD_GUIDE.md
Get-ChildItem .\docs\USB_CAM_PHASE4_TASK3_2_FIRST_BUILD_RECORD_TEMPLATE.md
```

如果这里都看不到，就别往下跑。

---

### Step 3：先跑打包前最小验证
#### 3.1 跑测试
```powershell
py -3 -m pytest -q test_usb_cam_refactor.py
```

如果没有 `py`：

```powershell
python -m pytest -q test_usb_cam_refactor.py
```

你要记录到 3.2 模板里的内容：
- 是否通过
- 输出是否仍为 `20 passed`
- 如果不是，偏差是什么

#### 3.2 跑语法检查
```powershell
py -3 -m py_compile usb_burst_cam_4k25_manual_v1_6_3.py usb_cam_paths.py usb_cam_preview.py usb_cam_process.py usb_cam_runtime.py usb_cam_ui_state.py usb_cam_finalize.py usb_cam_session_finalize.py usb_cam_session_writer.py usb_cam_capture.py usb_cam_ffmpeg.py usb_cam_stats.py
```

如果没报错，就在模板里记“py_compile 通过”。

---

### Step 4：执行 `build.bat`
直接跑：

```powershell
.\build.bat
```

这一步你要马上记录：
- 开始时间
- 结束时间
- 是否退出成功
- 控制台最后关键输出
- 如果失败，失败发生在哪一段

**别只记“失败了”。要记失败阶段。**

建议失败阶段统一写成这几类：
- Python 探测失败
- PyInstaller 探测失败
- PyInstaller 构建中失败
- 构建成功但产物目录异常
- 构建成功但 EXE 启动失败

---

### Step 5：检查产物目录
如果 `build.bat` 成功，立刻检查：

```powershell
Get-ChildItem .\build
Get-ChildItem .\dist
Get-ChildItem .\dist\USB_Cam_4K25
Get-ChildItem .\dist\USB_Cam_4K25\tools
```

你要确认：
- `build/` 在
- `dist/` 在
- `dist/USB_Cam_4K25/` 在
- `tools/` 在
- 主 EXE 在

然后把这些记进 3.2 模板。

---

### Step 6：放入 `ffmpeg.exe`
把你准备好的 `ffmpeg.exe` 放进去：

```text
dist/USB_Cam_4K25/tools/ffmpeg.exe
```

然后记录：
- ffmpeg 来源
- 是否确实放进 `tools/`
- 放入时间

如果你偷懒先赌 PATH，后面出问题很容易混淆来源。  
**首轮实战不要赌 PATH。直接随包放。**

---

### Step 7：跑最小验收，不要一上来跑满表
首轮只跑最短链路：

#### 7.1 冷启动
- 双击 EXE
- 或在 PowerShell 中直接启动 EXE
- 看 GUI 能不能起来

#### 7.2 GUI 基础
- 按钮能不能点
- 日志区/状态区有没有明显异常

#### 7.3 FFmpeg 发现
- 启动后是否仍提示找不到 ffmpeg

#### 7.4 预览
- 开一次
- 停一次

#### 7.5 采集
- 跑一次 direct
- 跑一次 video_then_frames

#### 7.6 落盘
检查有没有生成：
- 图片
- `frames.csv`
- `summary.txt`
- `metadata.json`

这些结果都填进 3.2 模板。

---

## 4. 如果第一包炸了，怎么分流记录

别把所有问题都写成“打包失败”。按下面分。

### A 类：构建前问题
特征：还没开始真正 PyInstaller 出包就炸了。

例如：
- 没有 Python
- 没有 PyInstaller
- 测试基线已经不对
- `py_compile` 就报错

处理：
- 先修环境/基线
- 不要继续往出包问题上猜

### B 类：构建阶段问题
特征：`build.bat` 跑了，但 PyInstaller 过程中报错。

例如：
- 缺模块
- 缺依赖
- hidden import 问题
- 资源未带入

处理：
- 保留完整控制台输出
- 在 3.2 模板里把“报错原文 + 初步判断”写清楚
- 后续修 PyInstaller 参数 / spec / hidden-import

### C 类：出包后启动问题
特征：包已经生成，但 EXE 一启动就炸。

例如：
- 闪退
- DLL 缺失
- GUI 起不来
- 找不到 ffmpeg

处理：
- 先命令行启动 EXE 看报错
- 再查 ffmpeg 和路径解析
- 再查日志文件

### D 类：功能链路问题
特征：能启动，但预览/采集/落盘不对。

例如：
- direct 不工作
- video_then_frames 不工作
- 能录但文件不完整
- 中文路径有问题

处理：
- 归到功能验收问题，不要误判成“构建失败”

---

## 5. 推荐的记录姿势

你在 Windows 上跑的时候，建议就按这个节奏：

1. 开 PowerShell
2. 开 3.2 记录模板
3. 每跑完一步，立刻填一行
4. 失败时直接复制控制台原文进去

不要等全部跑完再补。  
到那时候很多细节你肯定忘了。

---

## 6. 本轮跑完后，你应该交回什么

Task 3.3 做完，最少要有这两个结果：

### 结果 A：实际产物
至少二选一：
- 成功生成 `dist/USB_Cam_4K25/`
- 或明确卡在哪个失败阶段

### 结果 B：一份已填写的首轮记录
也就是一份实际填过的：

`USB_CAM_PHASE4_BUILD_RUN_YYYY-MM-DD_R1.md`

这份东西后面非常值钱，因为它会直接决定下一步到底是：
- 修构建脚本
- 补 hidden-import
- 修 ffmpeg 查找
- 修运行时问题
- 还是扩大第二轮验收

---

## 7. 跑完后的下一步判断

### 如果首轮通过度高
满足：
- 能构建
- 能启动
- ffmpeg 能找到
- direct / video_then_frames 都能跑
- 输出文件齐

那下一步就应该是：
- 扩大验收范围
- 跑中文路径 / 空格路径 / 不可写路径
- 准备第二轮稳定性验收

### 如果首轮只打出半包
例如：
- 能构建但启动炸
- 能启动但 ffmpeg 不通
- direct 通、另一模式不通

那下一步就别扩范围，先修阻断项。

### 如果首轮直接构建失败
那下一步很明确：
- 回到 PyInstaller 依赖/hidden-import/资源带入问题排查

---

## 8. 一句话结论

**Task 3.3 的本质不是再补文档，而是把“Windows 真机首包执行 → 结果记录 → 问题分流”这条链跑通。你现在该做的就是拿着 3.1 指南、3.2 模板和 `build.bat`，在 Windows 上狠狠干第一包。**
