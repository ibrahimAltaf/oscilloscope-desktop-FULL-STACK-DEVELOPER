from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Deque, Iterator, List

import numpy as np


@dataclass(frozen=True)
class SampleFrame:
    """One contiguous chunk of samples with timing metadata."""

    t0: float  # epoch seconds, start of first sample
    sample_rate_hz: float
    samples: np.ndarray  # shape (n,), float32

    def duration_s(self) -> float:
        if self.sample_rate_hz <= 0:
            return 0.0
        return float(len(self.samples)) / self.sample_rate_hz


class CircularSampleBuffer:
    """
    Retains the most recent `max_seconds` of data using a deque of frames.

    Efficient for replay: iterate frames in time order. Memory is bounded by
    approximate sample count (sum of frame lengths).
    """

    def __init__(self, max_seconds: float, nominal_sample_rate_hz: float) -> None:
        self._max_seconds = float(max_seconds)
        self._nominal_rate = float(nominal_sample_rate_hz)
        self._max_samples = max(1, int(self._max_seconds * self._nominal_rate))
        self._frames: Deque[SampleFrame] = deque()
        self._total_samples = 0
        self._lock = threading.Lock()

    @property
    def max_seconds(self) -> float:
        return self._max_seconds

    def clear(self) -> None:
        with self._lock:
            self._frames.clear()
            self._total_samples = 0

    def append(self, frame: SampleFrame) -> None:
        with self._lock:
            self._frames.append(frame)
            self._total_samples += len(frame.samples)
            self._trim_unlocked()

    def _trim_unlocked(self) -> None:
        while self._total_samples > self._max_samples and self._frames:
            old = self._frames.popleft()
            self._total_samples -= len(old.samples)

    def snapshot_frames(self) -> List[SampleFrame]:
        with self._lock:
            return list(self._frames)

    def iter_samples(self) -> Iterator[np.ndarray]:
        for f in self.snapshot_frames():
            yield f.samples

    def approx_duration_s(self) -> float:
        with self._lock:
            if not self._frames:
                return 0.0
            return sum(f.duration_s() for f in self._frames)
