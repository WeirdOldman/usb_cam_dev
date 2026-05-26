export type CaptureMode = "direct_frames" | "video_then_frames";
export type QualityMode = "copy" | "q2";
export type ActiveTab = "main" | "path" | "settings";

export type MonitorPayloadConfig = {
  camera_name?: string;
  output_dir?: string;
  image_prefix?: string;
  mode?: string;
  quality_mode?: string;
  delete_video_after_extract?: boolean;
  ffmpeg_path?: string;
  base_dir?: string;
  frontend_dev_url?: string;
  api_base_url?: string;
  mjpeg_url?: string;
  websocket_url?: string;
  control_start_url?: string;
  control_stop_url?: string;
  preview_start_url?: string;
  preview_stop_url?: string;
};

export type MonitorPayload = {
  running?: boolean;
  capture_phase?: string;
  runtime_seconds?: number;
  fps?: number;
  cpu_percent?: number;
  processed_frames?: number;
  acceleration?: string;
  bitrate_mbps?: number;
  resolution?: string;
  status_text?: string;
  capture_last_error?: string | null;
  capture_last_error_reason?: string | null;
  capture_last_error_code?: number | null;
  capture_last_session_dir?: string | null;
  preview_enabled?: boolean;
  preview_active?: boolean;
  preview_status?: string;
  ui_locks?: Partial<MonitorUiLocks>;
  timestamp?: string;
  config?: MonitorPayloadConfig;
};

export type MonitorEvent = {
  kind: string;
  message: string;
  timestamp: string;
};

export type MonitorUiLocks = {
  capture_start_disabled: boolean;
  capture_start_reason: string;
  capture_stop_disabled: boolean;
  capture_stop_reason: string;
  preview_toggle_disabled: boolean;
  preview_toggle_reason: string;
  path_edit_disabled: boolean;
  path_edit_reason: string;
  config_save_disabled: boolean;
  config_save_reason: string;
  camera_select_disabled: boolean;
  camera_select_reason: string;
};

export type MonitorConfig = {
  cameraName: string;
  outputDir: string;
  imagePrefix: string;
  mode: CaptureMode;
  qualityMode: QualityMode;
  deleteVideoAfterExtract: boolean;
  ffmpegPath: string;
  baseDir: string;
  frontendDevUrl: string;
  apiBaseUrl: string;
  mjpegUrl: string;
  websocketUrl: string;
  controlStartUrl: string;
  controlStopUrl: string;
  previewStartUrl: string;
  previewStopUrl: string;
};

export type MonitorRuntime = {
  isRunning: boolean;
  capturePhase: string;
  phaseLabel: string;
  runTime: number;
  liveFps: number;
  processedFrames: number;
  cpuPercent: number;
  acceleration: string;
  bitrateMbps: number;
  resolution: string;
  statusText: string;
  captureLastError: string;
  captureLastErrorReason: string;
  captureLastErrorCode: number | null;
  captureLastSessionDir: string;
  previewEnabled: boolean;
  previewActive: boolean;
  previewStatus: string;
  events: MonitorEvent[];
  cameraDevices: string[];
  uiLocks: MonitorUiLocks;
};
