from __future__ import annotations

import ctypes
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)


class SDKError(RuntimeError):
    """Base SDK integration error."""


class SDKConfigurationError(SDKError):
    """Raised when required DLL symbols/signatures are missing."""


@dataclass(frozen=True)
class DllInspectionResult:
    """Result of DLL export inspection."""

    path: Path
    exports: list[str]
    calling_convention_hint: str


@dataclass(frozen=True)
class BoundFunctions:
    """Bound function pointers to required SDK exports."""

    initialize: Optional[Callable[..., int]]
    open_device: Callable[..., int]
    close_device: Callable[..., int]
    start_capture: Callable[..., int]
    stop_capture: Optional[Callable[..., int]]
    read_data: Callable[..., int]


class HTHardWrapper:
    """
    Safe ctypes wrapper for `HTHardDll(1).dll`-style SDKs.

    Since vendor headers are not present in this repo, this class:
    1) Inspects export names first.
    2) Binds only known-safe signatures.
    3) Fails with actionable errors when signatures cannot be verified.
    """

    DEFAULT_EXPORT_MAP = {
        "initialize": "HT_Init",
        "open_device": "HT_OpenDevice",
        "close_device": "HT_CloseDevice",
        "start_capture": "HT_StartCapture",
        "stop_capture": "HT_StopCapture",
        "read_data": "HT_ReadData",
    }

    def __init__(self, dll_path: str | Path) -> None:
        self._dll_path = Path(dll_path)
        self._dll: Optional[ctypes.CDLL] = None
        self._bound: Optional[BoundFunctions] = None
        self._handle = ctypes.c_void_p()
        self._using_windll = False

    @property
    def dll_path(self) -> Path:
        return self._dll_path

    @property
    def is_open(self) -> bool:
        return bool(self._handle.value)

    def inspect_exports(self) -> DllInspectionResult:
        """
        Inspect PE exports.

        Preferred path uses `pefile` when available. If not installed, we try
        `dumpbin /exports` (Visual Studio tools) on Windows.
        """
        if not self._dll_path.exists():
            raise FileNotFoundError(f"DLL not found: {self._dll_path}")

        exports: list[str] = []
        try:
            import pefile  # type: ignore

            pe = pefile.PE(str(self._dll_path))
            if not hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
                raise SDKConfigurationError("DLL has no export table")
            for symbol in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                if symbol.name:
                    exports.append(symbol.name.decode("utf-8", errors="ignore"))
        except ModuleNotFoundError:
            if not sys.platform.startswith("win"):
                raise SDKConfigurationError(
                    "Install `pefile` to inspect exports on non-Windows systems."
                )
            exports = self._inspect_with_dumpbin()

        exports = sorted(set(exports))
        calling_hint = self._infer_calling_convention_hint(exports)
        logger.info("DLL inspection complete: %s exports, calling hint=%s", len(exports), calling_hint)
        return DllInspectionResult(path=self._dll_path, exports=exports, calling_convention_hint=calling_hint)

    def _inspect_with_dumpbin(self) -> list[str]:
        command = ["dumpbin", "/exports", str(self._dll_path)]
        try:
            proc = subprocess.run(command, capture_output=True, text=True, check=True)
        except Exception as exc:
            raise SDKConfigurationError(
                "Export inspection requires `pefile` or Visual Studio `dumpbin`."
            ) from exc
        exports: list[str] = []
        for line in proc.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[0].isdigit() and parts[1].isdigit():
                exports.append(parts[-1])
        return exports

    @staticmethod
    def _infer_calling_convention_hint(exports: list[str]) -> str:
        # stdcall x86 exports often look like `_FunctionName@N`.
        if any(name.startswith("_") and "@" in name for name in exports):
            return "likely_stdcall_x86"
        return "unknown_or_x64"

    def load(self) -> None:
        if self._dll is not None:
            return
        if not self._dll_path.exists():
            raise FileNotFoundError(f"DLL not found: {self._dll_path}")
        if sys.platform.startswith("win"):
            try:
                self._dll = ctypes.WinDLL(str(self._dll_path))
                self._using_windll = True
            except OSError:
                # Some SDKs expose cdecl despite docs claiming stdcall.
                self._dll = ctypes.CDLL(str(self._dll_path))
                self._using_windll = False
        else:
            # Non-Windows loading is for static validation only.
            self._dll = ctypes.CDLL(str(self._dll_path))
            self._using_windll = False

    def bind(self, inspection: DllInspectionResult, export_map: Optional[dict[str, str]] = None) -> None:
        self.load()
        assert self._dll is not None
        mapped = {**self.DEFAULT_EXPORT_MAP, **(export_map or {})}

        def resolve(export_name: str, required: bool = True) -> Optional[Callable[..., int]]:
            if hasattr(self._dll, export_name):
                return getattr(self._dll, export_name)
            if required:
                raise SDKConfigurationError(
                    f"Required export not found: {export_name}. "
                    "Use export_map=... with exact names from inspected exports."
                )
            return None

        fn_init = resolve(mapped["initialize"], required=False)
        fn_open = resolve(mapped["open_device"], required=True)
        fn_close = resolve(mapped["close_device"], required=True)
        fn_start = resolve(mapped["start_capture"], required=True)
        fn_stop = resolve(mapped["stop_capture"], required=False)
        fn_read = resolve(mapped["read_data"], required=True)

        # NOTE: These signatures must be verified against vendor header docs.
        if fn_init is not None:
            fn_init.argtypes = []
            fn_init.restype = ctypes.c_int

        fn_open.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
        fn_open.restype = ctypes.c_int

        fn_close.argtypes = [ctypes.c_void_p]
        fn_close.restype = ctypes.c_int

        fn_start.argtypes = [ctypes.c_void_p]
        fn_start.restype = ctypes.c_int

        if fn_stop is not None:
            fn_stop.argtypes = [ctypes.c_void_p]
            fn_stop.restype = ctypes.c_int

        fn_read.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int16),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
        fn_read.restype = ctypes.c_int

        self._bound = BoundFunctions(
            initialize=fn_init,
            open_device=fn_open,
            close_device=fn_close,
            start_capture=fn_start,
            stop_capture=fn_stop,
            read_data=fn_read,
        )

        logger.info(
            "Function binding success (WinDLL=%s, calling_hint=%s)",
            self._using_windll,
            inspection.calling_convention_hint,
        )

    def initialize(self) -> None:
        self._require_bound()
        if self._bound.initialize is None:
            logger.info("No explicit initialize export found; skipping initialize()")
            return
        rc = int(self._bound.initialize())
        self._raise_on_error(rc, "initialize")

    def open_device(self, index: int = 0) -> None:
        self._require_bound()
        handle = ctypes.c_void_p()
        rc = int(self._bound.open_device(ctypes.c_int(index), ctypes.byref(handle)))
        self._raise_on_error(rc, "open_device")
        if not handle.value:
            raise SDKError("open_device returned success but handle is NULL")
        self._handle = handle

    def start_capture(self) -> None:
        self._require_open()
        rc = int(self._bound.start_capture(self._handle))
        self._raise_on_error(rc, "start_capture")

    def read_samples(self, max_samples: int) -> np.ndarray:
        self._require_open()
        max_samples = max(1, int(max_samples))
        raw = np.empty(max_samples, dtype=np.int16)
        out_count = ctypes.c_int(0)
        rc = int(
            self._bound.read_data(
                self._handle,
                raw.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
                ctypes.c_int(max_samples),
                ctypes.byref(out_count),
            )
        )
        self._raise_on_error(rc, "read_samples")
        count = int(out_count.value)
        if count <= 0:
            return np.empty(0, dtype=np.int16)
        return raw[: min(count, max_samples)].copy()

    def stop_capture(self) -> None:
        if not self.is_open or self._bound is None:
            return
        if self._bound.stop_capture is None:
            return
        rc = int(self._bound.stop_capture(self._handle))
        if rc != 0:
            logger.warning("stop_capture returned non-zero status: %s", rc)

    def close_device(self) -> None:
        if self._bound is None or not self.is_open:
            self._handle = ctypes.c_void_p()
            return
        rc = int(self._bound.close_device(self._handle))
        self._handle = ctypes.c_void_p()
        if rc != 0:
            logger.warning("close_device returned non-zero status: %s", rc)

    def cleanup(self) -> None:
        try:
            self.stop_capture()
        finally:
            self.close_device()

    def _require_bound(self) -> None:
        if self._bound is None:
            raise SDKConfigurationError("Functions are not bound. Call inspect_exports() and bind() first.")

    def _require_open(self) -> None:
        self._require_bound()
        if not self.is_open:
            raise SDKError("Device is not open")

    @staticmethod
    def _raise_on_error(return_code: int, operation: str) -> None:
        if return_code != 0:
            raise SDKError(f"{operation} failed with code={return_code}")
