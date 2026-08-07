"""
Centralized security log storage in PostgreSQL.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from sqlalchemy import or_, desc

logger = logging.getLogger(__name__)

# Tier 4: TTL configuration - auto-delete logs older than 7 days
LOG_TTL_DAYS = 7

def store_security_log(
    *,
    server: str = "local",
    source_ip: Optional[str] = None,
    country: Optional[str] = None,
    event_type: str = "generic",
    message: str = "",
    log_source: str = "unknown",
    raw: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        from backend.database.connection import SessionLocal
        from backend.database.models import SecurityLog

        db = SessionLocal()
        try:
            log_entry = SecurityLog(
                server=server,
                source_ip=source_ip,
                country=country,
                event_type=event_type,
                message=message[:4000] if message else "",
                log_source=log_source,
                raw=(raw[:8000] if raw else None),
                extra=extra or {},
                timestamp=datetime.now(timezone.utc)
            )
            db.add(log_entry)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.debug("Security log store skipped: %s", exc)


def cleanup_old_logs(ttl_days: int = LOG_TTL_DAYS) -> int:
    """
    Tier 4: Auto-delete security logs older than TTL days.
    Gọi định kỳ để tránh bảng phình to.
    Returns: số lượng log đã xóa.
    """
    try:
        from backend.database.connection import SessionLocal
        from backend.database.models import SecurityLog

        db = SessionLocal()
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=ttl_days)
            deleted = db.query(SecurityLog).filter(
                SecurityLog.timestamp < cutoff_date
            ).delete()
            db.commit()
            if deleted > 0:
                logger.info("Cleaned up %d old security logs (older than %d days)", deleted, ttl_days)
            return deleted
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Log cleanup failed: %s", exc)
        return 0


def query_security_logs(
    *,
    source_ip: Optional[str] = None,
    event_type: Optional[str] = None,
    server: Optional[str] = None,
    log_source: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
) -> Dict[str, Any]:
    try:
        from backend.database.connection import SessionLocal
        from backend.database.models import SecurityLog

        db = SessionLocal()
        try:
            query = db.query(SecurityLog)
            
            if source_ip:
                query = query.filter(SecurityLog.source_ip == source_ip)
            if event_type:
                query = query.filter(SecurityLog.event_type == event_type)
            if server:
                query = query.filter(SecurityLog.server == server)
            if log_source:
                query = query.filter(SecurityLog.log_source == log_source)
            if search:
                query = query.filter(
                    or_(
                        SecurityLog.message.ilike(f"%{search}%"),
                        SecurityLog.source_ip.ilike(f"%{search}%")
                    )
                )

            total = query.count()
            logs = query.order_by(desc(SecurityLog.timestamp)).offset(skip).limit(limit).all()
            
            items = []
            for log in logs:
                items.append({
                    "id": log.id,
                    "server": log.server,
                    "source_ip": log.source_ip,
                    "country": log.country,
                    "event_type": log.event_type,
                    "message": log.message,
                    "log_source": log.log_source,
                    "extra": log.extra,
                    "timestamp": log.timestamp.replace(tzinfo=timezone.utc).isoformat() if log.timestamp else None
                })
                
            return {"items": items, "total": total, "limit": limit, "skip": skip}
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Security log query failed: %s", exc)
        return {"items": [], "total": 0, "limit": limit, "skip": skip, "error": str(exc)}


def cleanup_old_logs(retention_days: int = LOG_TTL_DAYS) -> int:
    """
    Xóa logs cũ hơn retention_days ngày.
    Gọi từ background worker để tránh bảng security_logs phình to.
    Trả về số dòng đã xóa.
    """
    try:
        from backend.database.connection import SessionLocal
        from backend.database.models import SecurityLog

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        db = SessionLocal()
        try:
            deleted = db.query(SecurityLog).filter(
                SecurityLog.timestamp < cutoff
            ).delete(synchronize_session=False)
            db.commit()
            if deleted > 0:
                logger.info("Security log cleanup: deleted %d rows older than %d days", deleted, retention_days)
            return deleted
        finally:
            db.close()
    except Exception as e:
        logger.error("Security log cleanup error: %s", e)
        return 0


async def log_cleanup_task(interval_hours: int = 6, retention_days: int = LOG_TTL_DAYS):
    """
    Background async task: dọn dẹp security_logs cũ mỗi 6 giờ.
    Tránh bảng phình to khi có nhiều máy chủ con gửi log.
    """
    import asyncio
    logger.info("Security log cleanup task started (every %dh, retain %dd)", interval_hours, retention_days)
    while True:
        await asyncio.sleep(interval_hours * 3600)
        try:
            # Chạy blocking DB operation trong thread pool
            deleted = await asyncio.to_thread(cleanup_old_logs, retention_days)
            if deleted > 0:
                logger.info("Auto-cleanup: removed %d old security logs", deleted)
        except Exception as e:
            logger.error("Log cleanup task error: %s", e)
