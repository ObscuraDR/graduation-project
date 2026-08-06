from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database.connection import get_db
from backend.database.repository import SettingRepository
from pydantic import BaseModel

router = APIRouter(prefix="/api/settings", tags=["settings"])


class NotificationSettingsSchema(BaseModel):
    # Email
    email_enabled: bool = False
    smtp_to: str = ""
    # Telegram
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # Discord
    discord_enabled: bool = False
    discord_webhook_url: str = ""


_DEFAULT_SETTINGS = {
    "email_enabled": False,
    "smtp_to": "",
    "telegram_enabled": False,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "discord_enabled": False,
    "discord_webhook_url": "",
}


@router.get("/notifications")
def get_notification_settings(db: Session = Depends(get_db)):
    return SettingRepository.get_value(db, "notifications", _DEFAULT_SETTINGS)


@router.post("/notifications")
def update_notification_settings(
    data: NotificationSettingsSchema,
    db: Session = Depends(get_db),
):
    SettingRepository.update_value(db, "notifications", data.model_dump())

    from backend.alert_engine.alert_manager import get_alert_manager
    from backend.config import settings as app_settings

    am = get_alert_manager()
    am.enable_email = data.email_enabled
    am.enable_telegram = data.telegram_enabled
    am.enable_discord = data.discord_enabled

    # Cập nhật smtp_to trong runtime settings (không cần restart)
    if data.smtp_to:
        app_settings.smtp_to = data.smtp_to
    app_settings.enable_email_alerts = data.email_enabled

    return {"status": "success", "message": "Cấu hình đã được lưu"}
