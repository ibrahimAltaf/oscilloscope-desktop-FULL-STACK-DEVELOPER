from __future__ import annotations

"""
Vercel-deployed FastAPI application for the Oscilloscope Backend.

Cloud-compatible surface only:
  • Full Swagger / OpenAPI interactive docs at /docs
  • Health check at /health
  • Hardware bridge endpoints (return informational cloud responses)
  • Simulated 1 kHz sine demo at /signal/batch
  • Full JSON-RPC protocol reference at /rpc-reference

IMPORTANT: Actual Hantek DLL / USB hardware capture runs locally on the
Windows machine via the Electron desktop app.  This cloud service provides
API documentation, health checks, and simulated demo data ONLY.
"""

import math
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

HARDWARE_MESSAGE = (
    "Hardware operations require the local Electron Windows app. "
    "Install and run Oscilloscope Desktop on your Windows machine "
    "with the Hantek device connected and the SDK DLL available."
)

# ── Request / Response schemas ─────────────────────────────────────────────────


class SelectDllRequest(BaseModel):
    dll_path: str = Field(
        ...,
        description="Absolute or relative path to the Hantek SDK DLL (e.g. HTHardDll.dll)",
        examples=["C:/Hantek/HTHardDll.dll"],
    )


class MapFunctionsRequest(BaseModel):
    initialize: str = Field("HT_Init", description="DLL export name for SDK initialization")
    open_device: str = Field("HT_OpenDevice", description="DLL export name for opening the device")
    close_device: str = Field("HT_CloseDevice", description="DLL export name for closing the device")
    start_capture: str = Field("HT_StartCapture", description="DLL export name for starting capture")
    stop_capture: str = Field("HT_StopCapture", description="DLL export name for stopping capture")
    read_data: str = Field("HT_ReadData", description="DLL export name for reading ADC sample data")


class ConnectRequest(BaseModel):
    device_index: int = Field(0, ge=0, description="USB device index (0 = first connected oscilloscope)")
    export_map: MapFunctionsRequest = Field(default_factory=MapFunctionsRequest)


class StartCaptureRequest(BaseModel):
    chunk_size: int = Field(2048, ge=64, le=65536, description="ADC samples per DLL read call")


class HardwareStatus(BaseModel):
    dll_path: str = Field("", description="Recorded DLL file path")
    dll_found: bool = Field(False, description="DLL file exists on disk")
    dll_arch: str = Field("unknown", description="DLL architecture: x64, x86, or unknown")
    python_arch: str = Field("unknown", description="Python process architecture")
    electron_arch: str = Field("unknown", description="Electron process architecture (x64/ia32)")
    dll_loaded: bool = Field(False, description="DLL successfully loaded into process memory")
    exports: Optional[list[str]] = Field(None, description="Exported function names discovered in DLL")
    mapped_functions: Optional[dict[str, str]] = Field(None, description="Logical name → DLL export name mapping")
    device_detected: bool = Field(False, description="Hantek device detected on USB")
    device_connected: bool = Field(False, description="Device is open and handle is valid")
    capture_started: bool = Field(False, description="Capture started without error")
    capture_running: bool = Field(False, description="Capture thread is alive and reading samples")
    real_data_received: bool = Field(False, description="At least one non-zero ADC sample batch received")
    zero_data_warning: bool = Field(False, description="ADC output consistently zero (cable/probe issue?)")
    samples_received: int = Field(0, description="Total ADC samples received since capture started")
    last_min: Optional[int] = Field(None, description="Minimum ADC code in last batch")
    last_max: Optional[int] = Field(None, description="Maximum ADC code in last batch")
    last_variance: Optional[float] = Field(None, description="Variance of last sample batch")
    sdk_error_code: Optional[int] = Field(None, description="Last Hantek SDK error code (0 = SUCCESS)")
    last_error: Optional[str] = Field(None, description="Last error message from SDK or service")
    final_status: str = Field("REAL HARDWARE NOT VERIFIED", description="12-point verification result")
    verification_reason: str = Field("", description="Human-readable explanation of final_status")


class RpcResponse(BaseModel):
    ok: bool = Field(..., description="Whether the operation succeeded")
    message: Optional[str] = Field(None, description="Human-readable message")
    status: Optional[HardwareStatus] = Field(None, description="Current hardware status snapshot")


class SignalBatch(BaseModel):
    batch_seq: int = Field(..., description="Monotonically increasing batch sequence number")
    t0: float = Field(..., description="Batch start timestamp (Unix epoch seconds)")
    t0_unix: float = Field(..., description="Alias for t0")
    sample_rate_hz: float = Field(..., description="ADC sample rate in Hz")
    sample_count: int = Field(..., description="Number of samples in this batch")
    samples: list[float] = Field(..., description="Sample values in volts (float32)")
    mode: str = Field("simulation", description="'simulation' or 'hardware'")
    server_time_utc: str = Field(..., description="Server wall-clock time at batch generation (ISO-8601)")
    ptp: float = Field(..., description="Peak-to-peak voltage amplitude")
    rms: float = Field(..., description="Root-mean-square voltage")
    volt_div: float = Field(0.5, description="Display: volts per division")
    time_div_s: float = Field(0.001, description="Display: seconds per division")
    drops: int = Field(0, description="Dropped batches due to slow consumer")


class ServiceStatus(BaseModel):
    running: bool = Field(..., description="Whether capture is currently active")
    device_state: str = Field(..., description="State machine: disconnected|connecting|connected|capturing|simulating|error")
    capture_state: str = Field(..., description="Capture state")
    last_error: Optional[str] = Field(None)
    buffer_seconds: float = Field(..., description="Seconds of signal history in circular buffer")
    sample_rate_hz: float = Field(..., description="Configured ADC sample rate in Hz")
    simulation: bool = Field(..., description="True when running in simulation mode (no hardware)")
    reconnect_failures: int = Field(..., description="Consecutive device reconnect failures")
    batches_sent: int = Field(..., description="Total signal batches sent since service start")
    flat_runs: int = Field(..., description="Consecutive zero-amplitude batches (quality gate)")
    drops: int = Field(..., description="Total WebSocket broadcast drops")
    volt_div: float = Field(..., description="Volts per display division")
    time_div_s: float = Field(..., description="Seconds per display division")


class BufferSummary(BaseModel):
    frame_count: int = Field(..., description="Frames in circular buffer")
    approx_duration_s: float = Field(..., description="Approximate buffered signal duration (seconds)")
    max_seconds: float = Field(..., description="Maximum configured buffer depth (seconds)")


# ── Application ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Oscilloscope Backend API",
    version="1.0.0",
    description="""
## Hantek Oscilloscope Backend — Cloud API & Documentation

This is the **cloud-deployed** documentation and API surface for the
[Oscilloscope Desktop](https://github.com/mubeenkhan) application.

---

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│  Vercel Cloud  (this service)                                 │
│  ✓  Swagger / OpenAPI interactive documentation              │
│  ✓  Health check   GET /health                               │
│  ✓  Simulated signal demo   GET /signal/batch                │
│  ✓  RPC protocol reference  GET /rpc-reference               │
│  ✗  No real hardware access                                  │
└──────────────────────────────────────────────────────────────┘
                    ↕  HTTP / REST
┌──────────────────────────────────────────────────────────────┐
│  Windows Local Machine  (Electron Desktop App)               │
│  ✓  Hantek DLL  (HTHardDll.dll / HT6000.dll)  via USB       │
│  ✓  Python hardware_service.py  (JSON-RPC over stdio)        │
│  ✓  Real-time ADC capture  up to 1 MSa/s                     │
│  ✓  Waveform + FFT display                                   │
│  ✓  12-point hardware verification report                    │
└──────────────────────────────────────────────────────────────┘
```

---

### Hardware-Only Endpoints

Endpoints marked **🔒 Hardware Only** require the local Electron Windows app.
Calling them from this cloud service returns an informational message:
> *"Hardware operations require the local Electron Windows app."*

---

### JSON-RPC Protocol (Electron ↔ Python)

The Electron main process communicates with `hardware_service.py` via
**JSON-RPC over stdin / stdout**.
See [`/rpc-reference`](/rpc-reference) for the full method catalog and
event stream format.

---

### Quick Links

| Resource | URL |
|---|---|
| Interactive Docs (Swagger UI) | [`/docs`](/docs) |
| Alternative Docs (ReDoc) | [`/redoc`](/redoc) |
| OpenAPI JSON spec | [`/openapi.json`](/openapi.json) |
| RPC Protocol Reference | [`/rpc-reference`](/rpc-reference) |
| Health Check | [`/health`](/health) |
| Signal Demo | [`/signal/batch`](/signal/batch) |
""",
    contact={"name": "Oscilloscope Desktop"},
    license_info={"name": "MIT"},
    openapi_tags=[
        {"name": "health", "description": "Service health and liveness"},
        {"name": "dll", "description": "DLL inspection and function mapping — 🔒 hardware-only"},
        {"name": "device", "description": "Device connection management — 🔒 hardware-only"},
        {"name": "capture", "description": "Signal capture control — 🔒 hardware-only"},
        {"name": "signal", "description": "Signal data — simulation demo available in cloud"},
        {"name": "hardware", "description": "Hardware status and 12-point verification report"},
        {"name": "logs", "description": "Log streaming reference"},
        {"name": "docs", "description": "API and RPC documentation reference"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory state — resets on cold start (Vercel is stateless by design)
_dll_path: str = ""
_batches_served: int = 0


# ── Internal helpers ───────────────────────────────────────────────────────────


def _cloud_status() -> HardwareStatus:
    return HardwareStatus(
        dll_path=_dll_path,
        verification_reason=(
            "Cloud service — hardware operations require the local Electron Windows app."
        ),
    )


def _sine_batch(
    count: int = 512,
    sample_rate: float = 10_000.0,
    freq: float = 1_000.0,
    amplitude: float = 1.0,
) -> list[float]:
    t0 = time.time() % 1_000.0
    return [
        amplitude * math.sin(2.0 * math.pi * freq * (t0 + i / sample_rate))
        for i in range(count)
    ]


# ── Health ─────────────────────────────────────────────────────────────────────


@app.get("/", tags=["health"], summary="Service root")
async def root() -> dict[str, Any]:
    """Returns service info and quick links to all key endpoints."""
    return {
        "service": "oscilloscope-backend",
        "version": "1.0.0",
        "mode": "cloud",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "openapi_json": "/openapi.json",
        "rpc_reference": "/rpc-reference",
        "signal_demo": "/signal/batch",
        "note": "Hardware capture requires the local Electron Windows app.",
    }


@app.get("/health", tags=["health"], summary="Health check")
async def health() -> dict[str, str]:
    """Returns `ok` with current UTC time. Use to verify the service is reachable."""
    return {
        "status": "ok",
        "mode": "cloud",
        "time_utc": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api-docs", include_in_schema=False)
async def api_docs_redirect() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/swagger", include_in_schema=False)
async def swagger_redirect() -> RedirectResponse:
    return RedirectResponse(url="/docs")


# ── DLL endpoints ──────────────────────────────────────────────────────────────


@app.post(
    "/dll/select",
    tags=["dll"],
    summary="Record DLL path",
    response_model=RpcResponse,
)
async def dll_select(payload: SelectDllRequest) -> RpcResponse:
    """
    Records the path to the Hantek SDK DLL for this cloud session.

    In the Electron app this triggers a file-system check and updates the hardware
    status panel.  In cloud mode the path is stored in memory only — no file-system
    operations are performed.
    """
    global _dll_path
    _dll_path = payload.dll_path
    return RpcResponse(
        ok=True,
        message="DLL path recorded (cloud session only — use Electron app for actual DLL loading)",
        status=_cloud_status(),
    )


@app.post(
    "/dll/inspect",
    tags=["dll"],
    summary="Inspect DLL exports 🔒 Hardware Only",
    response_model=RpcResponse,
)
async def dll_inspect() -> RpcResponse:
    """
    **Hardware Only.**  Runs `dumpbin /exports` on the selected DLL and returns the
    full list of exported function names.

    Used to verify that the required Hantek SDK exports (`HT_Init`, `HT_OpenDevice`,
    `HT_StartCapture`, `HT_ReadData`, etc.) are present before mapping them.

    Requires the Electron app running on a local Windows machine.
    """
    return RpcResponse(ok=False, message=HARDWARE_MESSAGE, status=_cloud_status())


@app.get(
    "/dll/exports",
    tags=["dll"],
    summary="Get cached DLL exports 🔒 Hardware Only",
    response_model=RpcResponse,
)
async def dll_exports() -> RpcResponse:
    """
    **Hardware Only.**  Returns the cached export list populated by `POST /dll/inspect`.

    Requires the Electron app on a local Windows machine.
    """
    return RpcResponse(ok=False, message=HARDWARE_MESSAGE, status=_cloud_status())


# ── Device endpoints ───────────────────────────────────────────────────────────


@app.post(
    "/device/connect",
    tags=["device"],
    summary="Connect hardware device 🔒 Hardware Only",
    response_model=RpcResponse,
)
async def device_connect(payload: ConnectRequest) -> RpcResponse:
    """
    **Hardware Only.**  Loads the Hantek DLL and calls `HT_OpenDevice` with the
    specified device index and export map.

    On success the device handle is retained for subsequent capture calls.
    Requires the Electron app on a local Windows machine with the Hantek oscilloscope
    connected via USB.
    """
    return RpcResponse(ok=False, message=HARDWARE_MESSAGE, status=_cloud_status())


@app.post(
    "/device/disconnect",
    tags=["device"],
    summary="Disconnect device 🔒 Hardware Only",
    response_model=RpcResponse,
)
async def device_disconnect() -> RpcResponse:
    """
    **Hardware Only.**  Calls `HT_CloseDevice` and releases the DLL handle.

    Requires the Electron app on a local Windows machine.
    """
    return RpcResponse(ok=False, message=HARDWARE_MESSAGE, status=_cloud_status())


# ── Capture endpoints ──────────────────────────────────────────────────────────


@app.post(
    "/capture/start",
    tags=["capture"],
    summary="Start real-time capture 🔒 Hardware Only",
    response_model=RpcResponse,
)
async def capture_start(payload: StartCaptureRequest) -> RpcResponse:
    """
    **Hardware Only.**  Starts the background capture thread that continuously calls
    `HT_ReadData` and emits `sample_batch` events to the Electron renderer.

    `chunk_size` controls how many ADC samples are read per DLL call (default 2048).
    Requires an open device connection via the Electron app.
    """
    return RpcResponse(ok=False, message=HARDWARE_MESSAGE, status=_cloud_status())


@app.post(
    "/capture/stop",
    tags=["capture"],
    summary="Stop capture 🔒 Hardware Only",
    response_model=RpcResponse,
)
async def capture_stop() -> RpcResponse:
    """
    **Hardware Only.**  Signals the capture thread to stop and waits for clean exit.

    Requires the Electron app on a local Windows machine.
    """
    return RpcResponse(ok=False, message=HARDWARE_MESSAGE, status=_cloud_status())


# ── Signal endpoints ───────────────────────────────────────────────────────────


@app.get(
    "/signal/batch",
    tags=["signal"],
    summary="Get signal batch (simulation demo in cloud)",
    response_model=SignalBatch,
)
async def signal_batch() -> SignalBatch:
    """
    Returns a signal batch.

    **Cloud mode:** Returns a simulated 1 kHz sine wave sampled at 10 kSa/s for
    demo and integration testing.

    **Local Electron app:** Returns real ADC samples from the Hantek oscilloscope
    at the configured sample rate (up to 1 MSa/s), scaled to volts using the
    configured full-scale range.
    """
    global _batches_served
    _batches_served += 1
    t0 = time.time()
    sample_rate = 10_000.0
    count = 512
    freq = 1_000.0
    amplitude = 1.0
    samples = _sine_batch(count, sample_rate, freq, amplitude)
    return SignalBatch(
        batch_seq=_batches_served,
        t0=t0,
        t0_unix=t0,
        sample_rate_hz=sample_rate,
        sample_count=count,
        samples=samples,
        mode="simulation",
        server_time_utc=datetime.now(timezone.utc).isoformat(),
        ptp=2.0 * amplitude,
        rms=amplitude / math.sqrt(2.0),
    )


@app.get(
    "/buffer/summary",
    tags=["signal"],
    summary="Circular buffer summary",
    response_model=BufferSummary,
)
async def buffer_summary() -> BufferSummary:
    """
    Returns a summary of the signal circular buffer.

    In cloud mode the buffer is always empty — capture is hardware-only.
    The Electron app maintains up to 120 seconds of ADC history in a thread-safe
    circular buffer.
    """
    return BufferSummary(frame_count=0, approx_duration_s=0.0, max_seconds=120.0)


# ── Hardware status ────────────────────────────────────────────────────────────


@app.get(
    "/hardware/status",
    tags=["hardware"],
    summary="Current hardware status",
    response_model=RpcResponse,
)
async def hardware_status() -> RpcResponse:
    """
    Returns the current hardware verification status.

    In cloud mode all hardware fields are `false` / empty.
    Connect via the Electron app for real hardware status.
    """
    return RpcResponse(
        ok=True,
        message="Cloud mode — no hardware connected",
        status=_cloud_status(),
    )


@app.get(
    "/hardware/report",
    tags=["hardware"],
    summary="12-point hardware verification report",
    response_model=RpcResponse,
)
async def hardware_report() -> RpcResponse:
    """
    Returns the 12-point hardware verification report.

    **Verification checklist:**
    1. DLL file found on disk
    2. DLL architecture matches Python process (x64/x86)
    3. DLL successfully loaded into process memory
    4. Required SDK exports present in DLL
    5. SDK functions mapped to logical names
    6. Device detected on USB bus
    7. Device connected (handle valid after `HT_OpenDevice`)
    8. Capture started without SDK error
    9. Capture thread alive and polling
    10. Real (non-zero) ADC data received
    11. No persistent zero-data warning (cable / probe OK)
    12. SDK error code is 0 (SUCCESS) throughout

    In cloud mode all checks are `false`.  The Electron app generates the real report.
    """
    return RpcResponse(
        ok=True,
        message="Cloud verification report (no hardware connected)",
        status=_cloud_status(),
    )


@app.get(
    "/status",
    tags=["hardware"],
    summary="Service status",
    response_model=ServiceStatus,
)
async def service_status() -> ServiceStatus:
    """Returns current service status.  Cloud mode: `simulation=true`, `running=false`."""
    return ServiceStatus(
        running=False,
        device_state="disconnected",
        capture_state="idle",
        last_error=None,
        buffer_seconds=0.0,
        sample_rate_hz=10_000.0,
        simulation=True,
        reconnect_failures=0,
        batches_sent=_batches_served,
        flat_runs=0,
        drops=0,
        volt_div=0.5,
        time_div_s=0.001,
    )


# ── Logs ───────────────────────────────────────────────────────────────────────


@app.get(
    "/logs",
    tags=["logs"],
    summary="Log stream reference",
)
async def logs() -> dict[str, Any]:
    """
    In the Electron app, logs are emitted via the Python→Electron IPC event stream
    (not HTTP).  This endpoint returns reference information about the log format.
    """
    return {
        "note": (
            "Logs are streamed via the Python ↔ Electron IPC event stream in the "
            "desktop app, not HTTP.  This cloud endpoint is for reference only."
        ),
        "event_type": "log",
        "format": {
            "level": "DEBUG | INFO | WARNING | ERROR",
            "message": "string",
        },
        "example_event": {
            "event": "log",
            "payload": {
                "level": "INFO",
                "message": "Capture started — chunk_size=2048",
            },
        },
        "cloud_logs": "This cloud service logs to Vercel's built-in log aggregator.",
    }


# ── RPC Reference ──────────────────────────────────────────────────────────────


@app.get(
    "/rpc-reference",
    tags=["docs"],
    summary="JSON-RPC protocol reference",
)
async def rpc_reference() -> dict[str, Any]:
    """
    Full reference for the JSON-RPC protocol used between the Electron main process
    and the Python `hardware_service.py` subprocess.

    **Transport:** Electron spawns Python via `child_process.spawn`.
    Requests are written to Python's **stdin** as newline-delimited JSON.
    Responses and push events are read from Python's **stdout** as
    newline-delimited JSON.
    """
    return {
        "protocol": "JSON-RPC over stdin/stdout (newline-delimited)",
        "transport": (
            "Electron spawns Python subprocess via child_process.spawn; "
            "requests via stdin, responses and events via stdout"
        ),
        "request_format": {
            "id": "<uuid-string>",
            "method": "<method_name>",
            "params": {"<param_key>": "<param_value>"},
        },
        "response_format": {
            "event": "rpc_response",
            "payload": {
                "request_id": "<uuid-string matching request id>",
                "ok": True,
                "result": {"<key>": "<value>"},
                "error": None,
            },
        },
        "pushed_events": {
            "description": "Python emits these events unprompted on state changes",
            "status": {
                "description": "Full HardwareStatus payload — emitted on every state change",
                "when": "After every RPC call or capture state transition",
            },
            "sample_batch": {
                "description": "Real-time ADC sample batch from the capture thread",
                "fields": {
                    "timestamp_unix": "float — batch start time (Unix epoch)",
                    "samples": "list[int] — raw ADC int16 codes",
                    "count": "int — number of samples in this batch",
                    "min": "int — minimum ADC code",
                    "max": "int — maximum ADC code",
                    "variance": "float — variance of ADC codes",
                },
            },
            "log": {
                "description": "Structured log message from the Python service",
                "fields": {"level": "str", "message": "str"},
            },
        },
        "methods": [
            {
                "name": "select_dll",
                "params": {"dll_path": "string — absolute Windows path to SDK DLL"},
                "description": "Record DLL path and check whether the file exists on disk",
                "hardware_only": False,
                "emits": ["status"],
            },
            {
                "name": "inspect_dll",
                "params": {},
                "description": (
                    "Run dumpbin /exports on the selected DLL; populate export list in "
                    "HardwareStatus.exports"
                ),
                "hardware_only": True,
                "emits": ["status"],
            },
            {
                "name": "map_sdk_functions",
                "params": {
                    "initialize": "DLL export name",
                    "open_device": "DLL export name",
                    "close_device": "DLL export name",
                    "start_capture": "DLL export name",
                    "stop_capture": "DLL export name",
                    "read_data": "DLL export name",
                },
                "description": "Map logical SDK function names to actual DLL export names",
                "hardware_only": True,
                "emits": ["status"],
            },
            {
                "name": "connect_device",
                "params": {
                    "device_index": "int (default 0)",
                    "export_map": "MapFunctionsRequest object",
                },
                "description": "Load DLL and call HT_OpenDevice; store handle for subsequent calls",
                "hardware_only": True,
                "emits": ["status"],
            },
            {
                "name": "start_capture",
                "params": {"chunk_size": "int (default 2048) — samples per DLL read call"},
                "description": "Start background capture thread (calls HT_ReadData in a loop)",
                "hardware_only": True,
                "emits": ["status", "sample_batch (continuous)", "log"],
            },
            {
                "name": "stop_capture",
                "params": {},
                "description": "Signal capture thread to stop and wait for clean exit",
                "hardware_only": True,
                "emits": ["status"],
            },
            {
                "name": "get_status",
                "params": {},
                "description": "Return full HardwareStatus (same payload as status push event)",
                "hardware_only": False,
                "emits": ["rpc_response with status field"],
            },
            {
                "name": "disconnect_device",
                "params": {},
                "description": "Call HT_CloseDevice, unload DLL, reset all device state",
                "hardware_only": True,
                "emits": ["status"],
            },
            {
                "name": "shutdown",
                "params": {},
                "description": "Stop all threads and exit the Python service process gracefully",
                "hardware_only": False,
                "emits": [],
            },
        ],
        "sdk_export_names": {
            "description": "Common Hantek DLL export names (may vary by DLL version)",
            "variants": {
                "HTHardDll.dll": ["HT_Init", "HT_OpenDevice", "HT_CloseDevice", "HT_StartCapture", "HT_StopCapture", "HT_ReadData"],
                "HT6000.dll": ["HT6000_Open", "HT6000_Close", "HT6000_StartCapture", "HT6000_StopCapture", "HT6000_ReadData"],
                "fuzzy_fallback": "The SDK wrapper also tries common prefix variants (HTHard_*, HT_*, HT6000_*)",
            },
        },
        "verification_checklist": [
            "1. DLL file found on disk",
            "2. DLL architecture matches Python process (x64/x86)",
            "3. DLL loaded into process memory without error",
            "4. Required SDK exports present in DLL",
            "5. SDK functions mapped to logical names",
            "6. Device detected on USB bus",
            "7. Device connected — handle valid after HT_OpenDevice",
            "8. Capture started without SDK error",
            "9. Capture thread alive and polling",
            "10. Real (non-zero) ADC data received",
            "11. No persistent zero-data warning",
            "12. SDK error code is 0 (SUCCESS) throughout",
        ],
    }
