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
    limit: int = Query(50, ge=1, le=500),
    skip: int = Query(0, ge=0),
    action: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get audit logs with pagination support."""
    result = AuditLogRepository.list_entries(db, limit=limit, skip=skip, action=action, username=username)
    rows = result.get("items", [])

    return {
        "items": [
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
        ],
        "total": result.get("total", 0),
        "limit": limit,
        "skip": skip
    }
