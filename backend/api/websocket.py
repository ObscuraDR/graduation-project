"""
WebSocket Manager and thread-safe alert broadcast bridge.

Sniffer/pipeline threads MUST NOT call async WebSocket methods directly.
They enqueue messages on AlertBroadcastBridge; a lifespan consumer task
broadcasts to all clients on the main asyncio event loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Sentinel value to unblock the consumer during shutdown
_SHUTDOWN_SENTINEL = object()


class ConnectionManager:
    """Manage WebSocket connections (async event loop only)."""

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket connected. Total connections: %s", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(
                "WebSocket disconnected. Total connections: %s",
                len(self.active_connections),
            )

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        try:
            await websocket.send_text(message)
        except Exception as exc:
            logger.error("Error sending personal message: %s", exc)
            self.disconnect(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast JSON message to all connected clients."""
        if not self.active_connections:
            return

        message_str = json.dumps(message, default=str)
        disconnected: List[WebSocket] = []

        for connection in list(self.active_connections):
            try:
                await connection.send_text(message_str)
            except Exception as exc:
                logger.error("Error broadcasting to connection: %s", exc)
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast_alert(self, alert: Dict[str, Any]) -> None:
        await self.broadcast({"type": "alert", "data": alert})

    async def broadcast_traffic_update(self, traffic_data: Dict[str, Any]) -> None:
        await self.broadcast({"type": "traffic", "data": traffic_data})

    async def broadcast_system_status(self, status: Dict[str, Any]) -> None:
        await self.broadcast({"type": "status", "data": status})

    def get_connection_count(self) -> int:
        return len(self.active_connections)


class AlertBroadcastBridge:
    """
    Thread-safe bridge between the sniffer thread and async WebSocket broadcast.

    Producers (sync): enqueue_alert() -> queue.Queue (non-blocking put_nowait)
    Consumer (async):  lifespan task reads queue and calls ConnectionManager.broadcast
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        maxsize: int = 10_000,
    ) -> None:
        self._manager = connection_manager
        self._thread_queue: queue.Queue = queue.Queue(maxsize=maxsize)
        self._consumer_task: Optional[asyncio.Task] = None
        self._running = False
        self.enqueued_total = 0
        self.dropped_total = 0
        self.broadcast_total = 0

    @property
    def is_running(self) -> bool:
        return self._running

    def enqueue_alert(self, alert: Dict[str, Any]) -> bool:
        """
        Enqueue an alert for WebSocket broadcast (sniffer / pipeline thread safe).

        Returns:
            True if enqueued, False if queue is full (alert dropped).
        """
        message = {"type": "alert", "data": alert}
        try:
            self._thread_queue.put_nowait(message)
            self.enqueued_total += 1
            return True
        except queue.Full:
            self.dropped_total += 1
            logger.warning(
                "Alert broadcast queue full (%s), dropping alert %s",
                self._thread_queue.maxsize,
                alert.get("alert_id"),
            )
            return False

    def _blocking_get(self, timeout: float) -> Any:
        """Blocking get for use inside asyncio.to_thread only."""
        try:
            return self._thread_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    async def start(self) -> None:
        """Start the async consumer (call from FastAPI lifespan startup)."""
        if self._running:
            return
        self._running = True
        self._consumer_task = asyncio.create_task(
            self._consume_loop(),
            name="alert-broadcast-consumer",
        )
        logger.info("Alert broadcast consumer started")

    async def stop(self, drain_timeout: float = 3.0) -> None:
        """Stop consumer and drain or cancel remaining work."""
        if not self._running and self._consumer_task is None:
            return

        self._running = False

        # Unblock consumer if waiting on queue.get
        try:
            self._thread_queue.put_nowait(_SHUTDOWN_SENTINEL)
        except queue.Full:
            pass

        if self._consumer_task is not None:
            try:
                await asyncio.wait_for(self._consumer_task, timeout=drain_timeout)
            except asyncio.TimeoutError:
                logger.warning("Alert broadcast consumer shutdown timed out; cancelling")
                self._consumer_task.cancel()
                try:
                    await self._consumer_task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                pass
            self._consumer_task = None

        await self._drain_remaining_async()
        logger.info(
            "Alert broadcast consumer stopped (enqueued=%s, broadcast=%s, dropped=%s)",
            self.enqueued_total,
            self.broadcast_total,
            self.dropped_total,
        )

    async def _drain_remaining_async(self) -> None:
        """Broadcast any messages left in the thread queue after consumer stops."""
        while True:
            try:
                item = self._thread_queue.get_nowait()
            except queue.Empty:
                break
            if item is _SHUTDOWN_SENTINEL:
                continue
            await self._dispatch(item)

    async def _consume_loop(self) -> None:
        """Read from thread-safe queue and broadcast on the event loop."""
        try:
            while self._running:
                item = await asyncio.to_thread(self._blocking_get, 0.25)
                if item is None:
                    continue
                if item is _SHUTDOWN_SENTINEL:
                    if not self._running:
                        break
                    continue
                await self._dispatch(item)
        except asyncio.CancelledError:
            logger.debug("Alert broadcast consumer cancelled")
            raise
        except Exception as exc:
            logger.exception("Alert broadcast consumer error: %s", exc)

    async def _dispatch(self, message: Dict[str, Any]) -> None:
        try:
            await self._manager.broadcast(message)
            self.broadcast_total += 1
        except Exception as exc:
            logger.error("Failed to broadcast queued message: %s", exc)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "is_running": self._running,
            "queue_size": self._thread_queue.qsize(),
            "queue_maxsize": self._thread_queue.maxsize,
            "enqueued_total": self.enqueued_total,
            "broadcast_total": self.broadcast_total,
            "dropped_total": self.dropped_total,
            "active_connections": self._manager.get_connection_count(),
        }


# Global singletons
manager = ConnectionManager()
broadcast_bridge = AlertBroadcastBridge(manager)


def get_connection_manager() -> ConnectionManager:
    return manager


def get_broadcast_bridge() -> AlertBroadcastBridge:
    return broadcast_bridge
