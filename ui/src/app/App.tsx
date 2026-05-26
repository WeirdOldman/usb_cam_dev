import { WinTitleBar } from "./components/WinTitleBar";
import { MonitoringInterface } from "./components/MonitoringInterface";
import { useMonitoringRuntime } from "./components/monitoring/useMonitoringRuntime";

export default function App() {
  const runtime = useMonitoringRuntime();

  return (
    <div className="flex h-screen w-full select-none flex-col overflow-hidden bg-[radial-gradient(circle_at_top_left,#f8fbff_0%,#eef2f7_42%,#e5ebf2_100%)] font-sans text-black dark:bg-[radial-gradient(circle_at_top_left,#2a3440_0%,#1d232b_48%,#161a20_100%)] dark:text-white">
      <WinTitleBar
        onMinimize={runtime.handleWindowMinimize}
        onToggleMaximize={runtime.handleWindowToggleMaximize}
        onClose={runtime.handleWindowClose}
      />

      <main className="relative z-10 flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden border-t border-white/40 bg-white/30 shadow-[inset_0_1px_0_rgba(255,255,255,0.45)] backdrop-blur-[2px] dark:border-white/6 dark:bg-black/10 dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
        <MonitoringInterface runtimeApi={runtime} />
      </main>
    </div>
  );
}
