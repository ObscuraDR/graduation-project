"""
Integration Tests – WebSocket Broadcast Queue
==============================================
Verifies that AlertBroadcastBridge correctly:
  1. Enqueues an alert dict into the thread-safe queue.
  2. The consumer loop dequeues and calls ConnectionManager.broadcast.

ConnectionManager.broadcast is mocked so no real WebSocket connection is
needed – this test is fully synchronous-safe via asyncio.run().
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.websocket import AlertBroadcastBridge, ConnectionManager


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_dummy_alert(alert_id: str = "test-001") -> dict:
    return {
        "alert_id": alert_id,
        "src_ip": "10.0.0.1",
        "dst_ip": "192.168.1.1",
        "attack_type": "DDoS",
        "severity": "critical",
        "confidence": 0.97,
    }


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_broadcast_bridge_enqueue() -> None:
    """
    enqueue_alert() must return True, increment enqueued_total,
    and place exactly one item in the internal queue.
    """
    mock_manager = MagicMock(spec=ConnectionManager)
    bridge = AlertBroadcastBridge(mock_manager, maxsize=100)

    alert = _make_dummy_alert()
    result = bridge.enqueue_alert(alert)

    assert result is True, "enqueue_alert() must return True on success"
    assert bridge.enqueued_total == 1
    assert bridge._thread_queue.qsize() == 1


@pytest.mark.unit
def test_broadcast_bridge_queue_full_drops_alert() -> None:
    """
    When the queue is full, enqueue_alert() must return False and
    increment dropped_total instead of raising.
    """
    mock_manager = MagicMock(spec=ConnectionManager)
    bridge = AlertBroadcastBridge(mock_manager, maxsize=1)

    # Fill the queue
    bridge.enqueue_alert(_make_dummy_alert("first"))
    assert bridge.enqueued_total == 1

    # This one must be dropped
    result = bridge.enqueue_alert(_make_dummy_alert("second"))
    assert result is False
    assert bridge.dropped_total == 1


@pytest.mark.integration
def test_websocket_broadcast_queue() -> None:
    """
    Full round-trip:
      1. Create bridge with mocked ConnectionManager.broadcast.
      2. Start the async consumer.
      3. Enqueue an alert from the 'sniffer thread' (sync call).
      4. Wait briefly for the consumer to process it.
      5. Assert ConnectionManager.broadcast was called with the correct payload.
    """

    async def _run():
        mock_broadcast = AsyncMock()
        mock_manager = MagicMock(spec=ConnectionManager)
        mock_manager.broadcast = mock_broadcast
        mock_manager.get_connection_count.return_value = 1

        bridge = AlertBroadcastBridge(mock_manager, maxsize=100)
        await bridge.start()

        alert = _make_dummy_alert("ws-test-001")
        enqueued = bridge.enqueue_alert(alert)
        assert enqueued is True

        # Give the consumer loop time to process (2 poll cycles × 0.25 s = 0.5 s)
        await asyncio.sleep(0.65)

        await bridge.stop(drain_timeout=1.0)

        # broadcast() should have been called once
        mock_broadcast.assert_called_once()
        call_args = mock_broadcast.call_args[0][0]  # first positional arg
        assert call_args["type"] == "alert"
        assert call_args["data"]["alert_id"] == "ws-test-001"
        assert call_args["data"]["attack_type"] == "DDoS"

    asyncio.run(_run())
