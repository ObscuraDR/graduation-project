import logging
import httpx
import asyncio
from typing import Dict
from backend.config import settings

logger = logging.getLogger(__name__)

class DiscordService:
    def __init__(self):
        self.enabled = settings.enable_discord_alerts
        self.webhook_url = settings.discord_webhook_url
        self.loop = None

    def set_event_loop(self, loop):
        self.loop = loop

    def dispatch_alert(self, alert: Dict):
        if not self.enabled or not self.webhook_url:
            return

        color = 15158332 if alert['severity'] == 'critical' else 15105570 # Red or Orange
        
        payload = {
            "embeds": [{
                "title": "🛡️ Z-Sentinel Intrusion Detected",
                "description": f"An attack of type **{alert['attack_type']}** has been detected.",
                "color": color,
                "fields": [
                    {"name": "Source IP", "value": alert['src_ip'], "inline": True},
                    {"name": "Severity", "value": alert['severity'].upper(), "inline": True},
                    {"name": "Target Port", "value": str(alert['dst_port']), "inline": True},
                    {"name": "Confidence", "value": f"{alert['confidence']*100:.1f}%", "inline": True}
                ],
                "footer": {"text": "Z-Sentinel IDS Engine"},
                "timestamp": alert['timestamp']
            }]
        }

        if self.loop:
            asyncio.run_coroutine_threadsafe(self._send_discord(payload), self.loop)

    async def _send_discord(self, payload: Dict):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload, timeout=10.0)
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")

discord_service = DiscordService()