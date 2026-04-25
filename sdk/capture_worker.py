from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass

import numpy as np

from sdk.circular_buffer import CircularBuffer
from sdk.hthard_wrapper import HTHardWrapper

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CaptureConfig:
    chunk_size: int = 2048
    queue_max_batches: int = 32
    buffer_max_batches: int = 256
    poll_sleep_s: float = 0.001


class CaptureWorker:
    """
    Device capture loop:
    DLL -> background thread -> bounded queue -> circular buffer.
    """

    def __init__(self, wrapper: HTHardWrapper, config: CaptureConfig) -> None:
        self._wrapper = wrapper
        self._config = config
        self._queue: queue.Queue[tuple[float, np.ndarray]] = queue.Queue(maxsize=config.queue_max_batches)
        self._buffer = CircularBuffer(max_batches=config.buffer_max_batches)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._dropped_queue_batches = 0

    @property
    def output_queue(self) -> queue.Queue[tuple[float, np.ndarray]]:
        return self._queue

    @property
    def circular_buffer(self) -> CircularBuffer:
        return self._buffer

    @property
    def dropped_queue_batches(self) -> int:
        return self._dropped_queue_batches

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="hthard-capture", daemon=True)
        self._thread.start()
        logger.info("Capture worker started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None
        logger.info("Capture worker stopped")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                samples = self._wrapper.read_samples(self._config.chunk_size)
                if samples.size == 0:
                    time.sleep(self._config.poll_sleep_s)
                    continue
                ts = time.time()
                self._buffer.append(samples=samples, timestamp_unix=ts)
                self._push_queue(ts, samples)
            except Exception:
                logger.exception("Capture read failed")
                time.sleep(max(self._config.poll_sleep_s, 0.01))

    def _push_queue(self, timestamp_unix: float, samples: np.ndarray) -> None:
        item = (timestamp_unix, samples.copy())
        try:
            self._queue.put_nowait(item)
            return
        except queue.Full:
            pass

        try:
            _ = self._queue.get_nowait()
            self._dropped_queue_batches += 1
            logger.warning(
                "Queue full; dropped oldest batch (total dropped=%s)",
                self._dropped_queue_batches,
            )
        except queue.Empty:
            # Race condition window; safe to continue.
            pass

        try:
            self._queue.put_nowait(item)
        except queue.Full:
            self._dropped_queue_batches += 1
            logger.warning(
                "Queue still full after drop; dropped current batch (total dropped=%s)",
                self._dropped_queue_batches,
            )
