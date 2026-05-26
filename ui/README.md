# USB Cam 4K25 UI

`ui/` 是当前桌面壳前端，服务于 `PyWebView + FastAPI + React` 主线。

## 本地开发

先安装依赖：

```bash
npm install
```

启动开发服务器：

```bash
npm run dev
```

打包静态资源：

```bash
npm run build
```

构建产物会被 `build_webview.bat` 复制到仓库根目录的 `ui_dist/`，供 `backend/main.py` 和打包流程使用。
