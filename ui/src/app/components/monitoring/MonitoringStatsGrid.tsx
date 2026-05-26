import { Activity, Clock, Cpu, Zap } from "lucide-react";

import { formatTime, sectionLabelStyle, surfacePanelStyle, winCardStyle } from "./monitoringShared";

type MonitoringStatsGridProps = {
  runTime: number;
  cpuPercent: number;
  processedFrames: number;
  acceleration: string;
  isRunning: boolean;
};

export function MonitoringStatsGrid({
  runTime,
  cpuPercent,
  processedFrames,
  acceleration,
  isRunning,
}: MonitoringStatsGridProps) {
  return (
    <div className="grid grid-cols-2 gap-4 shrink-0 sm:grid-cols-4">
      <div className={`${winCardStyle} flex flex-col p-2`}>
        <div className={`${surfacePanelStyle} flex h-full flex-col p-4 transition-shadow duration-300 hover:shadow-md`}>
          <div className="mb-2 flex items-center gap-2 text-gray-500 dark:text-gray-400">
            <Clock size={15} strokeWidth={1.5} className="text-[#005fb8] dark:text-[#60cdff]" />
            <span className={sectionLabelStyle}>会话时长</span>
          </div>
          <div className="mt-auto text-2xl font-mono font-light text-gray-900 dark:text-white">{formatTime(runTime)}</div>
        </div>
      </div>

      <div className={`${winCardStyle} flex flex-col p-2`}>
        <div className={`${surfacePanelStyle} flex h-full flex-col p-4 transition-shadow duration-300 hover:shadow-md`}>
          <div className="mb-2 flex items-center gap-2 text-gray-500 dark:text-gray-400">
            <Cpu size={15} strokeWidth={1.5} className="text-[#005fb8] dark:text-[#60cdff]" />
            <span className={sectionLabelStyle}>系统负载</span>
          </div>
          <div className="mt-auto flex items-baseline gap-1">
            <span className="text-2xl font-light text-gray-900 dark:text-white">{Math.round(cpuPercent)}</span>
            <span className="text-[13px] font-medium text-gray-500">%</span>
          </div>
        </div>
      </div>

      <div className={`${winCardStyle} flex flex-col p-2`}>
        <div className={`${surfacePanelStyle} flex h-full flex-col p-4 transition-shadow duration-300 hover:shadow-md`}>
          <div className="mb-2 flex items-center gap-2 text-gray-500 dark:text-gray-400">
            <Activity size={15} strokeWidth={1.5} className="text-[#005fb8] dark:text-[#60cdff]" />
            <span className={sectionLabelStyle}>已处理帧数</span>
          </div>
          <div className="mt-auto text-2xl font-light text-gray-900 dark:text-white">{processedFrames.toLocaleString()}</div>
        </div>
      </div>

      <div className={`${winCardStyle} flex flex-col p-2`}>
        <div className={`${surfacePanelStyle} flex h-full flex-col p-4 transition-shadow duration-300 hover:shadow-md`}>
          <div className="mb-2 flex items-center gap-2 text-gray-500 dark:text-gray-400">
            <Zap size={15} strokeWidth={1.5} className="text-[#005fb8] dark:text-[#60cdff]" />
            <span className={sectionLabelStyle}>硬件加速</span>
          </div>
          <div className="mt-auto flex items-center gap-2">
            <div
              className={`h-2.5 w-2.5 rounded-full shadow-[inset_0_1px_2px_rgba(0,0,0,0.2)] ${
                isRunning
                  ? "bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.4)]"
                  : "bg-gray-300 dark:bg-gray-600"
              }`}
            ></div>
            <span className="text-[14px] font-medium text-gray-900 dark:text-white">{acceleration}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
