import test from "node:test";
import assert from "node:assert/strict";

import {
  describeCapturePhase,
  localizeMonitorText,
  localizeUiLockReason,
  normalizeMonitorPayload,
  resolveMonitorStatusText,
} from "./monitorRuntimeState.js";

const baseRuntime = {
  isRunning: false,
  capturePhase: "idle",
  phaseLabel: "已停止",
  runTime: 0,
  liveFps: 0,
  processedFrames: 0,
  cpuPercent: 0,
  acceleration: "空闲",
  bitrateMbps: 0,
  resolution: "1280x720",
  statusText: "已停止",
  captureLastError: "",
  captureLastErrorReason: "",
  captureLastErrorCode: null,
  captureLastSessionDir: "",
  previewEnabled: true,
  previewActive: false,
  previewStatus: "预览就绪。",
  events: [],
};

test("resolveMonitorStatusText prefers structured capture error over generic status text", () => {
  assert.equal(
    resolveMonitorStatusText(
      {
        capture_last_error: "Selected camera could not be opened: INVALID_CAMERA.",
        status_text: "Control API request failed.",
      },
      "已停止",
    ),
    "所选相机无法打开：INVALID_CAMERA。",
  );
});

test("describeCapturePhase returns localized labels", () => {
  assert.equal(describeCapturePhase("failed", false), "失败");
  assert.equal(describeCapturePhase("starting", true), "启动中");
  assert.equal(describeCapturePhase("stopping", true), "停止中");
});

test("localizeMonitorText converts runtime and preview strings to Chinese", () => {
  assert.equal(localizeMonitorText("System initialized."), "系统已初始化。");
  assert.equal(localizeMonitorText("Waiting for WebSocket..."), "等待 WebSocket 连接...");
  assert.equal(localizeMonitorText("Preview ready."), "预览就绪。");
});

test("localizeUiLockReason reuses shared runtime translations", () => {
  assert.equal(localizeUiLockReason("Cannot stop preview while capture is running"), "采集运行中，不能停止预览。");
});

test("normalizeMonitorPayload surfaces localized backend failure detail", () => {
  const runtime = normalizeMonitorPayload(
    {
      running: false,
      capture_phase: "failed",
      status_text: "Preview stopped.",
      capture_last_error: "Capture completed without producing frames.",
      capture_last_error_reason: "capture_no_frames",
      capture_last_error_code: 21,
      capture_last_session_dir: "E:/captures/session_001",
      preview_enabled: false,
      preview_active: false,
      preview_status: "Preview stopped.",
      events: [{ kind: "preview", message: "Preview stopped.", timestamp: "2026-05-26T00:00:00" }],
    },
    baseRuntime,
  );

  assert.equal(runtime.phaseLabel, "失败");
  assert.equal(runtime.statusText, "采集已结束，但没有产出任何帧。");
  assert.equal(runtime.captureLastErrorReason, "capture_no_frames");
  assert.equal(runtime.captureLastErrorCode, 21);
  assert.equal(runtime.captureLastSessionDir, "E:/captures/session_001");
  assert.equal(runtime.previewStatus, "预览已停止。");
  assert.equal(runtime.events[0].message, "预览已停止。");
});
