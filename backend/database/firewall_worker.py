import asyncio
import logging
from backend.database.connection import SessionLocal
from backend.database.repository import BlacklistRepository
from backend.alert_engine.alert_manager import get_alert_manager

logger = logging.getLogger(__name__)


async def cleanup_expired_blacklist_task(interval_seconds: int = 60, batch_size: int = 100):
    """
    Background task định kỳ kiểm tra và gỡ chặn các IP đã hết hạn.
    Tối ưu hóa: Xử lý bất đồng bộ theo lô và batch update database.
    """
    logger.info("Firewall Cleanup Worker started (Interval: %ds)", interval_seconds)

    while True:
        try:
            db = SessionLocal()
            try:
                # 1. Lấy danh sách hết hạn
                expired_entries = BlacklistRepository.get_expired(db)
                if expired_entries:
                    for i in range(0, len(expired_entries), batch_size):
                        chunk = expired_entries[i : i + batch_size]
                        # Deactivate in DB first
                        expired_ips = [e.ip_address for e in chunk]
                        count = BlacklistRepository.batch_deactivate(db, expired_ips)
                        # Sync in-memory alert manager
                        alert_mgr = get_alert_manager()
                        for ip in expired_ips:
                            alert_mgr.remove_from_blacklist(ip)
                        logger.info("Expired block cleanup: deactivated %d/%d IPs", count, len(chunk))
            finally:
                db.close()

        except Exception as e:
            logger.error("Error in firewall cleanup worker: %s", e)

        # Chờ đợi cho lần quét tiếp theo
        await asyncio.sleep(interval_seconds)