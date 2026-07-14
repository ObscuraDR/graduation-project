from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from backend.database.connection import get_db
from backend.database.repository import SettingRepository
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/api/settings", tags=["settings"])


class NotificationSettingsSchema(BaseModel):
    # Email
    email_enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: str = ""
    email_cooldown_seconds: int = 60
    # Telegram
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # Discord
    discord_enabled: bool = False
    discord_webhook_url: str = ""


@router.get("/notifications")
def get_notification_settings(db: Session = Depends(get_db)):
    from backend.config import settings as app_settings
    defaults = {
        # Email — lấy từ .env làm giá trị mặc định
        "email_enabled": app_settings.enable_email_alerts,
        "smtp_host": app_settings.smtp_host,
        "smtp_port": app_settings.smtp_port,
        "smtp_user": app_settings.smtp_user,
        "smtp_password": "",  # Không trả password ra ngoài
        "smtp_from": app_settings.smtp_from,
        "smtp_to": app_settings.smtp_to,
        "email_cooldown_seconds": app_settings.email_cooldown_seconds,
        # Telegram
        "telegram_enabled": False,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        # Discord
        "discord_enabled": False,
        "discord_webhook_url": "",
    }
    saved = SettingRepository.get_value(db, "notifications", {})
    # Merge: saved override defaults, nhưng không trả password nếu rỗng
    merged = {**defaults, **saved}
    # Ẩn password — trả về placeholder nếu đã set
    if saved.get("smtp_password"):
        merged["smtp_password"] = "••••••••"
    return merged


@router.post("/notifications")
def update_notification_settings(
    data: NotificationSettingsSchema,
    db: Session = Depends(get_db)
):
    from backend.config import settings as app_settings
    from backend.notifications.email import email_service
    from backend.alert_engine.alert_manager import get_alert_manager

    # Lưu vào DB — nhưng nếu password là placeholder thì giữ nguyên cũ
    payload = data.model_dump()
    existing = SettingRepository.get_value(db, "notifications", {})
    if payload.get("smtp_password") == "••••••••":
        payload["smtp_password"] = existing.get("smtp_password", "")

    SettingRepository.update_value(db, "notifications", payload)

    # Áp dụng email config vào runtime settings
    app_settings.enable_email_alerts = data.email_enabled
    app_settings.smtp_host = data.smtp_host
    app_settings.smtp_port = data.smtp_port
    app_settings.smtp_user = data.smtp_user
    if payload.get("smtp_password"):
        app_settings.smtp_password = payload["smtp_password"]
    app_settings.smtp_from = data.smtp_from or data.smtp_user
    app_settings.smtp_to = data.smtp_to
    app_settings.email_cooldown_seconds = data.email_cooldown_seconds

    # Reset email cooldown để áp dụng cấu hình mới ngay
    email_service._cooldown_seconds = data.email_cooldown_seconds
    email_service.reset_cooldown()

    # Áp dụng Telegram / Discord
    am = get_alert_manager()
    am.enable_telegram = data.telegram_enabled
    am.enable_discord = data.discord_enabled
    am.enable_email = data.email_enabled

    return {"status": "success", "message": "Cấu hình thông báo đã được lưu"}


@router.post("/notifications/test-email")
async def test_email(db: Session = Depends(get_db)):
    """Gửi email test để kiểm tra cấu hình SMTP."""
    from backend.config import settings as app_settings
    from backend.notifications.email import email_service

    if not app_settings.enable_email_alerts:
        raise HTTPException(status_code=400, detail="Email alerts chưa được bật")

    recipients = [addr.strip() for addr in app_settings.smtp_to.split(",") if addr.strip()]
    if not recipients:
        raise HTTPException(status_code=400, detail="Chưa cấu hình địa chỉ nhận email (SMTP_TO)")

    success = await email_service.send_email(
        to=recipients,
        subject="[Z-Sentinel] Test Email — Cấu hình thành công",
        body="Đây là email kiểm tra từ Z-Sentinel IDS.\nNếu bạn nhận được email này, cấu hình SMTP đã hoạt động đúng.",
        html="""
        <div style="font-family:Arial,sans-serif;max-width:480px;margin:32px auto;
                    background:#f8f9fa;border-radius:8px;padding:28px;
                    border:1px solid #dee2e6">
          <h2 style="color:#2d6cdf;margin-top:0">✅ Z-Sentinel IDS — Test Email</h2>
          <p>Đây là email kiểm tra.</p>
          <p>Nếu bạn nhận được email này, cấu hình SMTP đã hoạt động đúng.</p>
          <hr style="border:none;border-top:1px solid #dee2e6;margin:20px 0">
          <p style="color:#888;font-size:12px;margin:0">Z-Sentinel IDS &bull; Auto-generated test</p>
        </div>
        """,
    )

    if success:
        return {"status": "success", "message": f"Email test đã gửi đến {', '.join(recipients)}"}
    else:
        raise HTTPException(status_code=500, detail="Gửi email thất bại — kiểm tra lại cấu hình SMTP")
