"""
JWT Authentication Tests
=========================
Covers the single-admin login flow added in ``backend/api/auth.py``:

  - POST /api/auth/login with correct creds  → 200 + token
  - POST /api/auth/login with wrong password → 401
  - POST /api/auth/login with unknown user   → 401
  - GET  /api/auth/me  without token         → 401
  - GET  /api/auth/me  with valid token      → 200 + user info
  - Token round-trip (create → decode) helpers

Uses FastAPI TestClient with ``get_db`` overridden to an in-memory SQLite
session seeded with an admin user. No Postgres, no live server — CI-safe.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch


ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


@pytest.fixture(scope="module")
def client_and_session():
    """
    TestClient around the full app, with get_db overridden to a shared
    in-memory SQLite session containing one seeded admin user.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from backend.database.models import Base, User
    from backend.database.connection import get_db
    from backend.api.auth import hash_password
    from backend.api.websocket import AlertBroadcastBridge

    # StaticPool + shared in-memory DB so every get_db() call sees same data
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    seed = TestSession()
    seed.add(
        User(
            username=ADMIN_USER,
            email="admin@ids-system.com",
            password_hash=hash_password(ADMIN_PASS),
            role="admin",
        )
    )
    seed.commit()
    seed.close()

    def _override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    with patch("backend.database.connection.init_db", return_value=None):
        with patch.object(AlertBroadcastBridge, "start", new=AsyncMock(return_value=None)):
            with patch.object(AlertBroadcastBridge, "stop", new=AsyncMock(return_value=None)):
                from backend.main import app

                app.dependency_overrides[get_db] = _override_get_db
                try:
                    with TestClient(app, raise_server_exceptions=False) as c:
                        yield c
                finally:
                    app.dependency_overrides.pop(get_db, None)


# ── login ────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_login_success(client_and_session) -> None:
    r = client_and_session.post(
        "/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] > 0
    assert body["user"]["username"] == ADMIN_USER
    assert body["user"]["role"] == "admin"


@pytest.mark.unit
def test_login_wrong_password(client_and_session) -> None:
    r = client_and_session.post(
        "/api/auth/login", json={"username": ADMIN_USER, "password": "wrongpass"}
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Incorrect username or password"


@pytest.mark.unit
def test_login_unknown_user(client_and_session) -> None:
    r = client_and_session.post(
        "/api/auth/login", json={"username": "ghost", "password": "whatever"}
    )
    assert r.status_code == 401


# ── /me protected endpoint ─────────────────────────────────────────────────

@pytest.mark.unit
def test_me_requires_token(client_and_session) -> None:
    client_and_session.cookies.clear()
    r = client_and_session.get("/api/auth/me")
    assert r.status_code == 401


@pytest.mark.unit
def test_me_rejects_garbage_token(client_and_session) -> None:
    client_and_session.cookies.clear()
    r = client_and_session.get(
        "/api/auth/me", headers={"Authorization": "Bearer not.a.real.token"}
    )
    assert r.status_code == 401


@pytest.mark.unit
def test_me_with_valid_token(client_and_session) -> None:
    login = client_and_session.post(
        "/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}
    )
    token = login.json()["access_token"]

    r = client_and_session.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["username"] == ADMIN_USER
    assert body["role"] == "admin"


# ── token helper unit tests (no HTTP) ────────────────────────────────────────

@pytest.mark.unit
def test_token_create_and_decode_roundtrip() -> None:
    from jose import jwt
    from backend.api.auth import create_access_token
    from backend.config import get_settings

    token, expires_in = create_access_token(subject="admin", role="admin")
    assert expires_in > 0

    settings = get_settings()
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"
    assert "exp" in payload


@pytest.mark.unit
def test_password_hash_and_verify() -> None:
    from backend.api.auth import hash_password, verify_password

    h = hash_password("s3cret-pw")
    assert verify_password("s3cret-pw", h) is True
    assert verify_password("wrong", h) is False
    # Malformed hash must not raise, just return False
    assert verify_password("anything", "not-a-bcrypt-hash") is False
