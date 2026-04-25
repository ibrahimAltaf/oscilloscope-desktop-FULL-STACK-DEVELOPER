from __future__ import annotations

from fastapi import FastAPI

from backend.schemas.hardware import (
    ConnectRequest,
    HardwareStatus,
    RpcResponse,
    SelectDllRequest,
    StartCaptureRequest,
)

app = FastAPI(
    title="Hardware Bridge API",
    version="1.0.0",
    description="RPC-style API contract for Hantek DLL integration and verification reporting.",
)

_status = HardwareStatus(verification_reason="Service not wired to hardware runtime in HTTP mode.")


@app.post("/dll/select", response_model=RpcResponse)
def select_dll(payload: SelectDllRequest) -> RpcResponse:
    _status.dll_path = payload.dll_path
    return RpcResponse(ok=True, message="DLL path recorded", status=_status)


@app.post("/dll/inspect", response_model=RpcResponse)
def inspect_dll() -> RpcResponse:
    return RpcResponse(ok=False, message="Use Electron RPC bridge for live inspection", status=_status)


@app.get("/dll/exports", response_model=RpcResponse)
def get_exports() -> RpcResponse:
    return RpcResponse(ok=True, status=_status)


@app.post("/device/connect", response_model=RpcResponse)
def connect_device(payload: ConnectRequest) -> RpcResponse:
    _status.mapped_functions = payload.export_map.model_dump()
    return RpcResponse(ok=False, message="Use Electron RPC bridge for live connection", status=_status)


@app.post("/device/disconnect", response_model=RpcResponse)
def disconnect_device() -> RpcResponse:
    return RpcResponse(ok=True, message="Disconnect requested", status=_status)


@app.post("/capture/start", response_model=RpcResponse)
def start_capture(payload: StartCaptureRequest) -> RpcResponse:
    _ = payload
    return RpcResponse(ok=False, message="Use Electron RPC bridge for live capture", status=_status)


@app.post("/capture/stop", response_model=RpcResponse)
def stop_capture() -> RpcResponse:
    return RpcResponse(ok=True, message="Stop requested", status=_status)


@app.get("/hardware/status", response_model=RpcResponse)
def hardware_status() -> RpcResponse:
    return RpcResponse(ok=True, status=_status)


@app.get("/hardware/report", response_model=RpcResponse)
def verification_report() -> RpcResponse:
    return RpcResponse(ok=True, status=_status)


@app.get("/logs", response_model=RpcResponse)
def get_logs() -> RpcResponse:
    return RpcResponse(ok=True, message="Logs are emitted via Electron event stream", status=_status)
