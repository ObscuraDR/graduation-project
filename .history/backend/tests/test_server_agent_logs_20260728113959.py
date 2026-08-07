import asyncio
import gzip
import json
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

sys.modules.setdefault("psycopg2", types.ModuleType("psycopg2"))

from backend.api.routes import servers


class DummyRequest:
    def __init__(self, body: bytes, headers: dict | None = None):
        self._body = body
        self.headers = headers or {}

    async def body(self) -> bytes:
        return self._body


@pytest.mark.unit
def test_receive_agent_logs_accepts_gzip_payload() -> None:
    payload = {
        "server_id": 2,
        "events": [
            {
                "event_type": "http_flood",
                "source_ip": "203.0.113.10",
                "message": "HTTP flood detected",
                "severity": "high",
            }
        ],
        "timestamp": "2026-07-28T00:00:00Z",
    }
    compressed_body = gzip.compress(json.dumps(payload).encode("utf-8"))

    class DummyDb:
        def close(self) -> None:
            return None

    def fake_get_db():
        yield DummyDb()

    with patch("backend.api.routes.servers.get_db", fake_get_db), patch(
        "backend.api.routes.servers.ServerRepository.get_server_by_id",
        return_value=SimpleNamespace(name="server-2"),
    ), patch("backend.api.routes.servers._log_queue.put", new=AsyncMock()) as put_mock:
        response = asyncio.run(
            servers.receive_agent_logs(
                server_id=2,
                request=DummyRequest(
                    compressed_body,
                    headers={"content-encoding": "gzip", "content-type": "application/json"},
                ),
                api_key="test-key",
            )
        )

    assert response["status"] == "accepted"
    assert response["queued_events"] == 1
    assert put_mock.await_count == 1
