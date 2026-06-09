import asyncio
import logging
from datetime import datetime
from backend.database.connection import SessionLocal
from backend.database.repository import BlacklistRepository
from backend.scripts.firewall_manager import FirewallManager

logger = logging.getLogger(__name__)

async def cleanup_expired_blacklist_task(interval_seconds: int = 60, batch_size: int = 100):
    """
    Background task định kỳ kiểm tra và gỡ chặn các IP đã hết hạn.
    Tối ưu hóa: Xử lý bất đồng bộ theo lô và batch update database.
    """
    fw_manager = FirewallManager()
    semaphore = asyncio.Semaphore(10)  # Giới hạn tối đa 10 tiến trình OS chạy cùng lúc
    logger.info(f"Firewall Cleanup Worker started (Interval: {interval_seconds}s)")
    
    while True:
        try:
            with SessionLocal() as db:
                # 1. Lấy danh sách hết hạn
                expired_entries = BlacklistRepository.get_expired(db)
                if expired_entries:
                    # Chia nhỏ danh sách để tránh treo loop quá lâu
                    for i in range(0, len(expired_entries), batch_size):
                        chunk = expired_entries[i : i + batch_size]
                        
                        async def unblock_with_sem(ip):
                            async with semaphore:
                                return ip, await fw_manager.unblock_ip(ip)

                        # 2. Thực thi song song lệnh gỡ chặn
                        tasks = [unblock_with_sem(e.ip_address) for e in chunk]
                        results = await asyncio.gather(*tasks)
                        
                        # Lọc ra các IP đã gỡ chặn thành công để update DB một lần
                        success_ips = [ip for ip, success in results if success]
                        
                        if success_ips:
                            count = BlacklistRepository.batch_deactivate(db, success_ips)
                            logger.info(f"Batch unblocked: {count}/{len(chunk)} IPs")

        except Exception as e:
            logger.error(f"Error in firewall cleanup worker: {e}")
        
        # Chờ đợi cho lần quét tiếp theo
        await asyncio.sleep(interval_seconds)