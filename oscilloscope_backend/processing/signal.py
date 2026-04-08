from __future__ import annotations

import math
from typing import Tuple

import numpy as np


def generate_sine_chunk(
    t0: float,
    sample_rate_hz: float,
    n_samples: int,
    *,
    frequency_hz: float,
    amplitude: float = 1.0,
    phase_rad: float = 0.0,
) -> np.ndarray:
    """Vectorized sine for simulation mode."""
    if n_samples <= 0:
        return np.zeros(0, dtype=np.float32)
    dt = 1.0 / sample_rate_hz
    t = t0 + np.arange(n_samples, dtype=np.float64) * dt
    w = 2.0 * math.pi * frequency_hz
    y = amplitude * np.sin(w * t + phase_rad)
    return y.astype(np.float32)


def rms(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(x.astype(np.float64)))))


def downsample_mean(x: np.ndarray, factor: int) -> Tuple[np.ndarray, int]:
    """Block-average decimation by integer factor (>=1)."""
    if factor <= 1 or x.size == 0:
        return x, 1
    n = (x.size // factor) * factor
    trimmed = x[:n].reshape(-1, factor).mean(axis=1)
    return trimmed.astype(np.float32), factor
