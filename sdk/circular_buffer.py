from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SampleBatch:
    timestamp_unix: float
    samples: np.ndarray


class CircularBuffer:
    """Thread-safe circular storage for recent sample batches."""

    def __init__(self, max_batches: int) -> None:
        self._max_batches = max(1, int(max_batches))
        self._buffer: deque[SampleBatch] = deque(maxlen=self._max_batches)
        self._lock = threading.Lock()
        self.drop_count = 0

    def append(self, samples: np.ndarray, timestamp_unix: float | None = None) -> None:
        batch = SampleBatch(
            timestamp_unix=time.time() if timestamp_unix is None else float(timestamp_unix),
            samples=samples.copy(),
        )
        with self._lock:
            was_full = len(self._buffer) == self._buffer.maxlen
            self._buffer.append(batch)
            if was_full:
                self.drop_count += 1

    def latest(self) -> SampleBatch | None:
        with self._lock:
            if not self._buffer:
                return None
            return self._buffer[-1]

    def snapshot(self) -> list[SampleBatch]:
        with self._lock:
            return list(self._buffer)
