from __future__ import annotations

from pydantic import BaseModel, Field


class SelectDllRequest(BaseModel):
    dll_path: str = Field(..., description="Absolute or relative path to SDK DLL")


class MapFunctionsRequest(BaseModel):
    initialize: str
    open_device: str
    close_device: str
    start_capture: str
    stop_capture: str
    read_data: str


class ConnectRequest(BaseModel):
    device_index: int = 0
    export_map: MapFunctionsRequest


class StartCaptureRequest(BaseModel):
    chunk_size: int = 2048


class HardwareStatus(BaseModel):
    dll_path: str = ""
    dll_found: bool = False
    dll_arch: str = "unknown"
    python_arch: str = "unknown"
    electron_arch: str = "unknown"
    dll_loaded: bool = False
    exports: list[str] | None = None
    mapped_functions: dict[str, str] | None = None
    device_detected: bool = False
    device_connected: bool = False
    capture_started: bool = False
    capture_running: bool = False
    real_data_received: bool = False
    zero_data_warning: bool = False
    samples_received: int = 0
    last_min: int | None = None
    last_max: int | None = None
    last_variance: float | None = None
    sdk_error_code: int | None = None
    last_error: str | None = None
    final_status: str = "REAL HARDWARE NOT VERIFIED"
    verification_reason: str = ""


class RpcResponse(BaseModel):
    ok: bool
    message: str | None = None
    status: HardwareStatus | None = None

