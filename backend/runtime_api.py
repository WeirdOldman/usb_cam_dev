from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


class StartCaptureRequest(BaseModel):
    mode: str = "direct_frames"
    output_dir: str | None = None
    image_prefix: str = "img"
    quality_mode: str = "copy"
    delete_video_after_extract: bool = False
    camera_name: str = "imx678' UVC "


class UpdateConfigRequest(BaseModel):
    camera_name: str | None = None
    output_dir: str | None = None
    image_prefix: str | None = None
    mode: str | None = None
    quality_mode: str | None = None
    delete_video_after_extract: bool | None = None


class SelectOutputDirRequest(BaseModel):
    current_dir: str | None = None


class RuntimeConfigResponse(BaseModel):
    camera_name: str
    output_dir: str
    image_prefix: str
    mode: str
    quality_mode: str
    delete_video_after_extract: bool
    ffmpeg_path: str
    base_dir: str
    frontend_dev_url: str
    api_base_url: str
    mjpeg_url: str
    websocket_url: str
    control_start_url: str
    control_stop_url: str
    auto_stop: dict


@dataclass(frozen=True)
class RuntimeApiConfig:
    title: str
    api_host: str
    api_port: int
    cors_origins: tuple[str, ...]
    mjpeg_path: str
    ws_path: str
    control_start_path: str
    control_stop_path: str
    config_path: str
    select_output_dir_path: str
    window_minimize_path: str
    window_toggle_maximize_path: str
    window_close_path: str
    open_output_dir_path: str
    ffmpeg_status_path: str
    preview_start_path: str
    preview_stop_path: str
    events_path: str
    camera_devices_path: str
    monitor_path: str
    open_directory_dialog: Callable[[str | None], str | None]
    require_window: Callable[[], Any]
    open_system_path: Callable[[str], None]
    list_camera_devices: Callable[[str | None], list[str]]
    resolve_ffmpeg_path: Callable[[], str]
    validate_runtime_options: Callable[[str, str], None]

    @property
    def api_base_url(self) -> str:
        return f"http://{self.api_host}:{self.api_port}"

    @property
    def websocket_base_url(self) -> str:
        return f"ws://{self.api_host}:{self.api_port}"


def create_runtime_app(*, runtime_state: Any, config: RuntimeApiConfig) -> FastAPI:
    app = FastAPI(title=config.title)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "status": "ok",
            "mjpeg_url": f"{config.api_base_url}{config.mjpeg_path}",
            "websocket_url": f"{config.websocket_base_url}{config.ws_path}",
            "control_start_url": f"{config.api_base_url}{config.control_start_path}",
            "control_stop_url": f"{config.api_base_url}{config.control_stop_path}",
            "config_url": f"{config.api_base_url}{config.config_path}",
        }

    @app.get(config.config_path, response_model=RuntimeConfigResponse)
    async def get_config() -> RuntimeConfigResponse:
        return RuntimeConfigResponse(**runtime_state.control_config())

    @app.put(config.config_path, response_model=RuntimeConfigResponse)
    async def update_config(request: UpdateConfigRequest) -> RuntimeConfigResponse:
        with runtime_state.control_lock:
            if runtime_state.capture_state.capture_running:
                raise HTTPException(status_code=409, detail="Cannot update config while capture is running")
            next_mode = request.mode if request.mode is not None else runtime_state.mode
            next_quality_mode = request.quality_mode if request.quality_mode is not None else runtime_state.quality_mode
            config.validate_runtime_options(next_mode, next_quality_mode)
            runtime_state.apply_config_update(request)
            runtime_state.refresh_monitor_payload()
            return RuntimeConfigResponse(**runtime_state.control_config())

    @app.post(config.select_output_dir_path)
    async def select_output_dir(request: SelectOutputDirRequest) -> dict[str, Any]:
        with runtime_state.control_lock:
            if runtime_state.capture_state.capture_running:
                raise HTTPException(status_code=409, detail="Cannot select output dir while capture is running")
            selected_dir = config.open_directory_dialog(request.current_dir)
            if not selected_dir:
                runtime_state.append_event("system", "Output directory selection cancelled.")
                return {"ok": False, "selected_dir": None, "config": runtime_state.control_config()}
            runtime_state.output_dir = Path(selected_dir)
            runtime_state.append_event("system", f"Output directory updated: {selected_dir}")
            runtime_state.refresh_monitor_payload(status_override="Output directory updated.")
            return {"ok": True, "selected_dir": selected_dir, "config": runtime_state.control_config()}

    @app.post(config.window_minimize_path)
    async def window_minimize() -> dict[str, bool]:
        config.require_window().minimize()
        return {"ok": True}

    @app.post(config.window_toggle_maximize_path)
    async def window_toggle_maximize() -> dict[str, bool]:
        window = config.require_window()
        if getattr(window, "state", None) == "maximized":
            window.restore()
        else:
            window.maximize()
        return {"ok": True}

    @app.post(config.window_close_path)
    async def window_close() -> dict[str, bool]:
        config.require_window().destroy()
        return {"ok": True}

    @app.post(config.open_output_dir_path)
    async def open_output_dir() -> dict[str, Any]:
        config.open_system_path(str(runtime_state.output_dir))
        runtime_state.append_event("system", f"Opened output directory: {runtime_state.output_dir}")
        return {"ok": True, "path": str(runtime_state.output_dir)}

    @app.get(config.ffmpeg_status_path)
    async def ffmpeg_status() -> dict[str, Any]:
        ffmpeg = config.resolve_ffmpeg_path()
        runtime_state.ffmpeg_path = ffmpeg
        runtime_state.append_event("system", "FFmpeg available." if ffmpeg else "FFmpeg not found.")
        runtime_state.refresh_monitor_payload(status_override="FFmpeg available." if ffmpeg else "FFmpeg not found.")
        return {"ok": True, "ffmpeg_found": bool(ffmpeg), "ffmpeg_path": ffmpeg}

    @app.get(config.camera_devices_path)
    async def camera_devices() -> dict[str, Any]:
        ffmpeg = runtime_state.ffmpeg_path or config.resolve_ffmpeg_path()
        runtime_state.ffmpeg_path = ffmpeg
        devices = config.list_camera_devices(ffmpeg)
        return {"ok": True, "devices": devices, "selected_device": runtime_state.camera_name}

    @app.post(config.preview_start_path)
    async def preview_start() -> dict[str, Any]:
        runtime_state.preview_enabled = True
        if not runtime_state.capture_state.capture_running:
            runtime_state.ensure_preview_running()
        runtime_state.append_event("preview", "Preview started.")
        runtime_state.refresh_monitor_payload(status_override="Preview started.")
        return {
            "ok": True,
            "preview_enabled": runtime_state.preview_enabled,
            "preview_status": runtime_state.preview_status_text(),
        }

    @app.post(config.preview_stop_path)
    async def preview_stop() -> dict[str, Any]:
        if runtime_state.capture_state.capture_running:
            raise HTTPException(status_code=409, detail="Cannot stop preview while capture is running")
        runtime_state.preview_enabled = False
        runtime_state.stop_preview(wait=True)
        runtime_state.append_event("preview", "Preview stopped.")
        runtime_state.refresh_monitor_payload(status_override="Preview stopped.")
        return {
            "ok": True,
            "preview_enabled": runtime_state.preview_enabled,
            "preview_status": runtime_state.preview_status_text(),
        }

    @app.get(config.mjpeg_path)
    async def mjpeg_stream() -> StreamingResponse:
        return StreamingResponse(
            runtime_state.iter_preview_mjpeg_chunks(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.get(config.events_path)
    async def get_events() -> dict[str, Any]:
        return {"ok": True, "events": runtime_state.recent_events()}

    @app.get(config.monitor_path)
    async def get_monitor() -> dict[str, Any]:
        return runtime_state.snapshot()

    @app.post(config.control_start_path)
    async def start_capture(request: StartCaptureRequest) -> dict[str, Any]:
        config.validate_runtime_options(request.mode, request.quality_mode)
        return runtime_state.start_capture(request)

    @app.post(config.control_stop_path)
    async def stop_capture() -> dict[str, Any]:
        return runtime_state.stop_capture()

    @app.websocket(config.ws_path)
    async def monitor_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                payload = runtime_state.snapshot()
                await websocket.send_json(payload)
                await asyncio.sleep(0.5)
        except (WebSocketDisconnect, RuntimeError):
            return

    return app
