import logging
import httpx
import asyncio
from typing import Dict
from backend.config import get_settings

logger = logging.getLogger(__name__)

class DiscordService:
    def __init__(self):
        self.loop = None

    def set_event_loop(self, loop):
        self.loop = loop

    def dispatch_alert(self, alert: Dict):
        settings = get_settings()
        if not settings.enable_discord_alerts or not settings.discord_webhook_url:
            return

        severity = alert.get('severity', 'low')
        color = 15158332 if severity == 'critical' else 15105570  # Red or Orange

        payload = {
            "embeds": [{
                "title": "🛡️ Z-Sentinel Intrusion Detected",
                "description": f"An attack of type **{alert.get('attack_type', 'Unknown')}** has been detected.",
                "color": color,
                "fields": [
                    {"name": "Source IP", "value": alert.get('src_ip', 'N/A'), "inline": True},
                    {"name": "Severity", "value": severity.upper(), "inline": True},
                    {"name": "Target Port", "value": str(alert.get('dst_port', 'N/A')), "inline": True},
                    {"name": "Confidence", "value": f"{alert.get('confidence', 0)*100:.1f}%", "inline": True}
                ],
                "footer": {"text": "Z-Sentinel IDS Engine"},
                "timestamp": alert.get('timestamp', '')
            }]
        }

        webhook_url = settings.discord_webhook_url
        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._send_discord(payload, webhook_url), self.loop)
        else:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._send_discord(payload, webhook_url))
            except RuntimeError:
                logger.warning("No event loop available for Discord dispatch")

    async def _send_discord(self, payload: Dict, webhook_url: str):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload, timeout=10.0)
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")

discord_service = DiscordService()