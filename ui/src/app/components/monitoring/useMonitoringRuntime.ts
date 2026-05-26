import { useEffect, useState } from "react";

import {
  localizeMonitorText,
  localizePreviewStatus,
  localizeUiLockReason,
  normalizeMonitorPayload,
} from "./monitorRuntimeState";
import type {
  CaptureMode,
  MonitorConfig,
  MonitorEvent,
  MonitorPayload,
  MonitorPayloadConfig,
  MonitorRuntime,
  MonitorUiLocks,
  QualityMode,
} from "./types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_FRONTEND_DEV_URL = "http://localhost:5173";
const DEFAULT_MJPEG_URL = `${DEFAULT_API_BASE_URL}/api/video/mjpeg`;
const DEFAULT_WS_URL = "ws://127.0.0.1:8000/ws/monitor";
const DEFAULT_START_URL = `${DEFAULT_API_BASE_URL}/api/control/start`;
const DEFAULT_STOP_URL = `${DEFAULT_API_BASE_URL}/api/control/stop`;
const DEFAULT_CONFIG_URL = `${DEFAULT_API_BASE_URL}/api/config`;
const DEFAULT_SELECT_OUTPUT_DIR_URL = `${DEFAULT_API_BASE_URL}/api/dialog/select-output-dir`;
const DEFAULT_PREVIEW_START_URL = `${DEFAULT_API_BASE_URL}/api/preview/start`;
const DEFAULT_PREVIEW_STOP_URL = `${DEFAULT_API_BASE_URL}/api/preview/stop`;
const DEFAULT_WINDOW_MINIMIZE_URL = `${DEFAULT_API_BASE_URL}/api/window/minimize`;
const DEFAULT_WINDOW_TOGGLE_MAXIMIZE_URL = `${DEFAULT_API_BASE_URL}/api/window/toggle-maximize`;
const DEFAULT_WINDOW_CLOSE_URL = `${DEFAULT_API_BASE_URL}/api/window/close`;
const DEFAULT_OPEN_OUTPUT_DIR_URL = `${DEFAULT_API_BASE_URL}/api/system/open-output-dir`;
const DEFAULT_FFMPEG_STATUS_URL = `${DEFAULT_API_BASE_URL}/api/system/ffmpeg-status`;
const DEFAULT_EVENTS_URL = `${DEFAULT_API_BASE_URL}/api/events`;
const DEFAULT_CAMERA_DEVICES_URL = `${DEFAULT_API_BASE_URL}/api/devices/cameras`;

const defaultConfig: MonitorConfig = {
  cameraName: "imx678' UVC ",
  outputDir: "capture_output",
  imagePrefix: "img",
  mode: "direct_frames",
  qualityMode: "copy",
  deleteVideoAfterExtract: false,
  ffmpegPath: "",
  baseDir: "",
  frontendDevUrl: DEFAULT_FRONTEND_DEV_URL,
  apiBaseUrl: DEFAULT_API_BASE_URL,
  mjpegUrl: DEFAULT_MJPEG_URL,
  websocketUrl: DEFAULT_WS_URL,
  controlStartUrl: DEFAULT_START_URL,
  controlStopUrl: DEFAULT_STOP_URL,
  previewStartUrl: DEFAULT_PREVIEW_START_URL,
  previewStopUrl: DEFAULT_PREVIEW_STOP_URL,
};

const defaultRuntime: MonitorRuntime = {
  isRunning: false,
  capturePhase: "idle",
  phaseLabel: "已停止",
  runTime: 0,
  liveFps: 0,
  processedFrames: 0,
  cpuPercent: 0,
  acceleration: "空闲",
  bitrateMbps: 0,
  resolution: "1280x720",
  statusText: "系统已初始化。",
  captureLastError: "",
  captureLastErrorReason: "",
  captureLastErrorCode: null,
  captureLastSessionDir: "",
  previewEnabled: false,
  previewActive: false,
  previewStatus: "预览已关闭。",
  events: [],
  cameraDevices: [],
  uiLocks: {
    capture_start_disabled: false,
    capture_start_reason: "",
    capture_stop_disabled: true,
    capture_stop_reason: "当前没有正在进行的采集。",
    preview_toggle_disabled: false,
    preview_toggle_reason: "",
    path_edit_disabled: false,
    path_edit_reason: "",
    config_save_disabled: false,
    config_save_reason: "",
    camera_select_disabled: false,
    camera_select_reason: "",
  },
};

function applyConfigPayload(prev: MonitorConfig, payload?: MonitorPayloadConfig): MonitorConfig {
  if (!payload) {
    return prev;
  }

  const apiBaseUrl = String(payload.api_base_url ?? prev.apiBaseUrl);

  return {
    cameraName: String(payload.camera_name ?? prev.cameraName),
    outputDir: String(payload.output_dir ?? prev.outputDir),
    imagePrefix: String(payload.image_prefix ?? prev.imagePrefix),
    mode: ((payload.mode as CaptureMode | undefined) ?? prev.mode),
    qualityMode: ((payload.quality_mode as QualityMode | undefined) ?? prev.qualityMode),
    deleteVideoAfterExtract: Boolean(payload.delete_video_after_extract ?? prev.deleteVideoAfterExtract),
    ffmpegPath: String(payload.ffmpeg_path ?? prev.ffmpegPath),
    baseDir: String(payload.base_dir ?? prev.baseDir),
    frontendDevUrl: String(payload.frontend_dev_url ?? prev.frontendDevUrl),
    apiBaseUrl,
    mjpegUrl: String(payload.mjpeg_url ?? `${apiBaseUrl}/api/video/mjpeg`),
    websocketUrl: String(payload.websocket_url ?? prev.websocketUrl),
    controlStartUrl: String(payload.control_start_url ?? `${apiBaseUrl}/api/control/start`),
    controlStopUrl: String(payload.control_stop_url ?? `${apiBaseUrl}/api/control/stop`),
    previewStartUrl: String(payload.preview_start_url ?? `${apiBaseUrl}/api/preview/start`),
    previewStopUrl: String(payload.preview_stop_url ?? `${apiBaseUrl}/api/preview/stop`),
  };
}

function applyUiLocks(prev: MonitorUiLocks, payload?: Partial<MonitorUiLocks>): MonitorUiLocks {
  if (!payload) {
    return prev;
  }
  const next = { ...prev, ...payload };
  return {
    ...next,
    capture_start_reason: localizeUiLockReason(next.capture_start_reason),
    capture_stop_reason: localizeUiLockReason(next.capture_stop_reason),
    preview_toggle_reason: localizeUiLockReason(next.preview_toggle_reason),
    path_edit_reason: localizeUiLockReason(next.path_edit_reason),
    config_save_reason: localizeUiLockReason(next.config_save_reason),
    camera_select_reason: localizeUiLockReason(next.camera_select_reason),
  };
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const data = (await response.json()) as { detail?: string; status_text?: string };
    if (typeof data.detail === "string" && data.detail) {
      return localizeMonitorText(data.detail);
    }
    if (typeof data.status_text === "string" && data.status_text) {
      return localizeMonitorText(data.status_text);
    }
  } catch {
    return null;
  }
  return null;
}

export function useMonitoringRuntime() {
  const [runtime, setRuntime] = useState<MonitorRuntime>(defaultRuntime);
  const [config, setConfig] = useState<MonitorConfig>(defaultConfig);
  const [wsConnected, setWsConnected] = useState(false);
  const [controlBusy, setControlBusy] = useState(false);
  const [configBusy, setConfigBusy] = useState(false);
  const [directoryBusy, setDirectoryBusy] = useState(false);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const response = await fetch(DEFAULT_CONFIG_URL);
        if (!response.ok) {
          throw new Error(`配置接口请求失败：${response.status}`);
        }
        const data = (await response.json()) as MonitorPayloadConfig;
        setConfig((prev) => applyConfigPayload(prev, data));
      } catch (error) {
        console.error(error);
        setRuntime((prev) => ({ ...prev, statusText: "配置接口请求失败。" }));
      }
    };

    void loadConfig();
  }, []);

  useEffect(() => {
    const loadEvents = async () => {
      try {
        const response = await fetch(DEFAULT_EVENTS_URL);
        if (!response.ok) {
          throw new Error(`事件接口请求失败：${response.status}`);
        }
        const data = (await response.json()) as { events?: MonitorEvent[] };
        setRuntime((prev) => ({
          ...prev,
          events: Array.isArray(data.events) ? data.events : prev.events,
        }));
      } catch (error) {
        console.error(error);
      }
    };

    void loadEvents();
  }, []);

  useEffect(() => {
    const loadCameraDevices = async () => {
      try {
        const response = await fetch(DEFAULT_CAMERA_DEVICES_URL);
        if (!response.ok) {
          throw new Error(`相机设备接口请求失败：${response.status}`);
        }
        const data = (await response.json()) as { devices?: string[]; selected_device?: string };
        setRuntime((prev) => ({
          ...prev,
          cameraDevices: Array.isArray(data.devices) ? data.devices : prev.cameraDevices,
        }));
        if (data.selected_device) {
          setConfig((prev) => ({ ...prev, cameraName: data.selected_device }));
        }
      } catch (error) {
        console.error(error);
      }
    };

    void loadCameraDevices();
  }, []);

  useEffect(() => {
    const ws = new WebSocket(config.websocketUrl);

    ws.onopen = () => {
      setWsConnected(true);
      setRuntime((prev) => ({ ...prev, statusText: "WebSocket 已连接。" }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data) as MonitorPayload;

      setRuntime((prev) => ({
        ...normalizeMonitorPayload(data, prev),
        uiLocks: applyUiLocks(prev.uiLocks, data.ui_locks),
      }));
      setConfig((prev) => applyConfigPayload(prev, data.config));
    };

    ws.onerror = () => {
      setWsConnected(false);
      setRuntime((prev) => ({ ...prev, statusText: "WebSocket 连接出错。" }));
    };

    ws.onclose = () => {
      setWsConnected(false);
      setRuntime((prev) => ({ ...prev, statusText: "WebSocket 已断开。" }));
    };

    return () => {
      ws.close();
    };
  }, [config.websocketUrl]);

  const updateConfig = (patch: Partial<MonitorConfig>) => {
    setConfig((prev) => ({ ...prev, ...patch }));
  };

  const handleControlClick = async () => {
    const targetUrl = runtime.isRunning ? config.controlStopUrl : config.controlStartUrl;
    setControlBusy(true);

    try {
      const response = await fetch(targetUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: runtime.isRunning
          ? undefined
          : JSON.stringify({
              mode: config.mode,
              output_dir: config.outputDir,
              image_prefix: config.imagePrefix,
              quality_mode: config.qualityMode,
              delete_video_after_extract: config.deleteVideoAfterExtract,
              camera_name: config.cameraName,
            }),
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response);
        throw new Error(detail || `控制接口请求失败：${response.status}`);
      }

      const data = (await response.json()) as {
        running?: boolean;
        status_text?: string;
        config?: MonitorPayloadConfig;
      };

      setRuntime((prev) => ({
        ...prev,
        isRunning: Boolean(data.running),
        statusText: data.status_text ? localizeMonitorText(String(data.status_text)) : prev.statusText,
      }));
      setConfig((prev) => applyConfigPayload(prev, data.config));
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "控制接口请求失败。";
      setRuntime((prev) => ({ ...prev, statusText: message }));
    } finally {
      setControlBusy(false);
    }
  };

  const handleSaveConfig = async () => {
    setConfigBusy(true);

    try {
      const response = await fetch(DEFAULT_CONFIG_URL, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          camera_name: config.cameraName,
          output_dir: config.outputDir,
          image_prefix: config.imagePrefix,
          mode: config.mode,
          quality_mode: config.qualityMode,
          delete_video_after_extract: config.deleteVideoAfterExtract,
        }),
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response);
        throw new Error(detail || `配置保存失败：${response.status}`);
      }

      const data = (await response.json()) as MonitorPayloadConfig;
      setConfig((prev) => applyConfigPayload(prev, data));
      setRuntime((prev) => ({ ...prev, statusText: "运行配置已保存到后端。" }));
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "配置保存失败。";
      setRuntime((prev) => ({ ...prev, statusText: message }));
    } finally {
      setConfigBusy(false);
    }
  };

  const handlePickOutputDir = async () => {
    setDirectoryBusy(true);

    try {
      const response = await fetch(DEFAULT_SELECT_OUTPUT_DIR_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_dir: config.outputDir,
        }),
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response);
        throw new Error(detail || `输出目录选择失败：${response.status}`);
      }

      const data = (await response.json()) as {
        ok?: boolean;
        selected_dir?: string | null;
        config?: MonitorPayloadConfig;
      };

      if (data.selected_dir) {
        setConfig((prev) => ({ ...prev, outputDir: String(data.selected_dir) }));
      }
      setConfig((prev) => applyConfigPayload(prev, data.config));
      setRuntime((prev) => ({
        ...prev,
        statusText: data.ok ? "已选择输出目录。" : "已取消选择输出目录。",
      }));
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "输出目录选择失败。";
      setRuntime((prev) => ({ ...prev, statusText: message }));
    } finally {
      setDirectoryBusy(false);
    }
  };

  const callWindowAction = async (url: string) => {
    try {
      const response = await fetch(url, { method: "POST" });
      if (!response.ok) {
        const detail = await readErrorDetail(response);
        throw new Error(detail || `窗口控制请求失败：${response.status}`);
      }
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "窗口控制请求失败。";
      setRuntime((prev) => ({ ...prev, statusText: message }));
    }
  };

  const openOutputDir = async () => {
    try {
      const response = await fetch(DEFAULT_OPEN_OUTPUT_DIR_URL, { method: "POST" });
      if (!response.ok) {
        const detail = await readErrorDetail(response);
        throw new Error(detail || `打开输出目录失败：${response.status}`);
      }
      setRuntime((prev) => ({ ...prev, statusText: "已打开输出目录。" }));
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "打开输出目录失败。";
      setRuntime((prev) => ({ ...prev, statusText: message }));
    }
  };

  const togglePreview = async () => {
    const targetUrl = runtime.previewEnabled ? config.previewStopUrl : config.previewStartUrl;
    try {
      const response = await fetch(targetUrl, { method: "POST" });
      if (!response.ok) {
        const detail = await readErrorDetail(response);
        throw new Error(detail || `预览控制失败：${response.status}`);
      }
      const data = (await response.json()) as {
        preview_enabled?: boolean;
        preview_status?: string;
      };
      setRuntime((prev) => ({
        ...prev,
        previewEnabled: Boolean(data.preview_enabled ?? prev.previewEnabled),
        previewStatus: localizePreviewStatus(String(data.preview_status ?? prev.previewStatus)),
        statusText: localizeMonitorText(String(data.preview_status ?? prev.statusText)),
      }));
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "预览控制请求失败。";
      setRuntime((prev) => ({ ...prev, statusText: message }));
    }
  };

  const checkFfmpeg = async () => {
    try {
      const response = await fetch(DEFAULT_FFMPEG_STATUS_URL);
      if (!response.ok) {
        const detail = await readErrorDetail(response);
        throw new Error(detail || `FFmpeg 状态检查失败：${response.status}`);
      }
      const data = (await response.json()) as { ffmpeg_found?: boolean; ffmpeg_path?: string };
      setConfig((prev) => ({ ...prev, ffmpegPath: String(data.ffmpeg_path ?? prev.ffmpegPath) }));
      setRuntime((prev) => ({
        ...prev,
        statusText: data.ffmpeg_found ? "FFmpeg 可用。" : "未找到 FFmpeg。",
      }));
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "FFmpeg 检查失败。";
      setRuntime((prev) => ({ ...prev, statusText: message }));
    }
  };

  return {
    runtime,
    config,
    wsConnected,
    controlBusy,
    configBusy,
    directoryBusy,
    updateConfig,
    handleControlClick,
    handleSaveConfig,
    handlePickOutputDir,
    handleWindowMinimize: () => callWindowAction(DEFAULT_WINDOW_MINIMIZE_URL),
    handleWindowToggleMaximize: () => callWindowAction(DEFAULT_WINDOW_TOGGLE_MAXIMIZE_URL),
    handleWindowClose: () => callWindowAction(DEFAULT_WINDOW_CLOSE_URL),
    openOutputDir,
    checkFfmpeg,
    togglePreview,
  };
}
