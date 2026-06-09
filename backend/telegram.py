import logging
import httpx
import asyncio
from typing import Dict
from backend.config import settings

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self):
        self.enabled = settings.enable_telegram_alerts
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        self.loop = None

    def set_event_loop(self, loop):
        self.loop = loop

    def dispatch_alert(self, alert: Dict):
        if not self.enabled or not self.token or not self.chat_id:
            return

        message = (
            "🚨 *Z-SENTINEL ALERT*\n\n"
            f"🛡️ *Attack:* {alert['attack_type']}\n"
            f"🔴 *Severity:* {alert['severity'].upper()}\n"
            f"🌐 *Source IP:* `{alert['src_ip']}`\n"
            f"🎯 *Target IP:* `{alert['dst_ip']}`\n"
            f"🕒 *Time:* {alert['timestamp']}\n"
            f"📊 *Confidence:* {alert['confidence']*100:.1f}%"
        )

        if self.loop:
            asyncio.run_coroutine_threadsafe(self._send_telegram(message), self.loop)

    async def _send_telegram(self, message: str):
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
                response = await client.post(self.api_url, json=payload, timeout=10.0)
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

telegram_service = TelegramService()