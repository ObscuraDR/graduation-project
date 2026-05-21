"""
Security Tests – Sniffer API Key Authentication
=================================================
Verifies that all /api/sniffer/* endpoints:
  - Return HTTP 401 when the X-API-Key header is missing.
  - Return HTTP 401 when an incorrect key is supplied.
  - Return HTTP 200 when the correct key is supplied.

Uses FastAPI TestClient (sync HTTPX transport). No live server, no Postgres,
no raw socket — fully CI-safe.

Key insight
-----------
``get_settings()`` uses ``@lru_cache``, so monkey-patching the *function* has
no effect after first call.  Instead we patch ``Settings.api_key`` on the
already-cached settings *instance* returned by ``get_settings()``, then restore
it in teardown.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

# ── constants ─────────────────────────────────────────────────────────────────
VALID_KEY = "test-api-key-for-pytest"
WRONG_KEY  = "totally-wrong-key"
EXPECTED_401 = {"detail": "Invalid or missing API key"}


# ── module-scoped client fixture ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """
    Build a TestClient around the full FastAPI app with the API key injected
    into the live settings singleton and all heavy I/O patched away.
    """
    from fastapi.testclient import TestClient
    from backend.config import get_settings
    from backend.api.websocket import AlertBroadcastBridge

    # --- inject test key into the cached settings singleton ---
    settings = get_settings()
    original_key = settings.api_key
    # pydantic-settings models are normally frozen; bypass via __dict__
    object.__setattr__(settings, "api_key", VALID_KEY)

    try:
        with patch("backend.database.connection.init_db", return_value=None):
            with patch.object(AlertBroadcastBridge, "start", new=AsyncMock(return_value=None)):
                with patch.object(AlertBroadcastBridge, "stop",  new=AsyncMock(return_value=None)):
                    from backend.main import app
                    with TestClient(app, raise_server_exceptions=False) as c:
                        yield c
    finally:
        # Restore original key so other test modules are unaffected
        object.__setattr__(settings, "api_key", original_key)


# ── 401 – missing key ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_sniffer_requires_api_key(client) -> None:
    """GET /api/sniffer/status without X-API-Key → 401."""
    r = client.get("/api/sniffer/status")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
    assert r.json() == EXPECTED_401


@pytest.mark.unit
def test_sniffer_start_requires_api_key(client) -> None:
    """POST /api/sniffer/start without key → 401."""
    r = client.post("/api/sniffer/start")
    assert r.status_code == 401
    assert r.json() == EXPECTED_401


@pytest.mark.unit
def test_sniffer_stop_requires_api_key(client) -> None:
    """POST /api/sniffer/stop without key → 401."""
    r = client.post("/api/sniffer/stop")
    assert r.status_code == 401
    assert r.json() == EXPECTED_401


# ── 401 – wrong key ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_sniffer_rejects_wrong_api_key(client) -> None:
    """GET /api/sniffer/status with wrong key → 401."""
    r = client.get("/api/sniffer/status", headers={"X-API-Key": WRONG_KEY})
    assert r.status_code == 401
    assert r.json() == EXPECTED_401


# ── 200 – valid key ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_sniffer_accepts_valid_api_key(client) -> None:
    """
    GET /api/sniffer/status with correct key → 200.
    Pipeline never started so body reports is_running=False.
    """
    r = client.get("/api/sniffer/status", headers={"X-API-Key": VALID_KEY})
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("is_running") is False or body.get("status") == "stopped"


@pytest.mark.unit
def test_sniffer_stop_accepts_valid_api_key(client) -> None:
    """
    POST /api/sniffer/stop with correct key → 200 (auth passes,
    business logic returns 'Sniffer is not running').
    """
    r = client.post("/api/sniffer/stop", headers={"X-API-Key": VALID_KEY})
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    assert r.json().get("status") == "error"   # "Sniffer is not running"


# ── public endpoints (no key required) ───────────────────────────────────────

@pytest.mark.unit
def test_health_is_public(client) -> None:
    """GET /health must be accessible without X-API-Key."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


@pytest.mark.unit
def test_websocket_is_public(client) -> None:
    """WebSocket /ws must accept connections without X-API-Key."""
    with client.websocket_connect("/ws") as ws:
        ws.send_text("ping")
        data = ws.receive_text()
        assert data   # any response proves connection is open
