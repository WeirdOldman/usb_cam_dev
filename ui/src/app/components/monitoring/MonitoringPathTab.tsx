import { MapPin } from "lucide-react";

import {
  formCardStyle,
  inputControlStyle,
  sectionLabelStyle,
  subtleButtonStyle,
  winCardStyle,
} from "./monitoringShared";
import type { MonitorConfig, MonitorRuntime } from "./types";

type MonitoringPathTabProps = {
  config: MonitorConfig;
  runtime: MonitorRuntime;
  directoryBusy: boolean;
  onPickOutputDir: () => void;
  onConfigChange: (patch: Partial<MonitorConfig>) => void;
};

export function MonitoringPathTab({
  config,
  runtime,
  directoryBusy,
  onPickOutputDir,
  onConfigChange,
}: MonitoringPathTabProps) {
  return (
    <div className="animate-in fade-in flex min-h-0 flex-1 items-center justify-center overflow-hidden p-4 duration-300 sm:p-5">
      <div className={`${winCardStyle} flex h-full min-h-0 w-full flex-col overflow-hidden`}>
        <div className="border-b border-black/[0.05] px-5 py-4 dark:border-white/[0.08]">
          <div>
            <div className={sectionLabelStyle}>路径与输出</div>
            <h2 className="mt-1 text-lg font-semibold text-gray-800 dark:text-gray-200">路径配置</h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              这里管理当前采集任务的输出目录、图像前缀以及中间视频保留策略。
            </p>
          </div>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto p-6 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-black/20 [&::-webkit-scrollbar]:w-1.5 dark:[&::-webkit-scrollbar-thumb]:bg-white/20">
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.4fr_0.9fr]">
            <div className={`${formCardStyle} space-y-4`}>
              <div className="flex items-center gap-2 text-gray-800 dark:text-gray-100">
                <MapPin size={18} strokeWidth={1.5} />
                <span className="font-medium">输出路由</span>
              </div>

              <label className="flex flex-col gap-2">
                <span className="text-[13px] font-medium text-gray-800 dark:text-gray-200">输出目录</span>
                <div className="flex gap-2">
                  <input
                    value={config.outputDir}
                    onChange={(event) => onConfigChange({ outputDir: event.target.value })}
                    disabled={runtime.uiLocks.path_edit_disabled}
                    title={runtime.uiLocks.path_edit_reason}
                    className={`${inputControlStyle} flex-1`}
                  />
                  <button
                    onClick={onPickOutputDir}
                    disabled={runtime.uiLocks.path_edit_disabled || directoryBusy}
                    title={runtime.uiLocks.path_edit_reason}
                    className={`${subtleButtonStyle} h-10 px-4`}
                  >
                    {directoryBusy ? "处理中..." : "浏览"}
                  </button>
                </div>
              </label>

              <label className="flex flex-col gap-2">
                <span className="text-[13px] font-medium text-gray-800 dark:text-gray-200">图像前缀</span>
                <input
                  value={config.imagePrefix}
                  onChange={(event) => onConfigChange({ imagePrefix: event.target.value })}
                  disabled={runtime.uiLocks.path_edit_disabled}
                  title={runtime.uiLocks.path_edit_reason}
                  className={inputControlStyle}
                />
              </label>

              <label className="flex items-center justify-between rounded-[20px] border border-black/10 bg-white/70 px-4 py-3 dark:border-white/10 dark:bg-black/10">
                <div>
                  <div className="text-[13px] font-medium text-gray-800 dark:text-gray-200">抽帧后删除视频</div>
                  <div className="text-[12px] text-gray-500 dark:text-gray-400">仅对 `video_then_frames` 模式生效</div>
                </div>
                <button
                  onClick={() => onConfigChange({ deleteVideoAfterExtract: !config.deleteVideoAfterExtract })}
                  disabled={runtime.uiLocks.path_edit_disabled}
                  title={runtime.uiLocks.path_edit_reason}
                  className={`relative h-5 w-10 rounded-full border transition-colors duration-200 ease-in-out disabled:opacity-60 ${
                    config.deleteVideoAfterExtract
                      ? "border-[#005fb8] bg-[#005fb8] dark:border-[#60cdff] dark:bg-[#60cdff]"
                      : "border-gray-300 bg-[#f3f3f3] hover:bg-gray-200 dark:border-gray-600 dark:bg-[#333] dark:hover:bg-[#444]"
                  }`}
                >
                  <div
                    className={`absolute top-[3px] h-3 w-3 rounded-full shadow-sm transition-transform duration-200 ${
                      config.deleteVideoAfterExtract
                        ? "translate-x-[22px] bg-white dark:bg-black"
                        : "translate-x-[4px] bg-gray-500 dark:bg-gray-400"
                    }`}
                  ></div>
                </button>
              </label>
            </div>

            <div className={`${formCardStyle}`}>
              <div className={sectionLabelStyle}>使用说明</div>
              <div className="mb-3 mt-1 text-sm font-semibold text-gray-800 dark:text-gray-100">路径说明</div>
              <div className="space-y-3 text-sm leading-relaxed text-gray-600 dark:text-gray-400">
                <p>这个页面只承接“输出与路径”相关的参数，不再和运行时状态、FFmpeg 工具状态混在一起。</p>
                <p>采集运行中不允许修改这些值，避免把输出路径和文件命名切到半途状态。</p>
                <p>如果后续要扩展更复杂的路径模板、多路输出和任务路由，可以继续在这里扩展。</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
