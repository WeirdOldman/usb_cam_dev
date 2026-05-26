import { Camera, FolderOpen, MapPin, SlidersHorizontal } from "lucide-react";
import { useState } from "react";

import { MonitoringPathTab } from "./monitoring/MonitoringPathTab";
import { MonitoringPreviewPanel } from "./monitoring/MonitoringPreviewPanel";
import { MonitoringSettingsTab } from "./monitoring/MonitoringSettingsTab";
import { MonitoringSidebar } from "./monitoring/MonitoringSidebar";
import { MonitoringStatusPanel } from "./monitoring/MonitoringStatusPanel";
import { MonitoringStatsGrid } from "./monitoring/MonitoringStatsGrid";
import {
  toolbarTabActiveStyle,
  toolbarTabBaseStyle,
  toolbarTabIdleStyle,
  subtleButtonStyle,
} from "./monitoring/monitoringShared";
import type { ActiveTab } from "./monitoring/types";
import type { useMonitoringRuntime } from "./monitoring/useMonitoringRuntime";

type MonitoringInterfaceProps = {
  runtimeApi: ReturnType<typeof useMonitoringRuntime>;
};

export function MonitoringInterface({ runtimeApi }: MonitoringInterfaceProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>("main");
  const {
    runtime,
    config,
    wsConnected,
    controlBusy,
    directoryBusy,
    updateConfig,
    handleControlClick,
    handleSaveConfig,
    handlePickOutputDir,
    openOutputDir,
    checkFfmpeg,
    togglePreview,
  } = runtimeApi;

  const tabItems: Array<{ key: ActiveTab; label: string; description: string; icon: typeof Camera }> = [
    { key: "main", label: "主控台", description: "采集与预览", icon: Camera },
    { key: "path", label: "路径与输出", description: "目录与命名", icon: MapPin },
    { key: "settings", label: "运行设置", description: "环境与校验", icon: SlidersHorizontal },
  ];

  return (
    <div className="flex h-full w-full flex-col bg-transparent">
      <div className="shrink-0 border-b border-black/[0.05] bg-white/48 px-4 py-3 backdrop-blur-xl dark:border-white/[0.08] dark:bg-[#20262d]/55">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <div className="text-[11px] font-semibold tracking-[0.18em] text-[#0b5cab] dark:text-[#7ddcff]">
              监控工作台
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
              <h1 className="text-[18px] font-semibold text-gray-900 dark:text-white">采集控制与运行状态</h1>
              <span className="rounded-full border border-black/8 bg-white/70 px-2.5 py-1 text-[11px] font-medium text-gray-600 dark:border-white/8 dark:bg-white/8 dark:text-gray-300">
                当前阶段：{runtime.phaseLabel}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {tabItems.map(({ key, label, description, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                title={label}
                aria-pressed={activeTab === key}
                className={`${toolbarTabBaseStyle} ${
                  activeTab === key ? toolbarTabActiveStyle : toolbarTabIdleStyle
                }`}
              >
                <Icon size={16} strokeWidth={1.7} />
                <span>{label}</span>
                <span className={`hidden text-[11px] lg:inline ${activeTab === key ? "text-white/80 dark:text-black/60" : "text-gray-400 dark:text-gray-500"}`}>
                  {description}
                </span>
              </button>
            ))}

            <button
              onClick={openOutputDir}
              title="打开输出目录"
              aria-label="打开输出目录"
              className={`${subtleButtonStyle} h-9 px-3.5`}
            >
              <FolderOpen size={16} strokeWidth={1.7} />
              <span>打开输出目录</span>
            </button>
          </div>
        </div>
      </div>

      {activeTab === "main" ? (
        <div className="animate-in fade-in flex min-h-0 flex-1 flex-col gap-5 overflow-hidden p-4 duration-300 sm:p-5 lg:flex-row">
          <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-5">
            <MonitoringPreviewPanel
              isRunning={runtime.isRunning}
              resolution={runtime.resolution}
              wsConnected={wsConnected}
              liveFps={runtime.liveFps}
              bitrateMbps={runtime.bitrateMbps}
              mjpegUrl={config.mjpegUrl}
              previewStatus={runtime.previewStatus}
              previewEnabled={runtime.previewEnabled}
              ffmpegPath={config.ffmpegPath}
            />
            <MonitoringStatsGrid
              runTime={runtime.runTime}
              cpuPercent={runtime.cpuPercent}
              processedFrames={runtime.processedFrames}
              acceleration={runtime.acceleration}
              isRunning={runtime.isRunning}
            />
            <MonitoringStatusPanel runtime={runtime} config={config} wsConnected={wsConnected} />
          </div>

          <MonitoringSidebar
            runtime={runtime}
            config={config}
            wsConnected={wsConnected}
            controlBusy={controlBusy}
            onControlClick={handleControlClick}
            onConfigChange={updateConfig}
            onTogglePreview={togglePreview}
          />
        </div>
      ) : activeTab === "path" ? (
        <MonitoringPathTab
          config={config}
          runtime={runtime}
          directoryBusy={directoryBusy}
          onPickOutputDir={handlePickOutputDir}
          onConfigChange={updateConfig}
        />
      ) : (
        <MonitoringSettingsTab
          runtime={runtime}
          config={config}
          configBusy={runtimeApi.configBusy}
          onSaveConfig={handleSaveConfig}
          onCheckFfmpeg={checkFfmpeg}
        />
      )}
    </div>
  );
}
