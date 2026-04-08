from __future__ import annotations

"""
HTHardDll.dll / HT6000.dll hardware bridge (ctypes).

Function names are resolved dynamically to tolerate vendor name differences.
We try standard exports (HT6000_*) and fall back to fuzzy matches that contain
the expected verb (open/start/read/stop/close).

Windows: default to __stdcall (WinDLL), fallback to CDLL (__cdecl) if needed.
"""

import logging
import os
import sys
from ctypes import CDLL, POINTER, WinDLL, byref, c_int, c_int16, c_void_p
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional

import numpy as np

from oscilloscope_backend.hantek.ht6000_errors import HT6000Status, describe_status

logger = logging.getLogger(__name__)


class HantekSDKError(RuntimeError):
    """Base class for SDK / DLL failures."""


class HantekNotConnectedError(HantekSDKError):
    """No device found or driver not reachable (typical after failed open)."""


class HantekInvalidHandleError(HantekSDKError):
    """Session handle is NULL or not valid for this API call."""


class HantekReadFailedError(HantekSDKError):
    """Vendor read path failed (timeout, USB stall, etc.)."""


class CallingConvention(IntEnum):
    STDCALL = 1
    CDECL = 0


# Export names — must match ht6000_api.h / vendor .def (Dependency Walker).
DEFAULT_EXPORTS = {
    "open_device": "HT6000_Open",
    "close_device": "HT6000_Close",
    "start_capture": "HT6000_StartCapture",
    "stop_capture": "HT6000_StopCapture",
    "read_data": "HT6000_ReadData",
}

# Extra name hints commonly seen in vendor DLLs
EXPORT_HINTS = {
    "open_device": ["HTHard_Open", "HT_Open", "Open_Device", "HT6000_Open"],
    "close_device": ["HTHard_Close", "HT_Close", "Close_Device", "HT6000_Close"],
    "start_capture": ["HTHard_StartCapture", "HT_StartCapture", "Start_Capture", "HT6000_StartCapture"],
    "stop_capture": ["HTHard_StopCapture", "HT_StopCapture", "Stop_Capture", "HT6000_StopCapture"],
    "read_data": ["HTHard_ReadData", "HT_ReadData", "Read_Data", "HT6000_ReadData"],
}

class HantekSDK:
    """
    ctypes wrapper for HT6000.dll.

    Primary output is ``read_data()`` → ``numpy.ndarray`` (float32, volts).
    Use ``read_data_as_list()`` when a Python list is required.
    Raw ADC codes: ``read_raw_int16()``.
    """

    def __init__(
        self,
        dll_path: Optional[str | Path] = None,
        *,
        calling_convention: CallingConvention = CallingConvention.STDCALL,
        export_names: Optional[dict[str, str]] = None,
        device_index: int = 0,
        adc_volts_full_scale: float = 8.0,
    ) -> None:
        # Resolve path from env, explicit arg, or bundled fallback
        env_path = os.getenv("OSCILLOSCOPE_HANTEK_DLL_PATH")
        if dll_path:
            resolved = Path(dll_path)
        elif env_path:
            resolved = Path(env_path)
        else:
            resolved = Path(__file__).resolve().parent / "HTHardDll.dll"

        self._dll_path = resolved if resolved else None
        self._calling_convention = calling_convention
        self._export_names = {**DEFAULT_EXPORTS, **(export_names or {})}
        self._device_index = int(device_index)
        self._volts_per_lsb = float(adc_volts_full_scale) / 32768.0

        self._dll: Any = None
        self._fn_open: Optional[Callable[..., int]] = None
        self._fn_close: Optional[Callable[..., int]] = None
        self._fn_start: Optional[Callable[..., int]] = None
        self._fn_stop: Optional[Callable[..., int]] = None
        self._fn_read: Optional[Callable[..., int]] = None
        self._device_handle = c_void_p(None)
        self._read_buffer_len = 1024  # default; adjustable

    @property
    def dll_path(self) -> Optional[Path]:
        return self._dll_path

    @property
    def is_loaded(self) -> bool:
        return self._dll is not None

    def _resolved_dll_path(self) -> Path:
        if not self._dll_path:
            raise HantekSDKError(
                "No DLL path configured (set OSCILLOSCOPE_HANTEK_DLL_PATH or pass dll_path=)"
            )
        p = self._dll_path
        if not p.is_absolute():
            p = Path.cwd() / p
        return p

    def load(self) -> None:
        if self._dll is not None:
            return
        path = self._resolved_dll_path()
        if not path.is_file():
            raise HantekNotConnectedError(f"HT DLL not found: {path}")

        try:
            if self._calling_convention == CallingConvention.STDCALL:
                try:
                    self._dll = WinDLL(str(path))
                except OSError:
                    # Fallback to CDLL if vendor uses cdecl despite stdcall flag
                    self._dll = CDLL(str(path))
            else:
                self._dll = CDLL(str(path))
        except OSError as e:
            raise HantekNotConnectedError(f"Failed to load {path}: {e}") from e

        self._bind_functions()
        logger.info("Loaded HT SDK: %s", path)

    def _bind_functions(self) -> None:
        assert self._dll is not None
        export_names = self._export_names
        all_symbols = {name.lower(): name for name in dir(self._dll)}

        def resolve(key: str, hints: Iterable[str]) -> Callable[..., int]:
            # exact preferred name
            preferred = export_names.get(key)
            if preferred and hasattr(self._dll, preferred):
                return getattr(self._dll, preferred)
            # hinted names
            for h in hints:
                if hasattr(self._dll, h):
                    return getattr(self._dll, h)
            # fuzzy contains
            target = key.split("_")[0] if "_" in key else key
            for sym in all_symbols.values():
                if target in sym.lower():
                    return getattr(self._dll, sym)
            raise AttributeError(f"Unable to resolve export for {key}")

        self._fn_open = resolve("open_device", EXPORT_HINTS["open_device"])
        self._fn_open.argtypes = [c_int, POINTER(c_void_p)]
        self._fn_open.restype = c_int

        self._fn_close = resolve("close_device", EXPORT_HINTS["close_device"])
        self._fn_close.argtypes = [c_void_p]
        self._fn_close.restype = c_int

        self._fn_start = resolve("start_capture", EXPORT_HINTS["start_capture"])
        self._fn_start.argtypes = [c_void_p]
        self._fn_start.restype = c_int

        try:
            self._fn_stop = resolve("stop_capture", EXPORT_HINTS["stop_capture"])
            self._fn_stop.argtypes = [c_void_p]
            self._fn_stop.restype = c_int
        except AttributeError:
            logger.warning("StopCapture export not found; stop will be skipped")
            self._fn_stop = None

        self._fn_read = resolve("read_data", EXPORT_HINTS["read_data"])
        self._fn_read.argtypes = [c_void_p, POINTER(c_int16), c_int, POINTER(c_int)]
        self._fn_read.restype = c_int

    def _raise_for_status(self, rc: int, *, context: str) -> None:
        if rc == HT6000Status.SUCCESS:
            return
        desc = describe_status(rc)
        msg = f"{context} failed: {desc} (code={rc})"
        if rc in (
            HT6000Status.ERROR_NOT_FOUND,
            HT6000Status.ERROR_NOT_CONNECTED,
        ):
            raise HantekNotConnectedError(msg)
        if rc == HT6000Status.ERROR_INVALID_HANDLE:
            raise HantekInvalidHandleError(msg)
        if rc in (HT6000Status.ERROR_READ_FAILED, HT6000Status.ERROR_IO, HT6000Status.ERROR_TIMEOUT):
            raise HantekReadFailedError(msg)
        raise HantekSDKError(msg)

    def _require_valid_handle(self) -> None:
        v = self._device_handle.value
        if v is None or v == 0:
            raise HantekInvalidHandleError("Invalid HT6000 handle: device not open")

    def open_device(self) -> None:
        """
        Open the scope (``HT6000_Open``). Stores the session handle for subsequent calls.
        """
        self.load()
        assert self._fn_open is not None
        out = c_void_p(None)
        rc = int(self._fn_open(c_int(self._device_index), byref(out)))
        try:
            self._raise_for_status(rc, context="HT6000_Open")
        except HantekSDKError:
            self._device_handle = c_void_p(None)
            raise
        if out.value is None or out.value == 0:
            raise HantekInvalidHandleError("HT6000_Open returned success but handle is NULL")
        self._device_handle = out
        logger.info("HT device opened (index=%s)", self._device_index)

    def close_device(self) -> None:
        if self._fn_close is None or self._dll is None:
            self._device_handle = c_void_p(None)
            return
        h = self._device_handle
        if h.value is None or h.value == 0:
            self._device_handle = c_void_p(None)
            return
        rc = int(self._fn_close(h))
        self._device_handle = c_void_p(None)
        if rc != HT6000Status.SUCCESS:
            logger.warning("HT6000_Close returned %s (%s)", rc, describe_status(rc))

    def start_capture(self) -> None:
        """Begin acquisition (``HT6000_StartCapture``)."""
        if self._fn_start is None:
            raise HantekSDKError("SDK not loaded")
        self._require_valid_handle()
        rc = int(self._fn_start(self._device_handle))
        self._raise_for_status(rc, context="HT6000_StartCapture")

    def stop_capture(self) -> None:
        if self._fn_stop is None or self._dll is None:
            return
        if self._device_handle.value in (None, 0):
            return
        rc = int(self._fn_stop(self._device_handle))
        if rc != HT6000Status.SUCCESS:
            logger.warning("HT6000_StopCapture returned %s (%s)", rc, describe_status(rc))

    def set_read_chunk_samples(self, n: int) -> None:
        self._read_buffer_len = max(64, int(n))

    def read_raw_int16(self) -> np.ndarray:
        """
        Read one chunk into a NumPy int16 array (ADC codes). Caller-owned buffer
        is filled via pointer passed to ``HT6000_ReadData``.
        """
        if self._fn_read is None:
            raise HantekSDKError("SDK not loaded")
        self._require_valid_handle()
        n = self._read_buffer_len
        raw = np.empty(n, dtype=np.int16)
        out_count = c_int(0)
        rc = int(
            self._fn_read(
                self._device_handle,
                raw.ctypes.data_as(POINTER(c_int16)),
                c_int(n),
                byref(out_count),
            )
        )
        count = int(out_count.value)
        if rc != HT6000Status.SUCCESS:
            self._raise_for_status(rc, context="HT6000_ReadData")
        if count <= 0:
            return np.zeros(0, dtype=np.int16)
        if count > n:
            count = n
        return raw[:count].copy()

    def read_data(self) -> np.ndarray:
        """
        Real samples as float32 volts (linear scale from int16 using configured full-scale).

        Returns a new NumPy array each call (safe to retain across DLL reads).
        """
        codes = self.read_raw_int16()
        if codes.size == 0:
            return np.zeros(0, dtype=np.float32)
        volts = (codes.astype(np.float32) * np.float32(self._volts_per_lsb)).astype(np.float32)
        logger.debug("read_data: %s samples ptp=%.4f rms=%.4f", volts.size, float(np.ptp(volts)), float(np.sqrt(np.mean(np.square(volts)))))
        return volts

    def read_data_as_list(self) -> List[float]:
        """Same as ``read_data`` but returns a Python ``list`` (higher overhead)."""
        return self.read_data().tolist()

    def unload(self) -> None:
        try:
            if self._dll is not None:
                try:
                    self.stop_capture()
                except Exception as e:
                    logger.debug("stop_capture during unload: %s", e)
                self.close_device()
        finally:
            self._dll = None
            self._fn_open = None
            self._fn_close = None
            self._fn_start = None
            self._fn_stop = None
            self._fn_read = None
            logger.info("HT SDK unloaded")


def is_windows() -> bool:
    return sys.platform.startswith("win")
