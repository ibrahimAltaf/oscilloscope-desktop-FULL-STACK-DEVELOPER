"""Hantek HT6000 series SDK integration (ctypes)."""

from oscilloscope_backend.hantek.ht6000_errors import HT6000Status, describe_status
from oscilloscope_backend.hantek.sdk import (
    CallingConvention,
    HantekSDK,
    HantekInvalidHandleError,
    HantekNotConnectedError,
    HantekReadFailedError,
    HantekSDKError,
)

__all__ = [
    "CallingConvention",
    "HT6000Status",
    "HantekSDK",
    "HantekSDKError",
    "HantekInvalidHandleError",
    "HantekNotConnectedError",
    "HantekReadFailedError",
    "describe_status",
]
