"""
Tests – Rate Limiting Middleware
=================================
Verifies sliding-window rate limits for /api/sniffer/*, /api/whitelist/*,
and /api/xai/* without a live server or real DB.

Strategy
--------
- Use FastAPI TestClient (sync HTTPX transport).
- Reset rate-limit state before every test via reset_all().
- Spoof client IP via X-Forwarded-For header so tests are IP-isolated.
- Patch heavy I/O (DB init, broadcast bridge) to keep tests fast.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

VALID_KEY = "test-key-ratelimit"


# ---------------------------------------------------------------------------
# Module-scoped TestClient
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    import sys, types
    # Stub scapy before importing main (packet_sniffer raises ImportError without it)
    for mod in ["scapy", "scapy.all", "scapy.layers", "scapy.layers.inet", "scapy.arch", "scapy.arch.windows"]:
        sys.modules.setdefault(mod, types.ModuleType(mod))

    from fastapi.testclient import TestClient
    from backend.config import get_settings
    from backend.api.websocket import AlertBroadcastBridge

    settings = get_settings()
    original_key = settings.api_key
    object.__setattr__(settings, "api_key", VALID_KEY)

    try:
        with patch("backend.database.connection.init_db", return_value=None):
            with patch.object(AlertBroadcastBridge, "start", new=AsyncMock(return_value=None)):
                with patch.object(AlertBroadcastBridge, "stop", new=AsyncMock(return_value=None)):
                    from backend.main import app
                    with TestClient(app, raise_server_exceptions=False) as c:
                        yield c
    finally:
        object.__setattr__(settings, "api_key", original_key)


@pytest.fixture(autouse=True)
def _reset_limits():
    """Wipe all rate-limit counters before each test."""
    from backend.api.middleware.rate_limit import reset_all
    reset_all()
    yield
    reset_all()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers(ip: str) -> dict:
    return {"X-API-Key": VALID_KEY, "X-Forwarded-For": ip}


# ---------------------------------------------------------------------------
# /api/sniffer/* — limit 10 req/60s
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_sniffer_status_under_limit(client) -> None:
    """10 requests to /api/sniffer/status should all succeed (200, not 429)."""
    for i in range(10):
        r = client.get("/api/sniffer/status", headers=_headers("10.0.0.1"))
        assert r.status_code == 200, f"Request {i+1} got {r.status_code}"


@pytest.mark.unit
def test_sniffer_status_exceeds_limit(client) -> None:
    """11th request to /api/sniffer/status from same IP → 429."""
    for _ in range(10):
        client.get("/api/sniffer/status", headers=_headers("10.0.0.2"))

    r = client.get("/api/sniffer/status", headers=_headers("10.0.0.2"))
    assert r.status_code == 429
    body = r.json()
    assert body["error"] == "rate_limit_exceeded"
    assert "retry_after_seconds" in body
    assert int(r.headers["Retry-After"]) > 0


@pytest.mark.unit
def test_sniffer_limit_is_per_ip(client) -> None:
    """Different IPs have independent counters."""
    for _ in range(10):
        client.get("/api/sniffer/status", headers=_headers("10.0.1.1"))

    # 10.0.1.1 is exhausted; 10.0.1.2 should still be fine
    r = client.get("/api/sniffer/status", headers=_headers("10.0.1.2"))
    assert r.status_code == 200


@pytest.mark.unit
def test_sniffer_429_body_structure(client) -> None:
    """429 response must include error, message, retry_after_seconds."""
    for _ in range(10):
        client.get("/api/sniffer/status", headers=_headers("10.0.0.3"))

    r = client.get("/api/sniffer/status", headers=_headers("10.0.0.3"))
    assert r.status_code == 429
    body = r.json()
    assert "error" in body
    assert "message" in body
    assert "retry_after_seconds" in body
    assert body["retry_after_seconds"] > 0


# ---------------------------------------------------------------------------
# /api/whitelist/* — limit 30 req/60s
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_whitelist_under_limit(client) -> None:
    """30 requests to /api/whitelist/list should all succeed."""
    for i in range(30):
        r = client.get("/api/whitelist/list", headers=_headers("10.0.2.1"))
        # 200 or 500 (DB not available) — anything but 429
        assert r.status_code != 429, f"Request {i+1} was rate-limited unexpectedly"


@pytest.mark.unit
def test_whitelist_exceeds_limit(client) -> None:
    """31st request to /api/whitelist/list → 429."""
    from backend.api.middleware.rate_limit import reset_ip
    from backend.database.connection import get_db
    from backend.main import app

    ip = "10.0.2.2"
    reset_ip(ip)

    # Override the DB dependency so every request returns 200 (no real Postgres needed)
    mock_session = MagicMock()
    mock_session.query.return_value.order_by.return_value.all.return_value = []

    def _override_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_db
    try:
        for i in range(30):
            r = client.get("/api/whitelist/list", headers=_headers(ip))
            assert r.status_code != 429, f"Request {i+1} was rate-limited too early"

        r = client.get("/api/whitelist/list", headers=_headers(ip))
        assert r.status_code == 429
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.unit
def test_whitelist_higher_limit_than_sniffer(client) -> None:
    """Whitelist allows 30 req while sniffer only allows 10 — limits are independent."""
    ip = "10.0.2.3"
    # exhaust sniffer limit
    for _ in range(10):
        client.get("/api/sniffer/status", headers=_headers(ip))
    assert client.get("/api/sniffer/status", headers=_headers(ip)).status_code == 429

    # whitelist should still have budget
    r = client.get("/api/whitelist/list", headers=_headers(ip))
    assert r.status_code != 429


# ---------------------------------------------------------------------------
# /api/xai/* — limit 60 req/60s
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_xai_limit_is_60(client) -> None:
    """60 requests to /api/xai/explain should not be rate-limited (may fail for other reasons)."""
    ip = "10.0.3.1"
    for i in range(60):
        r = client.post(
            "/api/xai/explain",
            json={"model_name": "ensemble", "features": {}},
            headers=_headers(ip),
        )
        assert r.status_code != 429, f"Request {i+1} was rate-limited at count {i+1}"


@pytest.mark.unit
def test_xai_exceeds_limit(client) -> None:
    """61st request to /api/xai/explain → 429."""
    ip = "10.0.3.2"
    for _ in range(60):
        client.post(
            "/api/xai/explain",
            json={"model_name": "ensemble", "features": {}},
            headers=_headers(ip),
        )

    r = client.post(
        "/api/xai/explain",
        json={"model_name": "ensemble", "features": {}},
        headers=_headers(ip),
    )
    assert r.status_code == 429


# ---------------------------------------------------------------------------
# Unprotected endpoints are not rate-limited
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_health_not_rate_limited(client) -> None:
    """/health has no rate limit — 100 requests should all pass."""
    for i in range(100):
        r = client.get("/health", headers={"X-Forwarded-For": "10.0.4.1"})
        assert r.status_code == 200, f"Request {i+1} unexpectedly got {r.status_code}"


# ---------------------------------------------------------------------------
# reset_ip helper
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_reset_ip_clears_counter(client) -> None:
    """reset_ip() allows a previously exhausted IP to make requests again."""
    from backend.api.middleware.rate_limit import reset_ip

    ip = "10.0.5.1"
    for _ in range(10):
        client.get("/api/sniffer/status", headers=_headers(ip))
    assert client.get("/api/sniffer/status", headers=_headers(ip)).status_code == 429

    reset_ip(ip)
    r = client.get("/api/sniffer/status", headers=_headers(ip))
    assert r.status_code == 200
