"""
HT6000 status codes — keep in sync with vendor HT6000*.h if provided.

Unknown codes still surface as HantekSDKError with the numeric value.
"""

from __future__ import annotations

from enum import IntEnum


class HT6000Status(IntEnum):
    """Typical vendor-style success / error codes (adjust to match your SDK)."""

    SUCCESS = 0
    ERROR_NOT_FOUND = -1001
    ERROR_NOT_CONNECTED = -1002
    ERROR_INVALID_HANDLE = -1003
    ERROR_INVALID_PARAM = -1004
    ERROR_TIMEOUT = -1005
    ERROR_IO = -1006
    ERROR_BUSY = -1007
    ERROR_READ_FAILED = -1008


def describe_status(code: int) -> str:
    try:
        return HT6000Status(code).name
    except ValueError:
        return f"UNKNOWN({code})"
