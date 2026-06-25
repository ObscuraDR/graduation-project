"""
Centralized security log storage (PostgreSQL with JSONB).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import or_, desc

logger = logging.getLogger(__name__)

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
