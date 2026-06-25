"""Audit trail helper — records user actions to PostgreSQL."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from backend.database.models import AuditLog


def get_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def get_actor_username(request: Request) -> str:
    """Best-effort username from JWT cookie/header; falls back to 'system'."""
    from jose import jwt, JWTError
    from backend.config import settings

    token = request.cookies.get("access_token")
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        return "system"
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("sub") or "system"
    except JWTError:
        return "system"


def record_audit(
    db: Session,
    username: str,
    action: str,
    *,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    client_ip: Optional[str] = None,
) -> AuditLog:
    entry = AuditLog(
        username=username,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        client_ip=client_ip,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
