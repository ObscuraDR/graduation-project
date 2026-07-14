"""
Unit Tests – Alert Manager
===========================
Tests AlertManager behaviour without touching PostgreSQL or WebSocket:
  - Cooldown suppression (same src_ip within cooldown window)
  - Normal traffic is never converted to an alert
  - Confidence below threshold is suppressed
  - Whitelisted IPs are suppressed
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from backend.alert_engine.alert_manager import AlertManager


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_prediction(
    attack_type: str = "DDoS",
    confidence: float = 0.95,
    severity: str = "critical",
) -> dict:
    return {
        "attack_type": attack_type,
        "confidence": confidence,
        "severity": severity,
        "model_name": "ensemble",
        "model_version": "1.0",
        "features": {},
        "all_probabilities": {},
    }


def _make_flow_info(src_ip: str = "10.0.0.1", dst_ip: str = "192.168.1.1") -> dict:
    return {
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "src_port": 54321,
        "dst_port": 80,
        "protocol": "TCP",
        "flow_key": f"{src_ip}:54321-{dst_ip}:80",
    }


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_alert_manager_cooldown(alert_manager: AlertManager) -> None:
    """
    Two alerts from the same src_ip within the cooldown window:
    the first must be returned; the second must be suppressed (None).
    """
    prediction = _make_prediction()
    flow_info = _make_flow_info(src_ip="10.0.0.42")

    # First alert – should be generated
    alert1 = alert_manager.generate_alert(prediction, flow_info)
    assert alert1 is not None, "First alert should be generated"
    assert alert1["src_ip"] == "10.0.0.42"
    assert alert1["attack_type"] == "DDoS"

    # Second alert immediately after – should be suppressed by cooldown
    alert2 = alert_manager.generate_alert(prediction, flow_info)
    assert alert2 is None, "Second alert within cooldown window must be suppressed"


@pytest.mark.unit
def test_alert_manager_normal_traffic_suppressed(alert_manager: AlertManager) -> None:
    """Normal traffic must never produce an alert."""
    prediction = _make_prediction(attack_type="Normal", confidence=0.99, severity="low")
    flow_info = _make_flow_info()

    result = alert_manager.generate_alert(prediction, flow_info)
    assert result is None


@pytest.mark.unit
def test_alert_manager_low_confidence_suppressed(alert_manager: AlertManager) -> None:
    """Alerts with confidence below threshold must be suppressed."""
    # Default threshold is 0.75; use 0.50
    prediction = _make_prediction(attack_type="PortScan", confidence=0.50)
    flow_info = _make_flow_info(src_ip="10.0.0.99")

    result = alert_manager.generate_alert(prediction, flow_info)
    assert result is None


@pytest.mark.unit
def test_alert_manager_whitelist_suppressed(alert_manager: AlertManager) -> None:
    """Alerts from a whitelisted IP must be suppressed."""
    ip = "10.0.0.77"
    alert_manager.add_to_whitelist(ip)

    prediction = _make_prediction()
    flow_info = _make_flow_info(src_ip=ip)

    result = alert_manager.generate_alert(prediction, flow_info)
    assert result is None


@pytest.mark.unit
def test_alert_manager_cooldown_expires(alert_manager: AlertManager) -> None:
    """After cooldown expires, the same src_ip should generate a new alert."""
    prediction = _make_prediction()
    flow_info = _make_flow_info(src_ip="10.0.0.55")

    # First alert
    alert1 = alert_manager.generate_alert(prediction, flow_info)
    assert alert1 is not None

    # Expire cooldown: backdate in-memory history AND clear Redis TTL key
    # (cooldown check ưu tiên Redis nếu available — phải clear cả hai)
    from datetime import timedelta
    past = datetime.utcnow() - timedelta(seconds=alert_manager.alert_cooldown + 1)
    alert_manager.alert_history["10.0.0.55"] = past
    from backend.cache.redis_cache import get_cache
    cache = get_cache()
    if cache.is_connected():
        cache.clear_alert_cooldown("10.0.0.55")

    # Now the cooldown has expired – second alert should succeed
    alert2 = alert_manager.generate_alert(prediction, flow_info)
    assert alert2 is not None, "Alert should be generated after cooldown expires"


@pytest.mark.unit
def test_alert_manager_stats_incremented(alert_manager: AlertManager) -> None:
    """total_alerts counter must increment for each generated alert."""
    before = alert_manager.total_alerts

    alert_manager.generate_alert(
        _make_prediction(),
        _make_flow_info(src_ip="10.1.2.3"),
    )
    assert alert_manager.total_alerts == before + 1


# ---------------------------------------------------------------------------
# Severity escalation & correlation
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_severity_escalated_after_repeated_attacks() -> None:
    """
    5+ attacks from the same IP within correlation_window escalate
    low/medium severity to high, and high to critical.
    Source: _apply_correlation() – total_recent >= 5 branch.
    """
    mgr = AlertManager(
        confidence_threshold=0.75,
        alert_cooldown=0,
        correlation_window=60,
        enable_db_save=False,
        enable_websocket=False,
        enable_email=False,
    )

    src_ip = "10.5.5.5"
    # Generate 5 alerts with medium severity to fill attack_patterns
    for i in range(5):
        flow = _make_flow_info(src_ip=src_ip)
        flow["flow_key"] = f"{src_ip}:1000{i}-192.168.1.1:80"
        mgr.generate_alert(_make_prediction(severity="medium"), flow)

    # 6th alert: severity should be escalated from medium → high
    flow6 = _make_flow_info(src_ip=src_ip)
    flow6["flow_key"] = f"{src_ip}:20000-192.168.1.1:80"
    alert = mgr.generate_alert(_make_prediction(severity="medium"), flow6)

    assert alert is not None
    assert alert["severity"] in ("high", "critical"), (
        f"Expected escalated severity, got {alert['severity']}"
    )
    assert alert["correlated"] is True, "Alert should be marked as correlated"


@pytest.mark.unit
def test_severity_not_escalated_below_threshold() -> None:
    """
    Fewer than 5 attacks from the same IP should NOT escalate severity.
    """
    mgr = AlertManager(
        confidence_threshold=0.75,
        alert_cooldown=0,
        correlation_window=60,
        enable_db_save=False,
        enable_websocket=False,
        enable_email=False,
    )

    src_ip = "10.6.6.6"
    # Only 2 prior alerts — below the escalation threshold of 5
    # Use non-DDoS/PortScan/BruteForce attack type to avoid type-specific escalation rules
    for i in range(2):
        flow = _make_flow_info(src_ip=src_ip)
        flow["flow_key"] = f"{src_ip}:3000{i}-192.168.1.1:80"
        mgr.generate_alert(
            _make_prediction(attack_type="Botnet", severity="low"),
            flow,
        )

    flow3 = _make_flow_info(src_ip=src_ip)
    flow3["flow_key"] = f"{src_ip}:40000-192.168.1.1:80"
    alert = mgr.generate_alert(
        _make_prediction(attack_type="Botnet", severity="low"),
        flow3,
    )

    assert alert is not None
    assert alert["severity"] == "low", (
        f"Severity should remain 'low' with only 2 prior attacks, got {alert['severity']}"
    )
    assert alert["correlated"] is False


@pytest.mark.unit
def test_ddos_correlation_escalates_to_critical() -> None:
    """
    DDoS attack with 2+ prior DDoS alerts from same IP escalates to critical.
    Source: _apply_correlation() – DDoS branch (total_recent >= 2).
    """
    mgr = AlertManager(
        confidence_threshold=0.75,
        alert_cooldown=0,
        correlation_window=60,
        enable_db_save=False,
        enable_websocket=False,
        enable_email=False,
    )

    src_ip = "10.7.7.7"
    # 2 prior DDoS alerts
    for i in range(2):
        flow = _make_flow_info(src_ip=src_ip)
        flow["flow_key"] = f"{src_ip}:5000{i}-192.168.1.1:80"
        mgr.generate_alert(_make_prediction(attack_type="DDoS", severity="high"), flow)

    # 3rd DDoS alert should be escalated to critical
    flow3 = _make_flow_info(src_ip=src_ip)
    flow3["flow_key"] = f"{src_ip}:60000-192.168.1.1:80"
    alert = mgr.generate_alert(_make_prediction(attack_type="DDoS", severity="high"), flow3)

    assert alert is not None
    assert alert["severity"] == "critical", (
        f"DDoS with 2+ prior alerts should escalate to critical, got {alert['severity']}"
    )
    assert alert["correlated"] is True
