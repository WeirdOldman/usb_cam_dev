import { Minus, Square, X } from "lucide-react";

type WinTitleBarProps = {
  onMinimize: () => void;
  onToggleMaximize: () => void;
  onClose: () => void;
};

export function WinTitleBar({ onMinimize, onToggleMaximize, onClose }: WinTitleBarProps) {
  return (
    <div className="z-50 flex h-11 w-full items-center justify-between border-b border-black/5 bg-[#eef2f7]/90 px-3 shadow-[0_1px_0_rgba(255,255,255,0.6)] backdrop-blur-xl select-none dark:border-white/8 dark:bg-[#1b2026]/92 dark:shadow-[0_1px_0_rgba(255,255,255,0.04)]">
      <div className="flex h-full flex-1 items-center gap-3">
        <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-[#0b5cab] shadow-[0_8px_16px_rgba(11,92,171,0.22)] dark:bg-[#60cdff] dark:shadow-[0_8px_16px_rgba(96,205,255,0.18)]">
          <div className="h-3.5 w-3.5 rounded-[4px] border border-white/25 bg-white/20 dark:border-black/15 dark:bg-black/10"></div>
        </div>
        <div className="pointer-events-none flex flex-col">
          <span className="text-[12px] font-semibold tracking-[0.12em] text-gray-700 dark:text-gray-200">
            USB 相机 4K25
          </span>
          <span className="text-[10px] tracking-[0.2em] text-gray-500 dark:text-gray-400">监控采集控制台</span>
        </div>
      </div>

      <div className="flex h-full shrink-0 items-center">
        <button
          onClick={onMinimize}
          title="最小化"
          aria-label="最小化"
          className="flex h-9 w-11 items-center justify-center rounded-xl text-gray-600 transition-colors hover:bg-black/5 dark:text-gray-300 dark:hover:bg-white/10"
        >
          <Minus size={16} strokeWidth={1.5} />
        </button>
        <button
          onClick={onToggleMaximize}
          title="最大化"
          aria-label="最大化"
          className="flex h-9 w-11 items-center justify-center rounded-xl text-gray-600 transition-colors hover:bg-black/5 dark:text-gray-300 dark:hover:bg-white/10"
        >
          <Square size={13} strokeWidth={1.5} />
        </button>
        <button
          onClick={onClose}
          title="关闭"
          aria-label="关闭"
          className="flex h-9 w-11 items-center justify-center rounded-xl text-gray-600 transition-colors hover:bg-red-500 hover:text-white dark:text-gray-300"
        >
          <X size={16} strokeWidth={1.5} />
        </button>
      </div>
    </div>
  );
}
