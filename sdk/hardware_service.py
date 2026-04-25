from __future__ import annotations

import json
import logging
import struct
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from sdk.capture_worker import CaptureConfig, CaptureWorker
from sdk.hthard_wrapper import HTHardWrapper


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
logger = logging.getLogger("hardware-service")


@dataclass
class ServiceState:
    dll_path: str = ""
    dll_found: bool = False
    dll_arch: str = "unknown"
    python_arch: str = "unknown"
    electron_arch: str = "unknown"
    dll_loaded: bool = False
    exports: list[str] | None = None
    device_connected: bool = False
    device_detected: bool = False
    capture_running: bool = False
    capture_started: bool = False
    real_data_received: bool = False
    zero_data_warning: bool = False
    samples_received: int = 0
    last_min: int | None = None
    last_max: int | None = None
    last_variance: float | None = None
    last_error: str | None = None
    sdk_error_code: int | None = None
    export_count: int = 0
    mapped_functions: dict[str, str] | None = None
    final_status: str = "REAL HARDWARE NOT VERIFIED"
    verification_reason: str = "DLL/device not validated yet"


class HardwareService:
    def __init__(self) -> None:
        self._state = ServiceState()
        self._state.python_arch = "x64" if struct.calcsize("P") == 8 else "x86"
        self._wrapper: HTHardWrapper | None = None
        self._worker: CaptureWorker | None = None
        self._stop = threading.Event()
        self._stream_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        msg = {"event": event, "payload": payload}
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()

    def reply(self, request_id: str, ok: bool, result: dict[str, Any] | None = None, error: str | None = None) -> None:
        self.emit(
            "rpc_response",
            {"request_id": request_id, "ok": ok, "result": result or {}, "error": error},
        )

    def _set_error(self, msg: str, code: int | None = None) -> None:
        self._state.last_error = msg
        self._state.sdk_error_code = code
        self._refresh_final_status()
        self.emit("status", asdict(self._state))

    def _refresh_final_status(self) -> None:
        if self._state.real_data_received and self._state.device_connected and self._state.capture_started:
            self._state.final_status = "REAL HARDWARE VERIFIED"
            self._state.verification_reason = "Device connected, capture started, and real sample batches received"
            return
        self._state.final_status = "REAL HARDWARE NOT VERIFIED"
        if self._state.last_error:
            self._state.verification_reason = self._state.last_error
        elif not self._state.dll_found:
            self._state.verification_reason = "DLL path missing or file not found"
        elif not self._state.device_connected:
            self._state.verification_reason = "Device not connected"
        elif self._state.capture_started and not self._state.real_data_received:
            self._state.verification_reason = "Capture started but no real signal data received"
        else:
            self._state.verification_reason = "Hardware validation is incomplete"

    @staticmethod
    def _detect_dll_arch(path: Path) -> str:
        with path.open("rb") as f:
            data = f.read(4096)
        if len(data) < 0x40:
            return "unknown"
        pe_offset = int.from_bytes(data[0x3C:0x40], "little")
        with path.open("rb") as f:
            f.seek(pe_offset + 4)
            machine = int.from_bytes(f.read(2), "little")
        if machine == 0x14C:
            return "x86"
        if machine == 0x8664:
            return "x64"
        return f"unknown(0x{machine:04X})"

    def handle(self, request_id: str, method: str, params: dict[str, Any]) -> None:
        try:
            if method == "select_dll":
                dll_path = str(params.get("dll_path", "")).strip()
                if not dll_path:
                    raise ValueError("DLL path missing")
                self._state.dll_path = dll_path
                p = Path(dll_path)
                self._state.dll_found = p.exists()
                self._state.dll_arch = self._detect_dll_arch(p) if p.exists() else "unknown"
                self._state.dll_loaded = False
                self._state.exports = None
                self._state.last_error = None
                self._refresh_final_status()
                self.reply(request_id, True, {"dll_path": dll_path})
                self.emit("status", asdict(self._state))
                return

            if method == "inspect_dll":
                self._ensure_wrapper()
                inspection = self._wrapper.inspect_exports()
                self._state.dll_loaded = True
                self._state.dll_found = True
                self._state.export_count = len(inspection.exports)
                self._state.exports = inspection.exports
                self._state.last_error = None
                self._refresh_final_status()
                self.reply(
                    request_id,
                    True,
                    {
                        "calling_convention_hint": inspection.calling_convention_hint,
                        "exports": inspection.exports,
                    },
                )
                self.emit("status", asdict(self._state))
                return

            if method == "connect_device":
                self._ensure_wrapper()
                export_map = params.get("export_map") or {}
                self._wrapper.bind(self._wrapper.inspect_exports(), export_map=export_map)
                self._wrapper.initialize()
                self._wrapper.open_device(int(params.get("device_index", 0)))
                self._state.device_connected = True
                self._state.device_detected = True
                self._state.mapped_functions = dict(export_map)
                self._state.last_error = None
                self._refresh_final_status()
                self.reply(request_id, True, {"device_connected": True})
                self.emit("status", asdict(self._state))
                return

            if method == "start_capture":
                if self._wrapper is None or not self._state.device_connected:
                    raise RuntimeError("Device not connected")
                self._wrapper.start_capture()
                chunk_size = max(64, int(params.get("chunk_size", 2048)))
                self._worker = CaptureWorker(self._wrapper, CaptureConfig(chunk_size=chunk_size))
                self._worker.start()
                self._state.capture_running = True
                self._state.capture_started = True
                self._state.last_error = None
                self._refresh_final_status()
                self._start_streaming_thread()
                self.reply(request_id, True, {"capture_running": True})
                self.emit("status", asdict(self._state))
                return

            if method == "stop_capture":
                if self._worker is not None:
                    self._worker.stop()
                if self._wrapper is not None:
                    self._wrapper.stop_capture()
                self._state.capture_running = False
                self._refresh_final_status()
                self.reply(request_id, True, {"capture_running": False})
                self.emit("status", asdict(self._state))
                return

            if method == "disconnect_device":
                self.shutdown()
                self.reply(request_id, True, {"device_connected": False})
                self.emit("status", asdict(self._state))
                return

            if method == "get_status":
                self.reply(request_id, True, asdict(self._state))
                return

            raise ValueError(f"Unknown method: {method}")
        except FileNotFoundError as exc:
            self._set_error(f"DLL path missing or not found: {exc}")
            self.reply(request_id, False, error=str(exc))
        except OSError as exc:
            msg = f"DLL cannot load: {exc}"
            self._set_error(msg)
            self.reply(request_id, False, error=msg)
        except Exception as exc:
            self._set_error(str(exc))
            self.reply(request_id, False, error=str(exc))

    def _ensure_wrapper(self) -> None:
        if not self._state.dll_path:
            raise ValueError("DLL path missing")
        if self._wrapper is None or self._wrapper.dll_path != Path(self._state.dll_path):
            self._wrapper = HTHardWrapper(self._state.dll_path)

    def _start_streaming_thread(self) -> None:
        if self._stream_thread and self._stream_thread.is_alive():
            return
        self._stop.clear()
        self._stream_thread = threading.Thread(target=self._stream_loop, name="stream-loop", daemon=True)
        self._stream_thread.start()

    def _stream_loop(self) -> None:
        while not self._stop.is_set():
            worker = self._worker
            if worker is None:
                time.sleep(0.05)
                continue
            try:
                ts, samples = worker.output_queue.get(timeout=0.2)
            except Exception:
                continue
            arr = samples.astype(np.int16)
            self._state.samples_received += int(arr.size)
            if arr.size > 0:
                self._state.real_data_received = True
                self._state.zero_data_warning = False
                self._state.last_min = int(arr.min())
                self._state.last_max = int(arr.max())
                self._state.last_variance = float(np.var(arr.astype(np.float64)))
            payload = {
                "timestamp_unix": float(ts),
                "samples": arr.tolist(),
                "count": int(arr.size),
                "min": int(arr.min()) if arr.size else 0,
                "max": int(arr.max()) if arr.size else 0,
                "variance": float(np.var(arr.astype(np.float64))) if arr.size else 0.0,
            }
            self.emit("sample_batch", payload)
            if arr.size == 0:
                self._state.zero_data_warning = True
                self.emit("log", {"level": "warning", "message": "No real signal data received"})
            self._refresh_final_status()
            self.emit("status", asdict(self._state))

    def shutdown(self) -> None:
        self._stop.set()
        if self._worker is not None:
            self._worker.stop()
        self._worker = None
        if self._wrapper is not None:
            self._wrapper.cleanup()
        self._wrapper = None
        self._state.capture_running = False
        self._state.device_connected = False
        self._refresh_final_status()


def main() -> int:
    svc = HardwareService()
    svc.emit("status", asdict(svc._state))
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            request_id = str(data.get("id", ""))
            method = str(data.get("method", ""))
            params = data.get("params", {}) or {}
            if method == "shutdown":
                svc.reply(request_id, True, {"shutdown": True})
                break
            svc.handle(request_id, method, params)
        except Exception as exc:
            svc.reply("unknown", False, error=f"Invalid request: {exc}")
    svc.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
