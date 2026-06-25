"""
Audit log API
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.repository import AuditLogRepository

audit_router = APIRouter()


@audit_router.get("/")
async def list_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    action: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    rows = AuditLogRepository.list_entries(db, limit=limit, skip=skip, action=action, username=username)
    return [
        {
            "id": r.id,
            "username": r.username,
            "action": r.action,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "details": r.details,
            "client_ip": r.client_ip,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
