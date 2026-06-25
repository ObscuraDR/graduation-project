import asyncio
import logging
from datetime import datetime, timedelta, timezone
from backend.database.connection import SessionLocal
from backend.database.models import AuditLog
from backend.api.user_behavior_detector import UserBehaviorDetector

logger = logging.getLogger(__name__)

async def ueba_detection_task(interval_seconds: int = 60):
    """
    Background task định kỳ chạy phân tích hành vi người dùng.
    """
    logger.info("UEBA Detection Worker started (Interval: %ds)", interval_seconds)
    
    while True:
        try:
            db = SessionLocal()
            try:
                detector = UserBehaviorDetector(db)
                
                # Tìm các người dùng có hoạt động trong 10 phút gần đây
                recent_time = datetime.now(timezone.utc) - timedelta(minutes=10)
                active_users = db.query(AuditLog.username).filter(
                    AuditLog.created_at >= recent_time
                ).distinct().all()
                
                for (username,) in active_users:
                    # Bỏ qua các tác vụ hệ thống tự động
                    if username == "system":
                        continue
                    
                    detector.check_velocity_attack(username)
            finally:
                db.close()
                
        except Exception as e:
            logger.error("Error in UEBA worker: %s", e)
        
        await asyncio.sleep(interval_seconds)