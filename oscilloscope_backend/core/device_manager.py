from __future__ import annotations

import logging
import random
import threading
import time
from enum import Enum
from typing import Callable, ClassVar, Optional

from oscilloscope_backend.hantek.sdk import HantekSDK, HantekSDKError

logger = logging.getLogger(__name__)


class DeviceState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CAPTURING = "capturing"
    SIMULATING = "simulating"
    ERROR = "error"


class DeviceManager:
    """
    Singleton: device lifecycle and reconnect policy.

    If ``HantekSDK.dll_path`` is set (real hardware / HT6000.dll), simulation is
    never used: failures surface as ERROR and reconnect attempts stay on hardware.

    Simulation applies only when no DLL path is configured and simulation is enabled.
    """

    _instance: ClassVar[Optional[DeviceManager]] = None
    _singleton_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(
        self,
        sdk: HantekSDK,
        *,
        simulation_enabled: bool = True,
        reconnect_interval_s: float = 2.0,
        reconnect_jitter_s: float = 0.5,
        reconnect_max_attempts: int = 0,
        on_state_change: Optional[Callable[[DeviceState], None]] = None,
    ) -> None:
        self._sdk = sdk
        self._simulation_enabled = simulation_enabled
        self._reconnect_interval_s = reconnect_interval_s
        self._reconnect_jitter_s = reconnect_jitter_s
        self._reconnect_max_attempts = reconnect_max_attempts
        self._on_state_change = on_state_change
        self._lock = threading.RLock()
        self._state = DeviceState.DISCONNECTED
        self._reconnect_failures = 0
        self._last_error: Optional[str] = None

    @classmethod
    def configure(
        cls,
        sdk: HantekSDK,
        *,
        simulation_enabled: bool = True,
        reconnect_interval_s: float = 2.0,
        reconnect_jitter_s: float = 0.5,
        reconnect_max_attempts: int = 0,
        on_state_change: Optional[Callable[[DeviceState], None]] = None,
    ) -> DeviceManager:
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls(
                    sdk,
                    simulation_enabled=simulation_enabled,
                    reconnect_interval_s=reconnect_interval_s,
                    reconnect_jitter_s=reconnect_jitter_s,
                    reconnect_max_attempts=reconnect_max_attempts,
                    on_state_change=on_state_change,
                )
            return cls._instance

    @classmethod
    def instance(cls) -> DeviceManager:
        if cls._instance is None:
            raise RuntimeError("DeviceManager.configure() must run before instance()")
        return cls._instance

    @classmethod
    def reset_for_testing(cls) -> None:
        with cls._singleton_lock:
            cls._instance = None

    def note_read_success(self) -> None:
        with self._lock:
            self._reconnect_failures = 0

    @property
    def state(self) -> DeviceState:
        with self._lock:
            return self._state

    @property
    def last_error(self) -> Optional[str]:
        with self._lock:
            return self._last_error

    @property
    def is_hardware_active(self) -> bool:
        with self._lock:
            return self._state in (DeviceState.CONNECTED, DeviceState.CAPTURING)

    @property
    def is_simulating(self) -> bool:
        with self._lock:
            return self._state == DeviceState.SIMULATING

    @property
    def is_hardware_mode(self) -> bool:
        """True when a DLL path is configured (HT6000.dll / real device path)."""
        return self._sdk.dll_path is not None

    @property
    def reconnect_failures(self) -> int:
        with self._lock:
            return self._reconnect_failures

    def _set_state(self, new: DeviceState, err: Optional[str] = None) -> None:
        with self._lock:
            self._state = new
            self._last_error = err
        logger.info("Device state -> %s", new.value)
        if self._on_state_change:
            self._on_state_change(new)

    def mark_capturing(self) -> None:
        """Public entry for capture loop to flip CONNECTED -> CAPTURING without exposing internals."""
        with self._lock:
            if self._state == DeviceState.CONNECTED:
                self._state = DeviceState.CAPTURING
        logger.debug("Device state -> %s", self._state.value)

    def connect(self) -> None:
        """Open device: simulation only without DLL path; hardware-only when DLL is set."""
        if self._sdk.dll_path is None:
            if self._simulation_enabled:
                self._set_state(DeviceState.SIMULATING)
            else:
                msg = "OSCILLOSCOPE_HANTEK_DLL_PATH is not set"
                self._set_state(DeviceState.ERROR, msg)
                raise HantekSDKError(msg)
            return

        self._set_state(DeviceState.CONNECTING)
        try:
            self._sdk.load()
            self._sdk.open_device()
            self._sdk.start_capture()
            self._reconnect_failures = 0
            self._set_state(DeviceState.CONNECTED)
        except HantekSDKError as e:
            logger.error("Hardware connection failed: %s", e)
            self._set_state(DeviceState.ERROR, str(e))
            raise

    def disconnect(self) -> None:
        prev = self.state
        if prev in (DeviceState.CONNECTED, DeviceState.CAPTURING):
            try:
                self._sdk.stop_capture()
            except Exception as e:
                logger.debug("stop_capture: %s", e)
            try:
                self._sdk.close_device()
            except Exception as e:
                logger.debug("close_device: %s", e)
        self._set_state(DeviceState.DISCONNECTED)

    def on_capture_read_failure(self, exc: BaseException) -> None:
        msg = str(exc)
        logger.warning("Capture read failed: %s", exc)
        with self._lock:
            self._reconnect_failures += 1
            st = self._state

        if st in (DeviceState.CONNECTED, DeviceState.CAPTURING):
            try:
                self._sdk.stop_capture()
            except Exception as e:
                logger.debug("stop_capture on failure: %s", e)
            self._set_state(DeviceState.ERROR, msg)

        if self._sdk.dll_path is None:
            if self._simulation_enabled:
                self._set_state(DeviceState.SIMULATING, msg)
            return

        # Hardware mode: never fall back to simulation after using HT6000.dll.
        if (
            self._reconnect_max_attempts > 0
            and self._reconnect_failures >= self._reconnect_max_attempts
        ):
            self._set_state(DeviceState.ERROR, msg)
            return

        delay = self._reconnect_interval_s
        if self._reconnect_jitter_s > 0:
            delay += random.uniform(0, self._reconnect_jitter_s)
        time.sleep(delay)
        try:
            self._sdk.unload()
            self.connect()
        except HantekSDKError as e:
            logger.warning("Reconnect failed: %s", e)
            self._set_state(DeviceState.ERROR, str(e))

    def teardown(self) -> None:
        try:
            self.disconnect()
        finally:
            try:
                self._sdk.unload()
            except Exception as e:
                logger.debug("sdk.unload: %s", e)
