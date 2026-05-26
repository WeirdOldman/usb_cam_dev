import { Camera, Eye, EyeOff, HardDrive, Play, Square, TerminalSquare } from "lucide-react";

import { localizeCaptureReason } from "./monitorRuntimeState";
import {
  primaryButtonStyle,
  sectionLabelStyle,
  subtleButtonStyle,
  surfacePanelStyle,
  winCardStyle,
} from "./monitoringShared";
import type { MonitorConfig, MonitorRuntime } from "./types";

type MonitoringSidebarProps = {
  runtime: MonitorRuntime;
  config: MonitorConfig;
  wsConnected: boolean;
  controlBusy: boolean;
  onControlClick: () => void;
  onConfigChange: (patch: Partial<MonitorConfig>) => void;
  onTogglePreview: () => void;
};

export function MonitoringSidebar({
  runtime,
  config,
  wsConnected,
  controlBusy,
  onControlClick,
  onConfigChange,
  onTogglePreview,
}: MonitoringSidebarProps) {
  return (
    <div className="flex w-full min-h-0 shrink-0 flex-col gap-4 lg:w-[368px]">
      <div className={`${winCardStyle} flex shrink-0 flex-col gap-4 p-5`}>
        <div className="flex items-center justify-between">
          <div>
            <div className={sectionLabelStyle}>控制中心</div>
            <h3 className="mt-1 flex items-center gap-2 text-[16px] font-semibold text-gray-900 dark:text-white">
              <TerminalSquare size={16} className="text-gray-500" />
              任务控制
            </h3>
          </div>
          <span
            className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${
              runtime.isRunning
                ? "border-green-200 bg-green-50 text-green-600 dark:border-green-500/20 dark:bg-green-500/10 dark:text-green-400"
                : runtime.capturePhase === "failed"
                  ? "border-red-200 bg-red-50 text-red-600 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
                  : "border-gray-200 bg-gray-100 text-gray-500 dark:border-white/10 dark:bg-white/5"
            }`}
          >
            {runtime.phaseLabel}
          </span>
        </div>

        <button
          onClick={onControlClick}
          disabled={
            controlBusy ||
            (!runtime.isRunning && runtime.uiLocks.capture_start_disabled) ||
            (runtime.isRunning && runtime.uiLocks.capture_stop_disabled)
          }
          title={runtime.isRunning ? runtime.uiLocks.capture_stop_reason : runtime.uiLocks.capture_start_reason}
          className={`h-12 text-[14px] ${primaryButtonStyle} ${
            runtime.isRunning
              ? "!bg-[#c42b1c] !text-white shadow-[0_10px_24px_rgba(196,43,28,0.2)] hover:!bg-[#b32719] dark:!bg-[#d6554a] dark:!text-white"
              : ""
          }`}
        >
          {runtime.isRunning ? <Square size={16} fill="currentColor" /> : <Play size={16} fill="currentColor" />}
          {controlBusy ? "发送中..." : runtime.isRunning ? "停止采集" : "开始采集"}
        </button>

        <button
          onClick={onTogglePreview}
          disabled={runtime.uiLocks.preview_toggle_disabled}
          title={runtime.uiLocks.preview_toggle_reason}
          className={`h-11 ${subtleButtonStyle}`}
        >
          {runtime.previewEnabled ? <EyeOff size={15} /> : <Eye size={15} />}
          {runtime.previewEnabled ? "停止预览" : "启动预览"}
        </button>

        <div className={`${surfacePanelStyle} px-4 py-3 text-[12px] leading-relaxed text-gray-600 dark:text-gray-300`}>
          {runtime.captureLastErrorReason
            ? `采集失败：${localizeCaptureReason(runtime.captureLastErrorReason, runtime.captureLastError)}`
            : runtime.isRunning
              ? "采集正在运行，预览画面来自当前采集流程。"
              : runtime.previewEnabled
                ? "空闲时可使用预览，采集控制已就绪。"
                : "预览已关闭。如需在采集前恢复实时监看，请先启动预览。"}
        </div>
      </div>

      <div className={`${winCardStyle} flex flex-1 flex-col overflow-hidden`}>
        <div className="custom-scrollbar flex-1 overflow-y-auto p-1 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-black/20 [&::-webkit-scrollbar]:w-1.5 dark:[&::-webkit-scrollbar-thumb]:bg-white/20">
          <div className="border-b border-black/[0.05] p-4 dark:border-white/[0.08]">
            <h4 className={`${sectionLabelStyle} mb-3`}>输入源</h4>

            <div className="space-y-3">
              {runtime.cameraDevices.length > 0 ? (
                <select
                  value={config.cameraName}
                  onChange={(event) => onConfigChange({ cameraName: event.target.value })}
                  disabled={runtime.uiLocks.camera_select_disabled}
                  title={runtime.uiLocks.camera_select_reason}
                  className="h-9 w-full rounded-md border border-black/10 bg-[#ffffff] px-3 text-[13px] text-gray-900 shadow-sm transition-colors hover:bg-gray-50 focus:border-[#005fb8] outline-none dark:border-white/10 dark:bg-[#333333] dark:text-white dark:hover:bg-[#383838] dark:focus:border-[#60cdff]"
                >
                  {runtime.cameraDevices.map((device) => (
                    <option key={device} value={device}>
                      {device}
                    </option>
                  ))}
                </select>
              ) : null}

              <div className="group relative">
                <input
                  value={config.cameraName}
                  onChange={(event) => onConfigChange({ cameraName: event.target.value })}
                  disabled={runtime.uiLocks.camera_select_disabled}
                  title={runtime.uiLocks.camera_select_reason}
                  className="h-9 w-full rounded-md border border-black/10 bg-[#ffffff] pl-3 pr-3 text-[13px] text-gray-900 shadow-sm transition-colors hover:bg-gray-50 focus:border-[#005fb8] outline-none dark:border-white/10 dark:bg-[#333333] dark:text-white dark:hover:bg-[#383838] dark:focus:border-[#60cdff]"
                />
                <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-500">
                  <Camera size={14} />
                </div>
              </div>
            </div>
          </div>

          <div className="border-b border-black/[0.05] p-4 dark:border-white/[0.08]">
            <h4 className={`${sectionLabelStyle} mb-4`}>采集流程</h4>

            <div className="space-y-4">
              <label className="flex flex-col gap-2">
                <span className="text-[13px] font-medium text-gray-800 dark:text-gray-200">采集模式</span>
                <select
                  value={config.mode}
                  onChange={(event) => onConfigChange({ mode: event.target.value as MonitorConfig["mode"] })}
                  className="h-9 w-full rounded-md border border-black/10 bg-[#ffffff] px-3 text-[13px] text-gray-900 shadow-sm transition-colors hover:bg-gray-50 focus:border-[#005fb8] outline-none dark:border-white/10 dark:bg-[#333333] dark:text-white dark:hover:bg-[#383838] dark:focus:border-[#60cdff]"
                >
                  <option value="direct_frames">直接输出图像帧</option>
                  <option value="video_then_frames">先录视频再抽帧</option>
                </select>
              </label>

              <label className="flex flex-col gap-2">
                <span className="text-[13px] font-medium text-gray-800 dark:text-gray-200">画质模式</span>
                <select
                  value={config.qualityMode}
                  onChange={(event) => onConfigChange({ qualityMode: event.target.value as MonitorConfig["qualityMode"] })}
                  className="h-9 w-full rounded-md border border-black/10 bg-[#ffffff] px-3 text-[13px] text-gray-900 shadow-sm transition-colors hover:bg-gray-50 focus:border-[#005fb8] outline-none dark:border-white/10 dark:bg-[#333333] dark:text-white dark:hover:bg-[#383838] dark:focus:border-[#60cdff]"
                >
                  <option value="copy">MJPEG 直拷贝</option>
                  <option value="q2">Q2 重新编码</option>
                </select>
              </label>
            </div>
          </div>

          <div className="p-4">
            <h4 className={`${sectionLabelStyle} mb-3 flex items-center gap-1.5`}>
              <HardDrive size={14} /> 运行日志
            </h4>
            <div className="h-[140px] overflow-y-auto rounded-lg border border-black/5 bg-[#f8f8f8] p-3 font-mono text-[11px] shadow-inner [&::-webkit-scrollbar-thumb]:bg-black/10 [&::-webkit-scrollbar]:w-1.5 dark:border-white/5 dark:bg-[#1e1e1e] dark:[&::-webkit-scrollbar-thumb]:bg-white/10">
              <div className={wsConnected ? "mb-1 text-green-600 dark:text-green-400" : "mb-1 text-yellow-600 dark:text-yellow-400"}>
                [{new Date().toLocaleTimeString()}] {wsConnected ? "WebSocket 已连接。" : "等待 WebSocket 连接..."}
              </div>
              {runtime.events.slice().reverse().map((event, index) => (
                <div
                  key={`${event.timestamp}-${index}`}
                  className={
                    event.kind === "capture"
                      ? "mb-1 text-blue-600 dark:text-blue-300"
                      : event.kind === "preview"
                        ? "mb-1 text-emerald-600 dark:text-emerald-300"
                        : "mb-1 text-gray-600 dark:text-gray-300"
                  }
                >
                  [{new Date(event.timestamp).toLocaleTimeString()}] {event.message}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
