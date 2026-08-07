import asyncio
import gzip
import json
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

psycopg2_stub = types.ModuleType('psycopg2')
psycopg2_stub.paramstyle = 'pyformat'
psycopg2_stub.connect = lambda *args, **kwargs: None
psycopg2_stub.extras = types.SimpleNamespace()
sys.modules['psycopg2'] = psycopg2_stub
sys.modules['psycopg2.extras'] = psycopg2_stub.extras

from backend.api.routes import servers


class DummyRequest:
    def __init__(self, body, headers=None):
        self._body = body
        self.headers = headers or {}

    async def body(self):
        return self._body


payload = {
    'server_id': 2,
    'events': [
        {
            'event_type': 'http_flood',
            'source_ip': '203.0.113.10',
            'message': 'HTTP flood detected',
            'severity': 'high',
        }
    ],
    'timestamp': '2026-07-28T00:00:00Z',
}
compressed_body = gzip.compress(json.dumps(payload).encode('utf-8'))


class DummyDb:
    def close(self):
        return None


def fake_get_db():
    yield DummyDb()


with patch('backend.api.routes.servers.get_db', fake_get_db), patch(
    'backend.api.routes.servers.ServerRepository.get_server_by_id',
    return_value=SimpleNamespace(name='server-2'),
), patch('backend.api.routes.servers._log_queue.put', new=AsyncMock()) as put_mock:
    response = asyncio.run(
        servers.receive_agent_logs(
            server_id=2,
            request=DummyRequest(compressed_body, headers={'content-encoding': 'gzip', 'content-type': 'application/json'}),
            api_key='test-key',
        )
    )

print(response)
print('await_count=', put_mock.await_count)
