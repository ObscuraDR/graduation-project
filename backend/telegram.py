import logging
import httpx
import asyncio
from typing import Dict
from backend.config import get_settings

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self):
        self.loop = None

    def set_event_loop(self, loop):
        self.loop = loop

    def dispatch_alert(self, alert: Dict):
        settings = get_settings()
        if not settings.enable_telegram_alerts or not settings.telegram_bot_token or not settings.telegram_chat_id:
            return

        message = (
            "🚨 *Z-SENTINEL ALERT*\n\n"
            f"🛡️ *Attack:* {alert.get('attack_type', 'Unknown')}\n"
            f"🔴 *Severity:* {alert.get('severity', 'unknown').upper()}\n"
            f"🌐 *Source IP:* `{alert.get('src_ip', 'N/A')}`\n"
            f"🎯 *Target IP:* `{alert.get('dst_ip', 'N/A')}`\n"
            f"🕒 *Time:* {alert.get('timestamp', 'N/A')}\n"
            f"📊 *Confidence:* {alert.get('confidence', 0)*100:.1f}%"
        )

        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self._send_telegram(message, settings.telegram_bot_token, settings.telegram_chat_id),
                self.loop
            )
        else:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._send_telegram(message, settings.telegram_bot_token, settings.telegram_chat_id))
            except RuntimeError:
                logger.warning("No event loop available for Telegram dispatch")

    async def _send_telegram(self, message: str, token: str, chat_id: str):
        api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
                response = await client.post(api_url, json=payload, timeout=10.0)
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

telegram_service = TelegramService()