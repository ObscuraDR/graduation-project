"""
Email Notification Service
===========================
Sends alert emails over SMTP (via aiosmtplib) with:

  - Severity / confidence gating  (high|critical AND >= 0.85)
  - Per-attacker-IP cooldown       (default: settings.email_cooldown_seconds)
  - Non-blocking dispatch          (asyncio.create_task – never blocks packet thread)
  - Multi-recipient support        (SMTP_TO is comma-separated)
  - Feature-flag guard             (ENABLE_EMAIL_ALERTS=true|false)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional

import aiosmtplib

from backend.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants – severity / confidence gate
# ---------------------------------------------------------------------------
_EMAIL_SEVERITIES: frozenset[str] = frozenset({"high", "critical"})
_EMAIL_MIN_CONFIDENCE: float = 0.85


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _recipients() -> List[str]:
    """Parse SMTP_TO (comma-separated) into a cleaned list of addresses."""
    return [addr.strip() for addr in settings.smtp_to.split(",") if addr.strip()]


def _severity_color(severity: str) -> str:
    return {"critical": "#c0392b", "high": "#e67e22"}.get(severity.lower(), "#7f8c8d")


def _build_plain(alert: dict) -> str:
    protocol = alert.get("protocol") or "N/A"
    return (
        f"IDS Security Alert\n"
        f"==================\n\n"
        f"Alert ID    : {alert.get('alert_id', 'N/A')}\n"
        f"Severity    : {alert.get('severity', '?').upper()}\n"
        f"Attack Type : {alert.get('attack_type', '?')}\n"
        f"Confidence  : {alert.get('confidence', 0):.2%}\n\n"
        f"Source IP   : {alert.get('src_ip', 'N/A')}\n"
        f"Dest IP     : {alert.get('dst_ip', 'N/A')}\n"
        f"Source Port : {alert.get('src_port', 'N/A')}\n"
        f"Dest Port   : {alert.get('dst_port', 'N/A')}\n"
        f"Protocol    : {protocol}\n\n"
        f"Timestamp   : {alert.get('timestamp', 'N/A')}\n\n"
        f"Summary     : A {alert.get('severity', '?').upper()} severity "
        f"{alert.get('attack_type', '?')} attack was detected from "
        f"{alert.get('src_ip', 'N/A')} with {alert.get('confidence', 0):.2%} "
        f"confidence. Immediate investigation is recommended.\n\n"
        f"---\nZ-Sentinel IDS\n"
    )


def _build_html(alert: dict) -> str:
    sev = alert.get("severity", "unknown")
    color = _severity_color(sev)
    protocol = alert.get("protocol") or "N/A"
    confidence_pct = f"{alert.get('confidence', 0):.2%}"

    def row(label: str, value) -> str:
        return (
            f"<tr>"
            f'<td style="padding:8px 12px;background:#f8f9fa;border:1px solid #dee2e6;'
            f'font-weight:bold;width:160px">{label}</td>'
            f'<td style="padding:8px 12px;border:1px solid #dee2e6">{value}</td>'
            f"</tr>"
        )

    rows = "".join([
        row("Alert ID",     alert.get("alert_id", "N/A")),
        row("Severity",     f'<span style="color:{color};font-weight:bold">{sev.upper()}</span>'),
        row("Attack Type",  alert.get("attack_type", "N/A")),
        row("Confidence",   confidence_pct),
        row("Source IP",    alert.get("src_ip", "N/A")),
        row("Dest IP",      alert.get("dst_ip", "N/A")),
        row("Source Port",  alert.get("src_port", "N/A")),
        row("Dest Port",    alert.get("dst_port", "N/A")),
        row("Protocol",     protocol),
        row("Timestamp",    alert.get("timestamp", "N/A")),
    ])

    summary = (
        f"A <strong style='color:{color}'>{sev.upper()}</strong> severity "
        f"<strong>{alert.get('attack_type', '?')}</strong> attack was detected from "
        f"<code>{alert.get('src_ip', 'N/A')}</code> with "
        f"<strong>{confidence_pct}</strong> confidence. "
        f"Immediate investigation is recommended."
    )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,Helvetica,sans-serif;margin:0;padding:0;background:#f0f2f5">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="max-width:640px;margin:32px auto;background:#ffffff;
                border-radius:8px;overflow:hidden;
                box-shadow:0 2px 12px rgba(0,0,0,0.12)">
    <!-- Header -->
    <tr>
      <td style="background:{color};padding:24px 28px">
        <h1 style="color:#fff;margin:0;font-size:20px;letter-spacing:.5px">
          &#9888; Z-Sentinel IDS &mdash; Security Alert
        </h1>
      </td>
    </tr>
    <!-- Body -->
    <tr>
      <td style="padding:24px 28px">
        <p style="margin:0 0 16px;font-size:14px;color:#555">{summary}</p>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse;font-size:13px">
          {rows}
        </table>
      </td>
    </tr>
    <!-- Footer -->
    <tr>
      <td style="padding:16px 28px;background:#f8f9fa;
                 border-top:1px solid #dee2e6;
                 font-size:11px;color:#888;text-align:center">
        Z-Sentinel Intrusion Detection System &bull; Auto-generated alert
      </td>
    </tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# EmailNotificationService
# ---------------------------------------------------------------------------

class EmailNotificationService:
    """
    Async email alert service.

    Thread-safety note
    ------------------
    ``dispatch_alert_email`` schedules an asyncio.Task from within the
    *event-loop thread*.  Call it from async context only (e.g. inside the
    broadcast bridge consumer).  ``AlertManager.generate_alert`` runs on the
    sniffer thread and must use the bridge queue — never call this directly
    from that thread.
    """

    def __init__(self, cooldown_seconds: Optional[int] = None):
        self._cooldown_seconds: int = (
            cooldown_seconds
            if cooldown_seconds is not None
            else settings.email_cooldown_seconds
        )
        # ip → datetime of last email sent
        self._email_history: Dict[str, datetime] = {}
        # Main event loop reference (set qua set_event_loop() từ lifespan)
        self._loop = None

    # ------------------------------------------------------------------
    # Cooldown helpers
    # ------------------------------------------------------------------

    def _is_email_in_cooldown(self, src_ip: str) -> bool:
        """Return True if an email was already sent for *src_ip* within the cooldown window."""
        if src_ip not in self._email_history:
            return False
        cutoff = self._email_history[src_ip] + timedelta(seconds=self._cooldown_seconds)
        return datetime.now(timezone.utc) < cutoff

    def _record_email_sent(self, src_ip: str) -> None:
        self._email_history[src_ip] = datetime.now(timezone.utc)

    def reset_cooldown(self, src_ip: Optional[str] = None) -> None:
        """Clear cooldown state (useful in tests)."""
        if src_ip:
            self._email_history.pop(src_ip, None)
        else:
            self._email_history.clear()

    # ------------------------------------------------------------------
    # Gate check
    # ------------------------------------------------------------------

    def should_send_email(self, alert: dict) -> bool:
        """
        Return True only when ALL conditions are met:
          1. ENABLE_EMAIL_ALERTS is true
          2. severity in {high, critical}
          3. confidence >= 0.85
          4. src_ip not in email cooldown
        """
        if not settings.enable_email_alerts:
            return False
        if alert.get("severity", "").lower() not in _EMAIL_SEVERITIES:
            return False
        if alert.get("confidence", 0.0) < _EMAIL_MIN_CONFIDENCE:
            return False
        src_ip = alert.get("src_ip", "")
        if self._is_email_in_cooldown(src_ip):
            logger.debug("Email suppressed (cooldown) for IP %s", src_ip)
            return False
        return True

    # ------------------------------------------------------------------
    # Low-level send
    # ------------------------------------------------------------------

    async def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        html: Optional[str] = None,
    ) -> bool:
        """
        Send a single email to one or more *to* addresses.

        Returns True on success, False on any SMTP error.
        """
        if not to:
            logger.warning("send_email called with empty recipient list – skipping")
            return False

        try:
            message = MIMEMultipart("alternative")
            message["From"] = settings.smtp_from
            message["To"] = ", ".join(to)
            message["Subject"] = subject

            message.attach(MIMEText(body, "plain"))
            if html:
                message.attach(MIMEText(html, "html"))

            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.smtp_password,
                start_tls=True,
            )
            logger.info("Email sent to %s | subject: %s", to, subject)
            return True

        except Exception as exc:
            logger.error("Failed to send email to %s: %s", to, exc)
            return False

    # ------------------------------------------------------------------
    # Alert-specific send
    # ------------------------------------------------------------------

    async def send_alert_email(self, alert: dict) -> bool:
        """Build and send a formatted alert email for *alert*."""
        sev = alert.get("severity", "unknown").upper()
        attack = alert.get("attack_type", "Unknown")
        subject = f"[IDS Alert] {sev}: {attack} detected from {alert.get('src_ip', '?')}"

        return await self.send_email(
            to=_recipients(),
            subject=subject,
            body=_build_plain(alert),
            html=_build_html(alert),
        )

    # ------------------------------------------------------------------
    # Non-blocking dispatch (call from async context)
    # ------------------------------------------------------------------

    def dispatch_alert_email(self, alert: dict) -> None:
        """
        Gate-check then fire-and-forget an alert email as an asyncio Task.

        This is the **only** method callers should use from inside the
        broadcast-bridge consumer coroutine.  It never raises.

        Thread/loop safety:
        - Khi gọi từ trong async context (event loop đang chạy) → tạo task ngay.
        - Khi gọi từ sync context / thread khác (không có running loop) →
          dùng loop reference đã lưu (nếu có) qua call_soon_threadsafe,
          hoặc log warning nếu không có loop nào.
        """
        if not self.should_send_email(alert):
            return

        src_ip = alert.get("src_ip", "")
        self._record_email_sent(src_ip)  # record *before* task fires to prevent bursts

        async def _send() -> None:
            success = await self.send_alert_email(alert)
            if not success:
                # Roll back cooldown so it can retry on the next event
                self._email_history.pop(src_ip, None)

        # Trường hợp 1: đang ở trong running event loop (async context)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_send())
            return
        except RuntimeError:
            pass  # Không có running loop trong thread hiện tại

        # Trường hợp 2: có loop reference đã lưu (set qua set_event_loop)
        if self._loop is not None and not self._loop.is_closed():
            try:
                self._loop.call_soon_threadsafe(lambda: self._loop.create_task(_send()))
                return
            except RuntimeError:
                pass

        # Trường hợp 3: không có loop nào → rollback cooldown, log warning
        self._email_history.pop(src_ip, None)
        logger.warning("No event loop available; email not dispatched for %s", src_ip)

    def set_event_loop(self, loop) -> None:
        """
        Lưu reference đến main event loop để dispatch email an toàn từ
        thread khác (ví dụ sniffer thread). Gọi từ FastAPI lifespan startup.
        """
        self._loop = loop
        logger.info("Email service event loop reference set")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
email_service = EmailNotificationService()
