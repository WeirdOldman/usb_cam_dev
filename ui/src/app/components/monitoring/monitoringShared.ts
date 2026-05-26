export const winCardStyle =
  "rounded-[24px] border border-black/[0.06] bg-white/78 backdrop-blur-xl shadow-[0_18px_45px_rgba(15,23,42,0.06),inset_0_1px_0_rgba(255,255,255,0.75)] dark:border-white/[0.08] dark:bg-[#23272d]/92 dark:shadow-[0_20px_50px_rgba(0,0,0,0.24),inset_0_1px_0_rgba(255,255,255,0.06)]";

export const surfacePanelStyle =
  "rounded-[22px] border border-black/[0.06] bg-white/78 backdrop-blur-sm shadow-[0_12px_28px_rgba(15,23,42,0.05)] dark:border-white/[0.08] dark:bg-[#282d34]/88 dark:shadow-[0_16px_34px_rgba(0,0,0,0.2)]";

export const sectionLabelStyle =
  "text-[11px] font-semibold tracking-[0.16em] text-gray-500 dark:text-gray-400";

export const toolbarTabBaseStyle =
  "inline-flex h-9 items-center gap-2 rounded-xl px-3 text-[13px] font-medium transition-all active:scale-[0.98]";

export const toolbarTabActiveStyle =
  "bg-[#0b5cab] text-white shadow-[0_10px_24px_rgba(11,92,171,0.22)] dark:bg-[#60cdff] dark:text-[#0f172a] dark:shadow-[0_8px_20px_rgba(96,205,255,0.2)]";

export const toolbarTabIdleStyle =
  "text-gray-600 hover:bg-black/5 dark:text-gray-200 dark:hover:bg-white/10";

export const subtleButtonStyle =
  "inline-flex items-center justify-center gap-2 rounded-xl border border-black/10 bg-white/80 px-4 text-sm font-medium text-gray-700 transition-all hover:bg-white hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:bg-[#353a42] dark:text-gray-200 dark:hover:bg-[#3d434c]";

export const primaryButtonStyle =
  "inline-flex items-center justify-center gap-2 rounded-xl bg-[#0b5cab] px-4 text-sm font-medium text-white shadow-[0_10px_24px_rgba(11,92,171,0.2)] transition-all hover:bg-[#0a549d] hover:shadow-[0_12px_28px_rgba(11,92,171,0.26)] disabled:cursor-not-allowed disabled:opacity-50 dark:bg-[#60cdff] dark:text-[#0f172a] dark:hover:bg-[#73d8ff]";

export const formCardStyle =
  "rounded-[22px] border border-black/8 bg-[#fbfcfd]/96 p-5 shadow-[0_10px_24px_rgba(15,23,42,0.04)] dark:border-white/10 dark:bg-[#252a31]/96 dark:shadow-[0_12px_28px_rgba(0,0,0,0.18)]";

export const inputControlStyle =
  "h-10 w-full rounded-xl border border-black/10 bg-white/90 px-3 text-[13px] text-gray-900 outline-none transition-all hover:bg-white focus:border-[#0b5cab] focus:shadow-[0_0_0_4px_rgba(11,92,171,0.10)] disabled:opacity-60 dark:border-white/10 dark:bg-[#333842] dark:text-white dark:hover:bg-[#3a404a] dark:focus:border-[#60cdff] dark:focus:shadow-[0_0_0_4px_rgba(96,205,255,0.12)]";

export function formatTime(seconds: number) {
  const h = Math.floor(seconds / 3600)
    .toString()
    .padStart(2, "0");
  const m = Math.floor((seconds % 3600) / 60)
    .toString()
    .padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return `${h}:${m}:${s}`;
}
