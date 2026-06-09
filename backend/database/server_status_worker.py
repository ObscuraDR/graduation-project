import asyncio
import logging
from datetime import datetime, timedelta
from backend.database.connection import SessionLocal
from backend.database.repository import ServerRepository
from backend.config import settings

logger = logging.getLogger(__name__)

async def check_server_status_task():
    """
    Background task định kỳ kiểm tra trạng thái của các máy chủ.
    Nếu một máy chủ không gửi heartbeat trong khoảng thời gian quy định,
    nó sẽ được đánh dấu là 'offline'.
    """
    logger.info("Server Status Checker Worker started.")
    
    while True:
        try:
            db = SessionLocal()
            try:
                servers = ServerRepository.get_all_servers(db)
                
                for server in servers:
                    # Tính toán thời gian kể từ lần cuối Agent gửi heartbeat
                    time_since_last_seen = datetime.utcnow() - server.last_seen
                    
                    if time_since_last_seen.total_seconds() > settings.server_offline_threshold_seconds:
                        # Nếu vượt quá ngưỡng, đánh dấu là offline
                        if server.status != "offline":
                            ServerRepository.update_server_status(db, server.id, "offline")
                    elif server.status == "offline":
                        # Nếu đang offline nhưng lại nhận được heartbeat (last_seen mới hơn), chuyển về online
                        # (Endpoint update_server_status đã tự động cập nhật last_seen)
                        ServerRepository.update_server_status(db, server.id, "online")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error in server status checker worker: {e}")
        
        # Chờ đợi cho lần quét tiếp theo
        await asyncio.sleep(settings.server_status_check_interval_seconds)