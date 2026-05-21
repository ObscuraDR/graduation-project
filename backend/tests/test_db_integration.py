"""
Integration Tests – Database (PostgreSQL via SQLAlchemy)
=========================================================
Tests that require a live PostgreSQL connection are automatically SKIPPED
when the database is unavailable – no connection string needed in CI.

Covered:
  - test_db_insert_alert: inserts one AttackAlert row and confirms count grows.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest


# ---------------------------------------------------------------------------
# session-scoped DB availability check
# ---------------------------------------------------------------------------

def _pg_available() -> bool:
    """Return True only if PostgreSQL responds to a ping."""
    try:
        from sqlalchemy import text
        from backend.database.connection import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_pg = pytest.mark.skipif(
    not _pg_available(),
    reason="PostgreSQL is not available – skipping DB integration test",
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    """Yield a live SQLAlchemy session, rolling back after each test."""
    from backend.database.connection import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

@requires_pg
@pytest.mark.integration
def test_db_insert_alert(db_session) -> None:
    """
    Insert a dummy AttackAlert row via AttackAlertRepository and confirm the
    row count increased by exactly 1.
    """
    from sqlalchemy import func
    from backend.database.models import AttackAlert
    from backend.database.repository import AttackAlertRepository

    # Row count before insert
    count_before: int = db_session.query(func.count(AttackAlert.id)).scalar()

    dummy_alert = {
        "alert_id": str(uuid.uuid4()),
        "src_ip": "10.99.88.77",
        "dst_ip": "192.168.0.1",
        "src_port": 12345,
        "dst_port": 443,
        "protocol": "TCP",
        "attack_type": "PortScan",
        "severity": "high",
        "confidence": 0.88,
        "correlated": False,
        "original_severity": "high",
        "status": "active",
        "model_name": "ensemble",
        "model_version": "1.0",
        "all_probabilities": {"Normal": 0.12, "PortScan": 0.88},
        "timestamp": datetime.utcnow().isoformat(),
    }

    AttackAlertRepository.create_alert(db_session, dummy_alert, flow_id=None)

    count_after: int = db_session.query(func.count(AttackAlert.id)).scalar()
    assert count_after == count_before + 1, (
        f"Expected row count to grow by 1 (was {count_before}, now {count_after})"
    )
