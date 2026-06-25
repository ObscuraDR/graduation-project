import asyncio
import logging
from datetime import datetime, timedelta, timezone
from backend.database.connection import SessionLocal
from backend.database.repository import ServerRepository
from backend.config import settings

logger = logging.getLogger(__name__)

async def check_server_status_task():
    """
    Background task định kỳ kiểm tra trạng thái của các máy chủ.
    """
    logger.info("Server Status Checker Worker started.")
    
    while True:
        try:
            db = SessionLocal()
            try:
                servers = ServerRepository.get_all_servers(db)
                
                for server in servers:
                    # last_seen có thể là naive datetime từ DB — chuẩn hóa
                    last_seen = server.last_seen
                    if last_seen.tzinfo is None:
                        last_seen = last_seen.replace(tzinfo=timezone.utc)
                    time_since_last_seen = datetime.now(timezone.utc) - last_seen
                    
                    if time_since_last_seen.total_seconds() > settings.server_offline_threshold_seconds:
                        if server.status != "offline":
                            ServerRepository.update_server_status(db, server.id, "offline")
                    elif server.status == "offline":
                        ServerRepository.update_server_status(db, server.id, "online")
            finally:
                db.close()
        except Exception as e:
            logger.error("Error in server status checker worker: %s", e)
        
        await asyncio.sleep(settings.server_status_check_interval_seconds)