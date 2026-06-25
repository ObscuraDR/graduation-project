"""
Blacklist, Geo-blocking, and Security Report API routes
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import AttackAlert, AttackHistory, Blacklist, GeoBlockRule, GeoAllowRule, GeoWatchRule
from backend.database.repository import (
    BlacklistRepository,
    GeoBlockRepository,
    GeoAllowRepository,
    GeoWatchRepository,
    BlockHistoryRepository,
    SecurityReportRepository,
    ServerRepository,
)
from backend.alert_engine.alert_manager import get_alert_manager
from backend.api.validation import validate_ipv4
from backend.audit.logger import record_audit, get_client_ip, get_actor_username

blacklist_router = APIRouter()
geoblock_router = APIRouter()
geoallow_router = APIRouter()
geowatch_router = APIRouter()
reports_router = APIRouter()


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────

class BlacklistAddRequest(BaseModel):
    ip_address: str = Field(..., min_length=1, max_length=45)
    reason: Optional[str] = Field(None, max_length=500)
    expires_hours: Optional[int] = Field(None, ge=1, description="Block duration in hours; omit for permanent")

    @field_validator("ip_address")
    @classmethod
    def _val_ip(cls, v: str) -> str:
        return validate_ipv4(v)


class BlacklistRemoveRequest(BaseModel):
    ip_address: str

    @field_validator("ip_address")
    @classmethod
    def _val_ip(cls, v: str) -> str:
        return validate_ipv4(v)


class GeoBlockAddRequest(BaseModel):
    country_code: str = Field(..., min_length=2, max_length=5)
    country_name: Optional[str] = Field(None, max_length=100)


# ──────────────────────────────────────────────
# Blacklist routes
# ──────────────────────────────────────────────

@blacklist_router.get("/")
async def list_blacklist(db: Session = Depends(get_db)):
    entries = BlacklistRepository.get_all_active(db)
    return [
        {
            "id": e.id,
            "ip_address": e.ip_address,
            "reason": e.reason,
            "country_code": e.country_code,
            "auto_blocked": e.auto_blocked,
            "is_active": e.is_active,
            "created_at": e.created_at.isoformat(),
            "expires_at": e.expires_at.isoformat() if e.expires_at else None,
        }
        for e in entries
    ]


@blacklist_router.post("/", status_code=status.HTTP_201_CREATED)
async def add_to_blacklist(body: BlacklistAddRequest, request: Request, db: Session = Depends(get_db)):
    existing = BlacklistRepository.get_by_ip(db, body.ip_address)
    if existing and existing.is_active:
        raise HTTPException(status_code=409, detail="IP already blacklisted")

    expires_at = None
    duration_hours = body.expires_hours
    if body.expires_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=body.expires_hours)

    country_code = None
    try:
        from backend.api.routes.geoip import lookup_country
        country_code = lookup_country(body.ip_address)
    except Exception:
        pass

    entry = BlacklistRepository.create(
        db,
        ip_address=body.ip_address,
        reason=body.reason,
        country_code=country_code,
        auto_blocked=False,
        expires_at=expires_at,
    )
    get_alert_manager().add_to_blacklist(body.ip_address)
    actor = get_actor_username(request)
    BlockHistoryRepository.record(
        db,
        ip_address=body.ip_address,
        action="block",
        reason=body.reason,
        duration_hours=duration_hours,
        performed_by=actor,
        auto_blocked=False,
    )
    record_audit(
        db, actor, "blacklist_add",
        resource_type="ip", resource_id=body.ip_address,
        details={"reason": body.reason, "expires_hours": body.expires_hours},
        client_ip=get_client_ip(request),
    )
    return {"message": "IP added to blacklist", "entry": {
        "id": entry.id, "ip_address": entry.ip_address,
        "country_code": entry.country_code, "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
    }}


@blacklist_router.delete("/{ip_address}")
async def remove_from_blacklist(ip_address: str, request: Request, db: Session = Depends(get_db)):
    ok = BlacklistRepository.deactivate(db, ip_address)
    if not ok:
        raise HTTPException(status_code=404, detail="IP not found in blacklist")
    get_alert_manager().remove_from_blacklist(ip_address)
    actor = get_actor_username(request)
    BlockHistoryRepository.record(
        db,
        ip_address=ip_address,
        action="unblock",
        reason="Manual unblock",
        performed_by=actor,
    )
    record_audit(
        db, actor, "blacklist_remove",
        resource_type="ip", resource_id=ip_address,
        client_ip=get_client_ip(request),
    )
    return {"message": f"{ip_address} removed from blacklist"}


@blacklist_router.get("/history")
async def list_block_history(
    limit: int = Query(100, ge=1, le=500),
    ip_address: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    rows = BlockHistoryRepository.list_entries(db, limit=limit, ip_address=ip_address)
    return [
        {
            "id": r.id,
            "ip_address": r.ip_address,
            "action": r.action,
            "reason": r.reason,
            "duration_hours": r.duration_hours,
            "performed_by": r.performed_by,
            "auto_blocked": r.auto_blocked,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


# ──────────────────────────────────────────────
# Geo-block routes
# ──────────────────────────────────────────────

@geoblock_router.get("/")
async def list_geo_rules(db: Session = Depends(get_db)):
    rules = GeoBlockRepository.get_all(db)
    return [
        {
            "id": r.id,
            "country_code": r.country_code,
            "country_name": r.country_name,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat(),
        }
        for r in rules
    ]


@geoblock_router.post("/", status_code=status.HTTP_201_CREATED)
async def add_geo_rule(body: GeoBlockAddRequest, request: Request, db: Session = Depends(get_db)):
    existing = db.query(GeoBlockRule).filter_by(country_code=body.country_code.upper()).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.commit()
            get_alert_manager().add_geo_block(body.country_code.upper())
            return {"message": f"Geo-block rule for {body.country_code.upper()} re-activated"}
        raise HTTPException(status_code=409, detail="Country already blocked")
    rule = GeoBlockRepository.add_rule(db, body.country_code, body.country_name)
    get_alert_manager().add_geo_block(body.country_code.upper())
    record_audit(
        db, get_actor_username(request), "geo_block_add",
        resource_type="country", resource_id=body.country_code.upper(),
        details={"country_name": body.country_name},
        client_ip=get_client_ip(request),
    )
    return {"message": f"Geo-block added for {rule.country_code}", "id": rule.id}


@geoblock_router.delete("/{country_code}")
async def remove_geo_rule(country_code: str, request: Request, db: Session = Depends(get_db)):
    ok = GeoBlockRepository.remove_rule(db, country_code)
    if not ok:
        raise HTTPException(status_code=404, detail="Geo-block rule not found")
    get_alert_manager().remove_geo_block(country_code.upper())
    record_audit(
        db, get_actor_username(request), "geo_block_remove",
        resource_type="country", resource_id=country_code.upper(),
        client_ip=get_client_ip(request),
    )
    return {"message": f"Geo-block removed for {country_code.upper()}"}


# ── Geo allow / watch ──────────────────────────────────────────────

def _geo_policy_list(db: Session, repo, label: str):
    rules = repo.get_all(db)
    return [
        {
            "id": r.id,
            "country_code": r.country_code,
            "country_name": r.country_name,
            "is_active": r.is_active,
            "policy": label,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rules
    ]


@geoallow_router.get("/")
async def list_geo_allow(db: Session = Depends(get_db)):
    return _geo_policy_list(db, GeoAllowRepository, "allow")


@geoallow_router.post("/", status_code=status.HTTP_201_CREATED)
async def add_geo_allow(body: GeoBlockAddRequest, request: Request, db: Session = Depends(get_db)):
    existing = db.query(GeoAllowRule).filter_by(country_code=body.country_code.upper()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Country already in allow list")
    rule = GeoAllowRepository.add_rule(db, body.country_code, body.country_name)
    get_alert_manager().add_geo_allow(body.country_code.upper())
    record_audit(
        db, get_actor_username(request), "geo_allow_add",
        resource_type="country", resource_id=body.country_code.upper(),
        client_ip=get_client_ip(request),
    )
    return {"message": f"Allow rule added for {rule.country_code}", "id": rule.id}


@geoallow_router.delete("/{country_code}")
async def remove_geo_allow(country_code: str, request: Request, db: Session = Depends(get_db)):
    if not GeoAllowRepository.remove_rule(db, country_code):
        raise HTTPException(status_code=404, detail="Allow rule not found")
    get_alert_manager().remove_geo_allow(country_code.upper())
    record_audit(
        db, get_actor_username(request), "geo_allow_remove",
        resource_type="country", resource_id=country_code.upper(),
        client_ip=get_client_ip(request),
    )
    return {"message": f"Allow rule removed for {country_code.upper()}"}


@geowatch_router.get("/")
async def list_geo_watch(db: Session = Depends(get_db)):
    return _geo_policy_list(db, GeoWatchRepository, "watch")


@geowatch_router.post("/", status_code=status.HTTP_201_CREATED)
async def add_geo_watch(body: GeoBlockAddRequest, request: Request, db: Session = Depends(get_db)):
    existing = db.query(GeoWatchRule).filter_by(country_code=body.country_code.upper()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Country already in watch list")
    rule = GeoWatchRepository.add_rule(db, body.country_code, body.country_name)
    get_alert_manager().add_geo_watch(body.country_code.upper())
    record_audit(
        db, get_actor_username(request), "geo_watch_add",
        resource_type="country", resource_id=body.country_code.upper(),
        client_ip=get_client_ip(request),
    )
    return {"message": f"Watch rule added for {rule.country_code}", "id": rule.id}


@geowatch_router.delete("/{country_code}")
async def remove_geo_watch(country_code: str, request: Request, db: Session = Depends(get_db)):
    if not GeoWatchRepository.remove_rule(db, country_code):
        raise HTTPException(status_code=404, detail="Watch rule not found")
    get_alert_manager().remove_geo_watch(country_code.upper())
    record_audit(
        db, get_actor_username(request), "geo_watch_remove",
        resource_type="country", resource_id=country_code.upper(),
        client_ip=get_client_ip(request),
    )
    return {"message": f"Watch rule removed for {country_code.upper()}"}


# ──────────────────────────────────────────────
# Security report routes
# ──────────────────────────────────────────────

def _build_report(db: Session, hours: int = 24) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=hours)

    alerts = db.query(AttackAlert).filter(AttackAlert.timestamp >= since).all()
    total = len(alerts)
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    type_counts: Dict[str, int] = {}
    attacker_counts: Dict[str, int] = {}

    for a in alerts:
        sev = (a.severity or "low").lower()
        counts[sev] = counts.get(sev, 0) + 1
        type_counts[a.attack_type] = type_counts.get(a.attack_type, 0) + 1
        attacker_counts[a.source_ip] = attacker_counts.get(a.source_ip, 0) + 1

    top_attackers = sorted(
        [{"ip": k, "count": v} for k, v in attacker_counts.items()],
        key=lambda x: x["count"], reverse=True
    )[:10]
    top_attack_types = sorted(
        [{"type": k, "count": v} for k, v in type_counts.items()],
        key=lambda x: x["count"], reverse=True
    )[:10]

    auto_blocked = db.query(Blacklist).filter_by(auto_blocked=True).count()
    geo_blocked = db.query(GeoBlockRule).filter_by(is_active=True).count()

    # Lightweight human-readable summary for PDF/export UI.
    critical = counts["critical"]
    high = counts["high"]
    medium = counts["medium"]
    low = counts["low"]
    summary = (
        f"In the last {hours}h, the system observed {total} alerts: "
        f"{critical} critical, {high} high, {medium} medium, and {low} low. "
        f"Auto-blocked IPs: {auto_blocked}; Geo-blocked countries: {geo_blocked}."
    )

    return {
        "report_id": str(uuid.uuid4()),
        "period_hours": hours,
        "period_start": since.isoformat(),
        "period_end": now.isoformat(),
        "total_alerts": total,
        "critical_count": counts["critical"],
        "high_count": counts["high"],
        "medium_count": counts["medium"],
        "low_count": counts["low"],
        "top_attackers": top_attackers,
        "top_attack_types": top_attack_types,
        "auto_blocked_count": auto_blocked,
        "geo_blocked_count": geo_blocked,
        "summary": summary,
        "generated_at": now.isoformat(),
    }


@reports_router.get("/security")
async def get_security_report(
    hours: int = Query(24, ge=1, le=720, description="Report window in hours"),
    save: bool = Query(False, description="Persist report to database"),
    db: Session = Depends(get_db),
):
    report = _build_report(db, hours)
    if save:
        from backend.database.models import SecurityReport
        SecurityReportRepository.create(db, {
            "report_id": report["report_id"],
            "period_start": datetime.fromisoformat(report["period_start"]),
            "period_end": datetime.fromisoformat(report["period_end"]),
            "total_alerts": report["total_alerts"],
            "critical_count": report["critical_count"],
            "high_count": report["high_count"],
            "medium_count": report["medium_count"],
            "low_count": report["low_count"],
            "top_attackers": report["top_attackers"],
            "top_attack_types": report["top_attack_types"],
            "auto_blocked_count": report["auto_blocked_count"],
            "geo_blocked_count": report["geo_blocked_count"],
        })
    return report


@reports_router.get("/security/history")
async def list_saved_reports(limit: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)):
    rows = SecurityReportRepository.get_latest(db, limit)
    return [
        {
            "id": r.id,
            "report_id": r.report_id,
            "period_start": r.period_start.isoformat(),
            "period_end": r.period_end.isoformat(),
            "total_alerts": r.total_alerts,
            "critical_count": r.critical_count,
            "high_count": r.high_count,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
