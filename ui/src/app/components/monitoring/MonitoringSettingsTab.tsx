import { Settings, ShieldCheck } from "lucide-react";

import {
  formCardStyle,
  primaryButtonStyle,
  sectionLabelStyle,
  subtleButtonStyle,
  surfacePanelStyle,
  winCardStyle,
} from "./monitoringShared";
import type { MonitorConfig, MonitorRuntime } from "./types";

type MonitoringSettingsTabProps = {
  runtime: MonitorRuntime;
  config: MonitorConfig;
  configBusy: boolean;
  onSaveConfig: () => void;
  onCheckFfmpeg: () => void;
};

export function MonitoringSettingsTab({
  runtime,
  config,
  configBusy,
  onSaveConfig,
  onCheckFfmpeg,
}: MonitoringSettingsTabProps) {
  return (
    <div className="animate-in fade-in flex min-h-0 flex-1 items-center justify-center overflow-hidden p-4 duration-300 sm:p-5">
      <div className={`${winCardStyle} flex h-full min-h-0 w-full flex-col overflow-hidden`}>
        <div className="border-b border-black/[0.05] px-5 py-4 dark:border-white/[0.08]">
          <div>
            <div className={sectionLabelStyle}>运行环境</div>
            <h2 className="mt-1 text-lg font-semibold text-gray-800 dark:text-gray-200">运行设置</h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              这里集中管理运行环境、配置持久化，以及打包运行前需要确认的基础状态。
            </p>
          </div>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto p-6 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-black/20 [&::-webkit-scrollbar]:w-1.5 dark:[&::-webkit-scrollbar-thumb]:bg-white/20">
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <div className={formCardStyle}>
              <div className="mb-3 flex items-center gap-2 text-gray-800 dark:text-gray-100">
                <Settings size={17} strokeWidth={1.5} />
                <span className="font-medium">运行配置</span>
              </div>
              <p className="mb-4 text-sm leading-relaxed text-gray-600 dark:text-gray-400">
                将当前界面上的采集参数同步回后端运行态，供后续启动采集和恢复状态时使用。
              </p>
              <button
                onClick={onSaveConfig}
                disabled={configBusy || runtime.uiLocks.config_save_disabled}
                title={runtime.uiLocks.config_save_reason}
                className={`h-11 w-full ${primaryButtonStyle}`}
              >
                {configBusy ? "保存中..." : "保存运行配置"}
              </button>
            </div>

            <div className={formCardStyle}>
              <div className="mb-3 flex items-center gap-2 text-gray-800 dark:text-gray-100">
                <ShieldCheck size={17} strokeWidth={1.5} />
                <span className="font-medium">FFmpeg 状态</span>
              </div>
              <p className="mb-4 text-sm leading-relaxed text-gray-600 dark:text-gray-400">
                检查当前后端识别到的 FFmpeg 可执行文件，并把结果回写到界面状态。
              </p>
              <button
                onClick={onCheckFfmpeg}
                className={`h-11 w-full ${subtleButtonStyle}`}
              >
                检查 FFmpeg
              </button>
            </div>
          </div>

          <div className={formCardStyle}>
            <div className={sectionLabelStyle}>状态快照</div>
            <div className="mb-3 mt-1 text-sm font-semibold text-gray-800 dark:text-gray-100">当前运行快照</div>
            <div className="grid grid-cols-1 gap-4 text-sm lg:grid-cols-2">
              <div className={`${surfacePanelStyle} p-4`}>
                <div className="mb-1 text-gray-500 dark:text-gray-400">FFmpeg 路径</div>
                <div className="break-all text-gray-800 dark:text-gray-100">{config.ffmpegPath || "未检测到"}</div>
              </div>
              <div className={`${surfacePanelStyle} p-4`}>
                <div className="mb-1 text-gray-500 dark:text-gray-400">API 基础地址</div>
                <div className="break-all text-gray-800 dark:text-gray-100">{config.apiBaseUrl}</div>
              </div>
              <div className={`${surfacePanelStyle} p-4`}>
                <div className="mb-1 text-gray-500 dark:text-gray-400">前端开发地址</div>
                <div className="break-all text-gray-800 dark:text-gray-100">{config.frontendDevUrl}</div>
              </div>
              <div className={`${surfacePanelStyle} p-4`}>
                <div className="mb-1 text-gray-500 dark:text-gray-400">后端基础目录</div>
                <div className="break-all text-gray-800 dark:text-gray-100">{config.baseDir || "不可用"}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
