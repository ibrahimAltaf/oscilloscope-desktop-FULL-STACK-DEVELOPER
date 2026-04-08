from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from oscilloscope_backend.core.broadcaster import SignalBroadcaster
from oscilloscope_backend.core.capture_service import CaptureService
from oscilloscope_backend.core.device_manager import DeviceManager
from oscilloscope_backend.hantek.sdk import CallingConvention, HantekSDK
from oscilloscope_backend.processing.buffer import CircularSampleBuffer
from oscilloscope_backend.utils.config import Settings, get_settings
from oscilloscope_backend.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class StartStopResponse(BaseModel):
    ok: bool
    message: str
    running: bool


class StatusResponse(BaseModel):
    running: bool
    device_state: str
    capture_state: str
    buffer_seconds: float
    sample_rate_hz: float
    simulation: bool
    reconnect_failures: int
    batches_sent: int
    flat_runs: int
    drops: int
    volt_div: float
    time_div_s: float


class BufferSummaryResponse(BaseModel):
    frame_count: int
    approx_duration_s: float
    max_seconds: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings=settings)
    loop = asyncio.get_running_loop()

    sdk = HantekSDK(
        settings.hantek_dll_path,
        device_index=settings.hantek_device_index,
        adc_volts_full_scale=settings.hantek_adc_volts_full_scale,
        calling_convention=(
            CallingConvention.STDCALL
            if settings.hantek_stdcall
            else CallingConvention.CDECL
        ),
    )
    sample_buffer = CircularSampleBuffer(settings.buffer_seconds, settings.sample_rate_hz)
    broadcaster = SignalBroadcaster(loop)
    device_manager = DeviceManager.configure(
        sdk,
        simulation_enabled=settings.simulation_enabled,
        reconnect_interval_s=settings.reconnect_interval_s,
        reconnect_jitter_s=settings.reconnect_jitter_s,
        reconnect_max_attempts=settings.reconnect_max_attempts,
    )
    capture = CaptureService(
        settings,
        sdk,
        device_manager,
        sample_buffer,
        broadcaster,
    )

    app.state.settings = settings
    app.state.sdk = sdk
    app.state.sample_buffer = sample_buffer
    app.state.broadcaster = broadcaster
    app.state.device_manager = device_manager
    app.state.capture = capture

    logger.info(
        "Oscilloscope API ready (host=%s port=%s dll=%s buffer_s=%s)",
        settings.host,
        settings.port,
        settings.hantek_dll_path or "none (simulation)",
        settings.buffer_seconds,
    )
    yield
    capture.shutdown()
    DeviceManager.reset_for_testing()
    logger.info("Oscilloscope API shutdown complete")


app = FastAPI(
    title="Oscilloscope Backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _state(request: Request) -> Any:
    return request.app.state


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/buffer/summary", response_model=BufferSummaryResponse)
async def buffer_summary(request: Request) -> BufferSummaryResponse:
    buf: CircularSampleBuffer = _state(request).sample_buffer
    frames = buf.snapshot_frames()
    return BufferSummaryResponse(
        frame_count=len(frames),
        approx_duration_s=buf.approx_duration_s(),
        max_seconds=buf.max_seconds,
    )


@app.get("/status", response_model=StatusResponse)
async def status(request: Request) -> StatusResponse:
    st: Settings = _state(request).settings
    cap: CaptureService = _state(request).capture
    dm: DeviceManager = _state(request).device_manager
    return StatusResponse(
        running=cap.is_running,
        device_state=dm.state.value,
        capture_state=dm.state.value,
        buffer_seconds=st.buffer_seconds,
        sample_rate_hz=st.sample_rate_hz,
        simulation=dm.is_simulating,
        reconnect_failures=dm.reconnect_failures,
        batches_sent=cap.batches_sent,
        flat_runs=cap.flat_runs,
        drops=_state(request).broadcaster.drop_count,
        volt_div=st.volt_div,
        time_div_s=st.time_div_s,
    )


@app.api_route("/start", methods=["GET", "POST"], response_model=StartStopResponse)
async def start_capture(request: Request) -> StartStopResponse:
    cap: CaptureService = _state(request).capture
    if cap.is_running:
        return StartStopResponse(ok=True, message="Already running", running=True)
    cap.start()
    return StartStopResponse(ok=True, message="Capture started", running=True)


@app.api_route("/stop", methods=["GET", "POST"], response_model=StartStopResponse)
async def stop_capture(request: Request) -> StartStopResponse:
    cap: CaptureService = _state(request).capture
    if not cap.is_running:
        return StartStopResponse(ok=True, message="Already stopped", running=False)
    cap.stop()
    return StartStopResponse(ok=True, message="Capture stopped", running=False)


@app.websocket("/ws/signal")
async def websocket_signal(websocket: WebSocket) -> None:
    await websocket.accept()
    st: Settings = websocket.app.state.settings
    broadcaster: SignalBroadcaster = websocket.app.state.broadcaster
    q = broadcaster.register(st.ws_queue_max_batches)
    logger.info("WebSocket client connected")
    try:
        while True:
            batch = await q.get()
            await websocket.send_json(batch)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    finally:
        broadcaster.unregister(q)
