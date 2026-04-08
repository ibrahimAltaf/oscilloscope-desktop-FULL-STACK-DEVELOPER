"""Device manager, capture threading, and WebSocket fan-out."""

from oscilloscope_backend.core.device_manager import DeviceManager, DeviceState
from oscilloscope_backend.utils.config import Settings, get_settings

__all__ = ["DeviceManager", "DeviceState", "Settings", "get_settings"]
