from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import numpy as np

from oscilloscope_backend.core.broadcaster import SignalBroadcaster
from oscilloscope_backend.core.device_manager import DeviceManager, DeviceState
from oscilloscope_backend.hantek.sdk import HantekSDK, HantekSDKError
from oscilloscope_backend.processing.buffer import CircularSampleBuffer, SampleFrame
from oscilloscope_backend.processing.signal import generate_sine_chunk
from oscilloscope_backend.utils.config import Settings

logger = logging.getLogger(__name__)


class CaptureService:
    """
    Dedicated capture thread: hardware or simulation → circular buffer → WebSocket fan-out.

    The FastAPI event loop stays non-blocking; all acquisition runs here.
    """

    def __init__(
        self,
        settings: Settings,
        sdk: HantekSDK,
        device_manager: DeviceManager,
        sample_buffer: CircularSampleBuffer,
        broadcaster: SignalBroadcaster,
    ) -> None:
        self._settings = settings
        self._sdk = sdk
        self._device_manager = device_manager
        self._buffer = sample_buffer
        self._broadcaster = broadcaster
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._sim_time_s = 0.0
        self._batch_seq = 0
        self._flat_runs = 0
        self._batches_sent = 0
        self._last_batch_time = 0.0

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self.is_running:
                return
            self._stop.clear()
            self._sim_time_s = 0.0
            self._batch_seq = 0
            t = threading.Thread(target=self._run_loop, name="osc-capture", daemon=True)
            self._thread = t
            t.start()
        logger.info("Capture thread started")

    def stop(self) -> None:
        self._stop.set()
        th: Optional[threading.Thread]
        with self._lock:
            th = self._thread
        if th is not None:
            th.join(timeout=10.0)
        with self._lock:
            self._thread = None
        try:
            self._device_manager.disconnect()
        except Exception as e:
            logger.debug("disconnect after stop: %s", e)
        logger.info("Capture thread stopped")

    def shutdown(self) -> None:
        self.stop()
        self._device_manager.teardown()

    @property
    def batches_sent(self) -> int:
        return self._batches_sent

    @property
    def last_batch_time(self) -> float:
        return self._last_batch_time

    @property
    def flat_runs(self) -> int:
        return self._flat_runs

    def _run_loop(self) -> None:
        try:
            self._device_manager.connect()
        except HantekSDKError as e:
            logger.error("Cannot start capture: %s", e)
            return

        self._sdk.set_read_chunk_samples(self._settings.read_chunk_samples)
        rate = self._settings.sample_rate_hz
        chunk = self._settings.read_chunk_samples
        interval = max(self._settings.capture_interval_s, 0.0)

        while not self._stop.is_set():
            t0_wall = time.time()
            try:
                # Simulation only when not using real hardware (no DLL path).
                if self._device_manager.is_simulating:
                    y = generate_sine_chunk(
                        self._sim_time_s,
                        rate,
                        chunk,
                        frequency_hz=self._settings.simulation_frequency_hz,
                        amplitude=self._settings.simulation_amplitude,
                    )
                    self._sim_time_s += len(y) / rate if rate > 0 else 0.0
                elif self._device_manager.state == DeviceState.CONNECTED:
                    # Real HT6000 path only while session is connected (no sine overlay).
                    y = self._sdk.read_data()
                    if y.size > 0:
                        self._device_manager.note_read_success()
                else:
                    if interval:
                        time.sleep(interval)
                    continue
            except Exception as e:
                self._device_manager.on_capture_read_failure(e)
                if interval:
                    time.sleep(interval)
                continue

            # Mark active capture only after at least one successful read.
            if self._device_manager.state == DeviceState.CONNECTED:
                self._device_manager.mark_capturing()

            if y.size == 0:
                if interval:
                    time.sleep(interval)
                continue

            # Basic flat-line detection to catch frozen/invalid streams.
            try:
                if float(np.ptp(y)) < 1e-6:
                    self._flat_runs += 1
                    if self._flat_runs % 25 == 0:
                        logger.warning("Signal appears flat for %s consecutive batches", self._flat_runs)
                else:
                    if self._flat_runs >= 25:
                        logger.info("Signal recovered after flat period (%s batches)", self._flat_runs)
                    self._flat_runs = 0
            except Exception:
                self._flat_runs = 0

            frame = SampleFrame(
                t0=t0_wall,
                sample_rate_hz=rate,
                samples=y,
            )
            self._buffer.append(frame)
            self._batch_seq += 1
            self._batches_sent += 1
            self._last_batch_time = t0_wall
            now_utc = datetime.now(timezone.utc)
            ptp = float(np.ptp(y)) if y.size else 0.0
            batch_rms = float(np.sqrt(np.mean(np.square(y.astype(np.float64))))) if y.size else 0.0
            batch: Dict[str, Any] = {
                "batch_seq": self._batch_seq,
                "t0": frame.t0,
                "t0_unix": frame.t0,
                "sample_rate_hz": frame.sample_rate_hz,
                "sample_count": int(y.size),
                "samples": y.astype(np.float32).tolist(),
                "mode": "simulation" if self._device_manager.is_simulating else "hardware",
                "server_time_utc": now_utc.isoformat(),
                "ptp": ptp,
                "rms": batch_rms,
                "volt_div": self._settings.volt_div,
                "time_div_s": self._settings.time_div_s,
                "drops": self._broadcaster.drop_count,
            }
            self._broadcaster.publish_batch_threadsafe(batch)
            if interval:
                time.sleep(interval)
