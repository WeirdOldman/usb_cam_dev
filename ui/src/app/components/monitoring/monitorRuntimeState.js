const directTextMap = new Map([
  ["System initialized.", "系统已初始化。"],
  ["WebSocket connected.", "WebSocket 已连接。"],
  ["WebSocket connection error.", "WebSocket 连接出错。"],
  ["WebSocket disconnected.", "WebSocket 已断开。"],
  ["Starting pipeline...", "正在启动采集流程..."],
  ["Stopping capture...", "正在停止采集..."],
  ["FFmpeg not found.", "未找到 FFmpeg。"],
  ["FFmpeg available.", "FFmpeg 可用。"],
  ["Preview started.", "预览已启动。"],
  ["Preview stopped.", "预览已停止。"],
  ["Preview running.", "预览运行中。"],
  ["Preview ready.", "预览就绪。"],
  ["Preview disabled", "预览已关闭"],
  ["Preview sourced from capture pipeline.", "预览画面来自采集流程。"],
  ["Running", "运行中"],
  ["Capture already running.", "采集已在运行中。"],
  ["Capture is not running.", "当前没有正在进行的采集。"],
  ["Capture completed without producing frames.", "采集已结束，但没有产出任何帧。"],
  ["Camera is already in use by another application.", "相机正被其他程序占用。"],
  ["Output directory updated.", "输出目录已更新。"],
  ["Output directory selected.", "已选择输出目录。"],
  ["Output directory selection cancelled.", "已取消选择输出目录。"],
  ["Config API request failed.", "配置接口请求失败。"],
  ["Control API request failed.", "控制接口请求失败。"],
  ["Config saved to backend runtime.", "运行配置已保存到后端。"],
  ["Config update request failed.", "配置保存失败。"],
  ["Output directory picker failed.", "输出目录选择失败。"],
  ["Window control request failed.", "窗口控制请求失败。"],
  ["Open output directory failed.", "打开输出目录失败。"],
  ["Opened output directory.", "已打开输出目录。"],
  ["Preview control request failed.", "预览控制请求失败。"],
  ["Check FFmpeg failed.", "FFmpeg 检查失败。"],
  ["Waiting for WebSocket...", "等待 WebSocket 连接..."],
  ["Not detected", "未检测到"],
  ["Stopped", "已停止"],
  ["Running", "运行中"],
  ["Failed", "失败"],
  ["Starting", "启动中"],
  ["Stopping", "停止中"],
  ["Idle", "空闲"],
  ["Unknown", "未知"],
  ["CUDA Active", "CUDA 已启用"],
  ["stable", "运行稳定。"],
  ["fps_below_threshold", "采集帧率低于阈值。"],
  ["disk_low_space", "磁盘剩余空间不足。"],
  ["Unsupported mode", "不支持的采集模式。"],
  ["Unsupported quality_mode", "不支持的画质模式。"],
  ["Cannot update config while capture is running", "采集运行中，不能修改配置。"],
  ["Cannot select output dir while capture is running", "采集运行中，不能选择输出目录。"],
  ["Cannot stop preview while capture is running", "采集运行中，不能停止预览。"],
]);

const detailPatterns = [
  [/^Capture completed: (\d+) frames\.$/, (_full, frames) => `采集完成：${frames} 帧。`],
  [/^Selected camera could not be opened: (.+?)\.$/, (_full, name) => `所选相机无法打开：${name}。`],
  [/^Selected camera input could not be opened: (.+?)\.$/, (_full, name) => `所选相机输入无法打开：${name}。`],
  [/^Capture runtime exception: (.+)$/, (_full, detail) => `采集运行异常：${detail}`],
  [/^Capture process exited unexpectedly with code (.+?)\.$/, (_full, code) => `采集进程异常退出，退出码：${code}。`],
  [/^Control API failed: (.+)$/, (_full, detail) => `控制接口请求失败：${detail}`],
  [/^Config update failed: (.+)$/, (_full, detail) => `配置保存失败：${detail}`],
  [/^Select output dir failed: (.+)$/, (_full, detail) => `输出目录选择失败：${detail}`],
  [/^Window action failed: (.+)$/, (_full, detail) => `窗口控制请求失败：${detail}`],
  [/^Open output dir failed: (.+)$/, (_full, detail) => `打开输出目录失败：${detail}`],
  [/^Preview control failed: (.+)$/, (_full, detail) => `预览控制失败：${detail}`],
  [/^FFmpeg status failed: (.+)$/, (_full, detail) => `FFmpeg 状态检查失败：${detail}`],
];

export function localizeCaptureReason(reasonCode, rawText = "") {
  switch (reasonCode) {
    case "ffmpeg_missing":
      return "未找到 FFmpeg。";
    case "camera_in_use":
      return "相机正被其他程序占用。";
    case "camera_invalid":
      return rawText ? localizeMonitorText(rawText) : "所选相机无法打开。";
    case "capture_no_frames":
      return "采集已结束，但没有产出任何帧。";
    case "capture_failed":
      return rawText ? localizeMonitorText(rawText) : "采集进程异常退出。";
    case "runtime_exception":
      return rawText ? localizeMonitorText(rawText) : "采集运行异常。";
    default:
      return reasonCode;
  }
}

export function localizeMonitorText(rawText, reasonCode = "") {
  if (!rawText) {
    return "";
  }
  if (reasonCode) {
    const localizedByReason = localizeCaptureReason(reasonCode, "");
    if (localizedByReason && localizedByReason !== reasonCode && !rawText.startsWith("Selected camera")) {
      return localizedByReason;
    }
  }
  if (directTextMap.has(rawText)) {
    return directTextMap.get(rawText);
  }
  for (const [pattern, formatter] of detailPatterns) {
    const match = rawText.match(pattern);
    if (match) {
      return formatter(...match);
    }
  }
  return rawText;
}

export function localizePreviewStatus(rawText) {
  return localizeMonitorText(rawText);
}

export function localizeMonitorEvent(event) {
  return {
    ...event,
    message: localizeMonitorText(event?.message ?? ""),
  };
}

export function localizeUiLockReason(reason) {
  return localizeMonitorText(reason);
}

export function describeCapturePhase(capturePhase, isRunning) {
  if (isRunning) {
    if (capturePhase === "starting") {
      return "启动中";
    }
    if (capturePhase === "stopping") {
      return "停止中";
    }
    return "运行中";
  }
  if (capturePhase === "failed") {
    return "失败";
  }
  return "已停止";
}

export function resolveMonitorStatusText(payload, fallbackStatusText = "") {
  if (payload && typeof payload.capture_last_error === "string" && payload.capture_last_error) {
    return localizeMonitorText(payload.capture_last_error, payload.capture_last_error_reason ?? "");
  }
  if (payload && typeof payload.status_text === "string" && payload.status_text) {
    return localizeMonitorText(payload.status_text);
  }
  return localizeMonitorText(fallbackStatusText);
}

export function normalizeMonitorPayload(payload, previousRuntime) {
  const nextRuntime = {
    ...previousRuntime,
    isRunning: Boolean(payload?.running),
    capturePhase: String(payload?.capture_phase ?? previousRuntime.capturePhase),
    runTime: Number(payload?.runtime_seconds ?? 0),
    liveFps: Number(payload?.fps ?? 0),
    processedFrames: Number(payload?.processed_frames ?? 0),
    cpuPercent: Number(payload?.cpu_percent ?? 0),
    acceleration: localizeMonitorText(String(payload?.acceleration ?? "Idle")),
    bitrateMbps: Number(payload?.bitrate_mbps ?? 0),
    resolution: String(payload?.resolution ?? "1280x720"),
    statusText: resolveMonitorStatusText(payload, previousRuntime.statusText),
    captureLastError: localizeMonitorText(String(payload?.capture_last_error ?? ""), String(payload?.capture_last_error_reason ?? "")),
    captureLastErrorReason: String(payload?.capture_last_error_reason ?? ""),
    captureLastErrorCode: typeof payload?.capture_last_error_code === "number" ? payload.capture_last_error_code : null,
    captureLastSessionDir: String(payload?.capture_last_session_dir ?? ""),
    previewEnabled: Boolean(payload?.preview_enabled ?? true),
    previewActive: Boolean(payload?.preview_active ?? false),
    previewStatus: localizePreviewStatus(String(payload?.preview_status ?? "Preview ready.")),
    events: Array.isArray(payload?.events) ? payload.events.map(localizeMonitorEvent) : previousRuntime.events,
  };
  nextRuntime.phaseLabel = describeCapturePhase(nextRuntime.capturePhase, nextRuntime.isRunning);
  return nextRuntime;
}
