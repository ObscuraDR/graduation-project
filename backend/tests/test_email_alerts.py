"""
Unit Tests – Email Alert Notification
======================================
All tests use mocking; no real SMTP connection is ever made.

Coverage
--------
  1.  should_send_email gate: disabled via ENABLE_EMAIL_ALERTS=false
  2.  should_send_email gate: severity too low (medium, low)
  3.  should_send_email gate: confidence below 0.85
  4.  should_send_email gate: passes for high + 0.85
  5.  should_send_email gate: passes for critical + 1.0
  6.  Email cooldown: second dispatch for same IP within window → suppressed
  7.  Email cooldown: after reset → dispatch allowed again
  8.  send_alert_email: SMTP called with correct args (mock aiosmtplib.send)
  9.  send_alert_email: SMTP failure returns False (no raise)
 10.  dispatch_alert_email: fire-and-forget task is created when gate passes
 11.  dispatch_alert_email: no task when gate fails
 12.  Multi-recipient: _recipients() splits SMTP_TO correctly
 13.  alert_manager.generate_alert dispatches email for high-severity alert
 14.  alert_manager.generate_alert does NOT dispatch email when enable_email=False
 15.  HTML body contains required alert fields
 16.  Plain-text body contains required alert fields
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.notifications.email import (
    EmailNotificationService,
    _EMAIL_MIN_CONFIDENCE,
    _EMAIL_SEVERITIES,
    _build_html,
    _build_plain,
    _recipients,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SAMPLE_ALERT: dict = {
    "alert_id": "test-uuid-1234",
    "attack_type": "DDoS",
    "severity": "critical",
    "confidence": 0.97,
    "src_ip": "10.0.0.1",
    "dst_ip": "192.168.1.1",
    "src_port": 54321,
    "dst_port": 80,
    "protocol": "TCP",
    "timestamp": "2026-05-19T10:00:00",
}

LOW_SEVERITY_ALERT: dict = {**SAMPLE_ALERT, "severity": "medium", "confidence": 0.90}
LOW_CONFIDENCE_ALERT: dict = {**SAMPLE_ALERT, "severity": "high", "confidence": 0.70}
HIGH_ALERT: dict = {**SAMPLE_ALERT, "severity": "high", "confidence": 0.85}


@pytest.fixture
def svc() -> EmailNotificationService:
    """Fresh EmailNotificationService with 60 s cooldown."""
    return EmailNotificationService(cooldown_seconds=60)


# ---------------------------------------------------------------------------
# Helper: run a coroutine in the test event loop
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ===========================================================================
# 1. Gate: ENABLE_EMAIL_ALERTS = false
# ===========================================================================

@pytest.mark.unit
def test_gate_disabled_by_flag(svc: EmailNotificationService) -> None:
    """When ENABLE_EMAIL_ALERTS is False the gate must return False."""
    with patch("backend.notifications.email.settings") as mock_settings:
        mock_settings.enable_email_alerts = False
        mock_settings.email_cooldown_seconds = 60

        assert svc.should_send_email(SAMPLE_ALERT) is False


# ===========================================================================
# 2. Gate: severity too low
# ===========================================================================

@pytest.mark.unit
@pytest.mark.parametrize("severity", ["low", "medium", "info"])
def test_gate_low_severity(svc: EmailNotificationService, severity: str) -> None:
    alert = {**SAMPLE_ALERT, "severity": severity}
    with patch("backend.notifications.email.settings") as mock_settings:
        mock_settings.enable_email_alerts = True
        mock_settings.email_cooldown_seconds = 60

        assert svc.should_send_email(alert) is False, f"Expected False for severity={severity}"


# ===========================================================================
# 3. Gate: confidence below threshold
# ===========================================================================

@pytest.mark.unit
def test_gate_low_confidence(svc: EmailNotificationService) -> None:
    with patch("backend.notifications.email.settings") as mock_settings:
        mock_settings.enable_email_alerts = True
        mock_settings.email_cooldown_seconds = 60

        assert svc.should_send_email(LOW_CONFIDENCE_ALERT) is False


# ===========================================================================
# 4. Gate: high severity + confidence 0.85 → passes
# ===========================================================================

@pytest.mark.unit
def test_gate_passes_high_severity(svc: EmailNotificationService) -> None:
    with patch("backend.notifications.email.settings") as mock_settings:
        mock_settings.enable_email_alerts = True
        mock_settings.email_cooldown_seconds = 60

        assert svc.should_send_email(HIGH_ALERT) is True


# ===========================================================================
# 5. Gate: critical severity + confidence 1.0 → passes
# ===========================================================================

@pytest.mark.unit
def test_gate_passes_critical_severity(svc: EmailNotificationService) -> None:
    with patch("backend.notifications.email.settings") as mock_settings:
        mock_settings.enable_email_alerts = True
        mock_settings.email_cooldown_seconds = 60

        assert svc.should_send_email(SAMPLE_ALERT) is True


# ===========================================================================
# 6. Cooldown: second dispatch for same IP suppressed
# ===========================================================================

@pytest.mark.unit
def test_email_cooldown_suppresses_second(svc: EmailNotificationService) -> None:
    src_ip = SAMPLE_ALERT["src_ip"]
    with patch("backend.notifications.email.settings") as mock_settings:
        mock_settings.enable_email_alerts = True
        mock_settings.email_cooldown_seconds = 60

        assert svc.should_send_email(SAMPLE_ALERT) is True
        svc._record_email_sent(src_ip)  # simulate first send

        # Second call within cooldown window → suppressed
        assert svc.should_send_email(SAMPLE_ALERT) is False


# ===========================================================================
# 7. Cooldown: after reset → dispatch allowed again
# ===========================================================================

@pytest.mark.unit
def test_email_cooldown_reset(svc: EmailNotificationService) -> None:
    src_ip = SAMPLE_ALERT["src_ip"]
    with patch("backend.notifications.email.settings") as mock_settings:
        mock_settings.enable_email_alerts = True
        mock_settings.email_cooldown_seconds = 60

        svc._record_email_sent(src_ip)
        assert svc.should_send_email(SAMPLE_ALERT) is False  # in cooldown

        svc.reset_cooldown(src_ip)
        assert svc.should_send_email(SAMPLE_ALERT) is True   # cooldown cleared


# ===========================================================================
# 8. send_alert_email: SMTP called with correct args
# ===========================================================================

@pytest.mark.unit
def test_send_alert_email_calls_smtp(svc: EmailNotificationService) -> None:
    """aiosmtplib.send must be called exactly once with correct host/port."""
    with (
        patch("backend.notifications.email.settings") as mock_settings,
        patch("backend.notifications.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send,
    ):
        mock_settings.enable_email_alerts = True
        mock_settings.email_cooldown_seconds = 60
        mock_settings.smtp_host = "smtp.example.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_user = "user@example.com"
        mock_settings.smtp_password = "secret"
        mock_settings.smtp_from = "IDS <ids@example.com>"
        mock_settings.smtp_to = "soc@example.com"

        result = _run(svc.send_alert_email(SAMPLE_ALERT))

    assert result is True
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["hostname"] == "smtp.example.com"
    assert call_kwargs["port"] == 587
    assert call_kwargs["start_tls"] is True


# ===========================================================================
# 9. send_alert_email: SMTP failure returns False (no raise)
# ===========================================================================

@pytest.mark.unit
def test_send_alert_email_smtp_failure(svc: EmailNotificationService) -> None:
    """SMTP exceptions must be caught; send_alert_email returns False."""
    with (
        patch("backend.notifications.email.settings") as mock_settings,
        patch(
            "backend.notifications.email.aiosmtplib.send",
            new_callable=AsyncMock,
            side_effect=ConnectionRefusedError("SMTP down"),
        ),
    ):
        mock_settings.enable_email_alerts = True
        mock_settings.email_cooldown_seconds = 60
        mock_settings.smtp_host = "smtp.example.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_user = "u"
        mock_settings.smtp_password = "p"
        mock_settings.smtp_from = "IDS <ids@example.com>"
        mock_settings.smtp_to = "soc@example.com"

        result = _run(svc.send_alert_email(SAMPLE_ALERT))

    assert result is False


# ===========================================================================
# 10. dispatch_alert_email: asyncio task created when gate passes
# ===========================================================================

@pytest.mark.unit
def test_dispatch_creates_task_when_gate_passes(svc: EmailNotificationService) -> None:
    """dispatch_alert_email must schedule an asyncio Task for qualifying alerts."""
    with (
        patch("backend.notifications.email.settings") as mock_settings,
        patch.object(svc, "send_alert_email", new_callable=AsyncMock) as mock_send,
    ):
        mock_settings.enable_email_alerts = True
        mock_settings.email_cooldown_seconds = 60

        async def _run_dispatch():
            svc.dispatch_alert_email(SAMPLE_ALERT)
            # Yield control so the fire-and-forget task can execute
            await asyncio.sleep(0)

        asyncio.get_event_loop().run_until_complete(_run_dispatch())

    mock_send.assert_called_once_with(SAMPLE_ALERT)


# ===========================================================================
# 11. dispatch_alert_email: no task when gate fails
# ===========================================================================

@pytest.mark.unit
def test_dispatch_no_task_when_gate_fails(svc: EmailNotificationService) -> None:
    """dispatch_alert_email must be a no-op when the gate rejects the alert."""
    with (
        patch("backend.notifications.email.settings") as mock_settings,
        patch.object(svc, "send_alert_email", new_callable=AsyncMock) as mock_send,
    ):
        mock_settings.enable_email_alerts = False
        mock_settings.email_cooldown_seconds = 60

        async def _run_dispatch():
            svc.dispatch_alert_email(SAMPLE_ALERT)
            await asyncio.sleep(0)

        asyncio.get_event_loop().run_until_complete(_run_dispatch())

    mock_send.assert_not_called()


# ===========================================================================
# 12. Multi-recipient: _recipients() splits SMTP_TO
# ===========================================================================

@pytest.mark.unit
def test_recipients_splits_comma_list() -> None:
    with patch("backend.notifications.email.settings") as mock_settings:
        mock_settings.smtp_to = "a@example.com , b@example.com,  c@example.com  "
        result = _recipients()

    assert result == ["a@example.com", "b@example.com", "c@example.com"]


@pytest.mark.unit
def test_recipients_single_address() -> None:
    with patch("backend.notifications.email.settings") as mock_settings:
        mock_settings.smtp_to = "soc@corp.com"
        result = _recipients()

    assert result == ["soc@corp.com"]


# ===========================================================================
# 13. alert_manager.generate_alert dispatches email for high-severity alert
# ===========================================================================

@pytest.mark.unit
def test_alert_manager_dispatches_email(alert_manager) -> None:
    """
    AlertManager with enable_email=True (default) must call
    email_service.dispatch_alert_email for a qualifying alert.
    """
    from backend.alert_engine.alert_manager import AlertManager

    mgr = AlertManager(
        confidence_threshold=0.75,
        alert_cooldown=30,
        enable_db_save=False,
        enable_websocket=False,
        enable_email=True,
    )

    prediction = {
        "attack_type": "DDoS",
        "confidence": 0.95,
        "severity": "critical",
        "model_name": "ensemble",
        "model_version": "1.0",
        "features": {},
        "all_probabilities": {},
    }
    flow_info = {
        "src_ip": "10.1.2.3",
        "dst_ip": "192.168.0.1",
        "src_port": 12345,
        "dst_port": 443,
        "protocol": "TCP",
        "flow_key": "10.1.2.3:12345-192.168.0.1:443",
    }

    with patch("backend.alert_engine.alert_manager.email_service") as mock_email:
        alert = mgr.generate_alert(prediction, flow_info)

    assert alert is not None
    mock_email.dispatch_alert_email.assert_called_once_with(alert)


# ===========================================================================
# 14. alert_manager does NOT dispatch email when enable_email=False
# ===========================================================================

@pytest.mark.unit
def test_alert_manager_no_email_when_disabled(alert_manager_no_email) -> None:
    prediction = {
        "attack_type": "PortScan",
        "confidence": 0.92,
        "severity": "high",
        "model_name": "ensemble",
        "model_version": "1.0",
        "features": {},
        "all_probabilities": {},
    }
    flow_info = {
        "src_ip": "10.9.8.7",
        "dst_ip": "172.16.0.1",
        "src_port": 9999,
        "dst_port": 22,
        "protocol": "TCP",
        "flow_key": "10.9.8.7:9999-172.16.0.1:22",
    }

    with patch("backend.alert_engine.alert_manager.email_service") as mock_email:
        alert = alert_manager_no_email.generate_alert(prediction, flow_info)

    assert alert is not None
    mock_email.dispatch_alert_email.assert_not_called()


# ===========================================================================
# 15. HTML body contains required fields
# ===========================================================================

@pytest.mark.unit
def test_html_body_contains_required_fields() -> None:
    html = _build_html(SAMPLE_ALERT)

    for field in (
        SAMPLE_ALERT["alert_id"],
        SAMPLE_ALERT["attack_type"],
        SAMPLE_ALERT["src_ip"],
        SAMPLE_ALERT["dst_ip"],
        str(SAMPLE_ALERT["src_port"]),
        str(SAMPLE_ALERT["dst_port"]),
        SAMPLE_ALERT["protocol"],
        SAMPLE_ALERT["timestamp"],
        "CRITICAL",          # severity uppercased
        "97.00%",            # confidence formatted
    ):
        assert field in html, f"Expected field not found in HTML body: {field!r}"


# ===========================================================================
# 16. Plain-text body contains required fields
# ===========================================================================

@pytest.mark.unit
def test_plain_body_contains_required_fields() -> None:
    plain = _build_plain(SAMPLE_ALERT)

    for field in (
        SAMPLE_ALERT["alert_id"],
        SAMPLE_ALERT["attack_type"],
        SAMPLE_ALERT["src_ip"],
        SAMPLE_ALERT["dst_ip"],
        str(SAMPLE_ALERT["src_port"]),
        str(SAMPLE_ALERT["dst_port"]),
        SAMPLE_ALERT["protocol"],
        SAMPLE_ALERT["timestamp"],
        "CRITICAL",
        "97.00%",
    ):
        assert field in plain, f"Expected field not found in plain-text body: {field!r}"
