from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SignalBroadcaster:
    """
    Fan-out from the capture thread to asyncio WebSocket tasks.

    Uses ``loop.call_soon_threadsafe`` so producers never block on slow clients.
    If a subscriber queue is full, the oldest batch is dropped (live scope).
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._lock = threading.Lock()
        self._queues: List[asyncio.Queue[Dict[str, Any]]] = []
        self._drops = 0

    def register(self, maxsize: int) -> asyncio.Queue[Dict[str, Any]]:
        q: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=maxsize)
        with self._lock:
            self._queues.append(q)
        logger.debug("WebSocket subscriber registered (queues=%s)", len(self._queues))
        return q

    def unregister(self, q: asyncio.Queue[Dict[str, Any]]) -> None:
        with self._lock:
            if q in self._queues:
                self._queues.remove(q)
        logger.debug("WebSocket subscriber removed (queues=%s)", len(self._queues))

    @property
    def drop_count(self) -> int:
        with self._lock:
            return self._drops

    def publish_batch_threadsafe(self, batch: Dict[str, Any]) -> None:
        def _broadcast() -> None:
            with self._lock:
                targets = list(self._queues)
            for q in targets:
                self._put_drop_oldest(q, batch)

        try:
            self._loop.call_soon_threadsafe(_broadcast)
        except RuntimeError:
            logger.debug("Event loop not running; drop batch")

    def _put_drop_oldest(self, q: asyncio.Queue[Dict[str, Any]], batch: Dict[str, Any]) -> None:
        try:
            q.put_nowait(batch)
        except asyncio.QueueFull:
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                q.put_nowait(batch)
            except asyncio.QueueFull:
                with self._lock:
                    self._drops += 1
