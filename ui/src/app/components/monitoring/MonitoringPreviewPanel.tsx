import { Video } from "lucide-react";

import { sectionLabelStyle } from "./monitoringShared";

type MonitoringPreviewPanelProps = {
  isRunning: boolean;
  resolution: string;
  wsConnected: boolean;
  liveFps: number;
  bitrateMbps: number;
  mjpegUrl: string;
  previewStatus: string;
  previewEnabled: boolean;
  ffmpegPath: string;
};

export function MonitoringPreviewPanel({
  isRunning,
  resolution,
  wsConnected,
  liveFps,
  bitrateMbps,
  mjpegUrl,
  previewStatus,
  previewEnabled,
  ffmpegPath,
}: MonitoringPreviewPanelProps) {
  const streamActive = previewEnabled || isRunning;

  return (
    <div
      className={`relative flex min-h-[320px] flex-1 flex-col overflow-hidden rounded-[28px] border bg-[#0f141b] shadow-[0_30px_60px_rgba(15,23,42,0.22)] transition-colors duration-500 ${
        isRunning
          ? "border-[#0b5cab]/45 shadow-[0_0_0_1px_rgba(11,92,171,0.1),0_30px_60px_rgba(11,92,171,0.16)] dark:border-[#60cdff]/45 dark:shadow-[0_0_0_1px_rgba(96,205,255,0.12),0_24px_50px_rgba(96,205,255,0.12)]"
          : "border-black/20 dark:border-white/10"
      }`}
    >
      <div className="absolute inset-x-0 top-0 z-10 h-24 bg-gradient-to-b from-black/45 via-black/20 to-transparent"></div>

      <div className="absolute left-5 top-5 z-10 flex flex-wrap gap-2">
        <span
          className={`rounded-full border px-3 py-1 text-[11px] font-semibold tracking-[0.18em] shadow-sm backdrop-blur-md transition-all duration-300 ${
            isRunning
              ? "border-red-400/50 bg-red-500/90 text-white shadow-[0_0_10px_rgba(239,68,68,0.4)]"
              : "border-white/10 bg-black/40 text-gray-300"
          }`}
        >
          {isRunning ? "采集中" : "离线"}
        </span>
        <span className="rounded-full border border-white/10 bg-black/35 px-3 py-1 text-[11px] font-medium text-gray-200 backdrop-blur-md">
          {resolution}
        </span>
        <span className="rounded-full border border-white/10 bg-black/35 px-3 py-1 text-[11px] font-medium text-gray-200 backdrop-blur-md">
          {previewEnabled ? previewStatus : "预览已关闭"}
        </span>
      </div>

      <div className="absolute left-5 top-[4.75rem] z-10 max-w-[68%]">
        <div className="rounded-2xl border border-white/10 bg-black/35 px-4 py-3 text-[11px] leading-relaxed text-gray-200 backdrop-blur-md">
          <div className={`${sectionLabelStyle} mb-1 text-white/55 dark:text-white/55`}>运行来源</div>
          <div className="truncate">视频流：{resolution} / MJPEG</div>
          <div className="truncate">FFmpeg：{ffmpegPath || "未检测到"}</div>
        </div>
      </div>

      <div className="relative flex h-full w-full items-center justify-center p-1">
        {!isRunning ? (
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.03] dark:opacity-[0.05]"
            style={{
              backgroundImage:
                "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)",
              backgroundSize: "20px 20px",
            }}
          ></div>
        ) : null}

        {streamActive ? (
          <img
            src={mjpegUrl}
            alt="实时预览"
            className={`h-full w-full object-contain transition-opacity duration-500 ${wsConnected ? "opacity-100" : "opacity-85"}`}
          />
        ) : null}

        {!streamActive ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-black/25 text-gray-300 backdrop-blur-[1px]">
            <div className="rounded-full border border-white/10 bg-white/5 p-4 shadow-inner">
              <Video size={40} className="opacity-60" strokeWidth={1} />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium tracking-[0.12em]">预览未启动</p>
              <p className="mt-1 text-xs text-gray-400">空闲状态默认不拉取视频流，点击右侧按钮再启动预览</p>
            </div>
          </div>
        ) : !wsConnected ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-black/25 text-gray-300 backdrop-blur-[1px]">
            <div className="rounded-full border border-white/10 bg-white/5 p-4 shadow-inner">
              <Video size={40} className="opacity-60" strokeWidth={1} />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium tracking-[0.12em]">等待后端预览流</p>
              <p className="mt-1 text-xs text-gray-400">连接建立后会在这里显示实时画面</p>
            </div>
          </div>
        ) : null}
      </div>

      {isRunning ? (
        <div className="absolute bottom-0 left-0 right-0 flex justify-between bg-gradient-to-t from-black/90 via-black/50 to-transparent p-4 font-mono text-[11px] tracking-wider text-white/90">
          <span className="flex items-center gap-1.5">
            <div className={`h-1.5 w-1.5 rounded-full ${wsConnected ? "animate-pulse bg-green-400" : "bg-yellow-400"}`}></div>
            帧率：{liveFps.toFixed(2)}
          </span>
          <span>码率：{bitrateMbps.toFixed(1)} Mbps</span>
        </div>
      ) : null}
    </div>
  );
}
