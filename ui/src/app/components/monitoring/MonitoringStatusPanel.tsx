import { CircleDot, Radio, ShieldCheck, TerminalSquare } from "lucide-react";

import { localizeCaptureReason } from "./monitorRuntimeState";
import { sectionLabelStyle, surfacePanelStyle, winCardStyle } from "./monitoringShared";
import type { MonitorConfig, MonitorRuntime } from "./types";

type MonitoringStatusPanelProps = {
  runtime: MonitorRuntime;
  config: MonitorConfig;
  wsConnected: boolean;
};

export function MonitoringStatusPanel({
  runtime,
  config,
  wsConnected,
}: MonitoringStatusPanelProps) {
  return (
    <div className={`${winCardStyle} grid shrink-0 grid-cols-1 gap-4 p-4 xl:grid-cols-4`}>
      <div className={`${surfacePanelStyle} p-4`}>
        <div className="mb-2 flex items-center gap-2 text-gray-500 dark:text-gray-400">
          <CircleDot size={15} strokeWidth={1.5} className="text-[#005fb8] dark:text-[#60cdff]" />
          <span className={sectionLabelStyle}>采集状态</span>
        </div>
        <div className={`${sectionLabelStyle} mb-2`}>
          阶段：{runtime.phaseLabel}
        </div>
        <div className="text-sm leading-relaxed text-gray-800 dark:text-gray-100">{runtime.statusText}</div>
        {runtime.captureLastErrorReason ? (
          <div className="mt-3 space-y-2 text-[11px] text-gray-500 dark:text-gray-400">
            <div>
              失败原因：
              <span className="ml-1 font-mono text-[#c42b1c] dark:text-[#ff8f6b]">
                {localizeCaptureReason(runtime.captureLastErrorReason, runtime.captureLastError)}
              </span>
            </div>
            {runtime.captureLastSessionDir ? (
              <div className="break-all">
                会话目录：
                <span className="ml-1 font-mono text-gray-700 dark:text-gray-200">{runtime.captureLastSessionDir}</span>
              </div>
            ) : null}
            {runtime.captureLastErrorCode !== null ? (
              <div>
                退出码：
                <span className="ml-1 font-mono text-gray-700 dark:text-gray-200">{runtime.captureLastErrorCode}</span>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className={`${surfacePanelStyle} p-4`}>
        <div className="mb-2 flex items-center gap-2 text-gray-500 dark:text-gray-400">
          <Radio size={15} strokeWidth={1.5} className="text-[#005fb8] dark:text-[#60cdff]" />
          <span className={sectionLabelStyle}>预览状态</span>
        </div>
        <div className="text-sm leading-relaxed text-gray-800 dark:text-gray-100">{runtime.previewStatus}</div>
        <div className="mt-2 text-[11px] text-gray-500 dark:text-gray-400">
          {runtime.previewActive ? "预览流正在输出。" : "预览流当前空闲。"}
        </div>
      </div>

      <div className={`${surfacePanelStyle} p-4`}>
        <div className="mb-2 flex items-center gap-2 text-gray-500 dark:text-gray-400">
          <ShieldCheck size={15} strokeWidth={1.5} className="text-[#005fb8] dark:text-[#60cdff]" />
          <span className={sectionLabelStyle}>连接状态</span>
        </div>
        <div className="text-sm leading-relaxed text-gray-800 dark:text-gray-100">
          {wsConnected ? "WebSocket 已连接。" : "WebSocket 未连接。"}
        </div>
        <div className="mt-2 text-[11px] text-gray-500 dark:text-gray-400">
          MJPEG 源地址：{config.mjpegUrl}
        </div>
      </div>

      <div className={`${surfacePanelStyle} p-4`}>
        <div className="mb-2 flex items-center gap-2 text-gray-500 dark:text-gray-400">
          <TerminalSquare size={15} strokeWidth={1.5} className="text-[#005fb8] dark:text-[#60cdff]" />
          <span className={sectionLabelStyle}>FFmpeg 运行时</span>
        </div>
        <div className="break-all text-sm leading-relaxed text-gray-800 dark:text-gray-100">
          {config.ffmpegPath || "未检测到"}
        </div>
      </div>
    </div>
  );
}
