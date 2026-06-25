"""
conftest.py – shared fixtures for the Z-Sentinel IDS test suite.

Fixtures
--------
features_json_path   – absolute Path to models/features.json
models_dir           – absolute Path to models/
alert_manager        – fresh AlertManager (DB + WS disabled)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ── backend root (one level up from backend/tests/) ──────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "models"
FEATURES_JSON = MODELS_DIR / "features.json"


# ── path fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def features_json_path() -> Path:
    """Absolute path to models/features.json."""
    assert FEATURES_JSON.exists(), f"features.json not found at {FEATURES_JSON}"
    return FEATURES_JSON


@pytest.fixture(scope="session")
def models_dir() -> Path:
    """Absolute path to the models/ directory."""
    assert MODELS_DIR.exists(), f"models/ dir not found at {MODELS_DIR}"
    return MODELS_DIR


@pytest.fixture(scope="session")
def feature_names_from_json(features_json_path: Path) -> list[str]:
    """Parsed feature_names list from features.json."""
    with open(features_json_path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data["feature_names"]


# ── auto-reset rate limiter between every test ────────────────────────────────
# Rate limiter dùng in-memory state (module-level dict). Nếu không reset,
# counter tích lũy qua các test cases → tests bị 429 thay vì kết quả mong đợi.

@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Wipe tất cả rate-limit counters trước và sau mỗi test."""
    try:
        from backend.api.middleware.rate_limit import reset_all
        reset_all()
        yield
        reset_all()
    except ImportError:
        yield


# ── alert manager (no DB, no WebSocket) ──────────────────────────────────────

@pytest.fixture
def alert_manager():
    """Return a fresh AlertManager with DB and WS disabled."""
    from backend.alert_engine.alert_manager import AlertManager

    mgr = AlertManager(
        confidence_threshold=0.75,
        alert_cooldown=30,
        enable_db_save=False,
        enable_websocket=False,
    )
    return mgr


@pytest.fixture
def alert_manager_no_email():
    """Return a fresh AlertManager with DB, WS, and email disabled."""
    from backend.alert_engine.alert_manager import AlertManager

    mgr = AlertManager(
        confidence_threshold=0.75,
        alert_cooldown=30,
        enable_db_save=False,
        enable_websocket=False,
        enable_email=False,
    )
    return mgr


# ── shared SQLite in-memory session (also used by integration tests) ──────────

@pytest.fixture
def sqlite_session():
    """
    Yield a fresh SQLAlchemy session backed by an in-memory SQLite database.
    Schema is created and torn down per test – no Postgres required.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.database.models import Base

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    session = SessionFactory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()
