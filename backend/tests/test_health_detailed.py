"""
backend/tests/test_health_detailed.py
Tests for GET /health/detailed — all external services are mocked.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from backend.main import app
    return TestClient(app, raise_server_exceptions=False)


def _engine_mock(ok: bool):
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    if not ok:
        conn.__enter__.side_effect = Exception("postgres down")
    eng = MagicMock()
    eng.connect.return_value = conn
    return eng


def _cache_mock(ok: bool):
    m = MagicMock()
    m.is_connected.return_value = ok
    return m


def _mongo_mock(ok: bool):
    m = MagicMock()
    if not ok:
        m.admin.command.side_effect = Exception("mongo down")
    return m


def _loader_mock(loaded: bool):
    m = MagicMock()
    m.is_loaded = loaded
    return m


PATCHES = {
    "engine": "backend.database.connection.engine",
    "cache": "backend.cache.redis_cache.get_cache",
    "mongo": "backend.database.connection.get_mongo_client",
    "loader": "backend.detection_engine.model_loader.get_model_loader",
}


class TestHealthDetailed:
    def _call(self, client, postgres=True, redis=True, mongo=True, model=True):
        with patch(PATCHES["engine"], _engine_mock(postgres)), \
             patch(PATCHES["cache"], return_value=_cache_mock(redis)), \
             patch(PATCHES["mongo"], return_value=_mongo_mock(mongo)), \
             patch(PATCHES["loader"], return_value=_loader_mock(model)):
            return client.get("/health/detailed")

    def test_all_services_up(self, client):
        resp = self._call(client)
        assert resp.status_code == 200
        data = resp.json()
        assert data["postgres"]["connected"] is True
        assert data["redis"]["connected"] is True
        assert data["mongo"]["connected"] is True
        assert data["model_loaded"] is True
        assert data["pipeline_running"] is False
        assert "timestamp" in data

    def test_postgres_down(self, client):
        resp = self._call(client, postgres=False)
        assert resp.status_code == 200
        assert resp.json()["postgres"]["connected"] is False

    def test_redis_down(self, client):
        resp = self._call(client, redis=False)
        assert resp.status_code == 200
        assert resp.json()["redis"]["connected"] is False

    def test_mongo_down(self, client):
        resp = self._call(client, mongo=False)
        assert resp.status_code == 200
        assert resp.json()["mongo"]["connected"] is False

    def test_model_not_loaded(self, client):
        resp = self._call(client, model=False)
        assert resp.status_code == 200
        assert resp.json()["model_loaded"] is False

    def test_all_services_down(self, client):
        resp = self._call(client, postgres=False, redis=False, mongo=False, model=False)
        assert resp.status_code == 200
        data = resp.json()
        assert data["postgres"]["connected"] is False
        assert data["redis"]["connected"] is False
        assert data["mongo"]["connected"] is False
        assert data["model_loaded"] is False

    def test_response_schema(self, client):
        resp = self._call(client)
        data = resp.json()
        required = {"postgres", "redis", "mongo", "model_loaded", "pipeline_running", "timestamp"}
        assert required.issubset(data.keys())
