from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.connection import get_db
from backend.database.repository import SettingRepository
from pydantic import BaseModel

router = APIRouter(prefix="/api/settings", tags=["settings"])

class NotificationSettingsSchema(BaseModel):
    telegram_enabled: bool
    telegram_bot_token: str
    telegram_chat_id: str
    discord_enabled: bool
    discord_webhook_url: str

@router.get("/notifications")
def get_notification_settings(db: Session = Depends(get_db)):
    return SettingRepository.get_value(db, "notifications", {
        "telegram_enabled": False,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "discord_enabled": False,
        "discord_webhook_url": ""
    })

@router.post("/notifications")
def update_notification_settings(data: NotificationSettingsSchema, db: Session = Depends(get_db)):
    SettingRepository.update_value(db, "notifications", data.model_dump())
    
    # Thông báo cho AlertManager cập nhật lại cấu hình runtime (tùy chọn)
    from backend.alert_engine.alert_manager import get_alert_manager
    am = get_alert_manager()
    am.enable_telegram = data.telegram_enabled
    am.enable_discord = data.discord_enabled
    
    return {"status": "success", "message": "Cấu hình đã được lưu"}