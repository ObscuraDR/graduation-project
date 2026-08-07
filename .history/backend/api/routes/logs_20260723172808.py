"""
Security log viewer API
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from backend.database.security_log_store import query_security_logs

logs_router = APIRouter()


@logs_router.get("/")
async def list_security_logs(
    source_ip: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    server: Optional[str] = Query(None),
    log_source: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
):
    """Search centralized security logs stored in PostgreSQL."""
    return query_security_logs(
        source_ip=source_ip,
        event_type=event_type,
        server=server,
        log_source=log_source,
        search=search,
        limit=limit,
        skip=skip,
    )
