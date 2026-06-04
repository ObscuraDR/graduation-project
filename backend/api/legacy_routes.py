"""
API Routes
FastAPI route handlers for IDS backend
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from backend.database.connection import get_db
from backend.database.models import AttackAlert, Model, Whitelist
from backend.alert_engine.alert_manager import get_alert_manager
from backend.ml.models import IDSModel

logger = logging.getLogger(__name__)

# Create routers
alerts_router = APIRouter()
predictions_router = APIRouter()
models_router = APIRouter()
whitelist_router = APIRouter()
stats_router = APIRouter()

# Global alert manager instance (replaces removed backend.alerts.engine.AlertEngine)
alert_manager = get_alert_manager()
# Global model instance (will be loaded at startup)
ml_model: Optional[IDSModel] = None


# ==================== Shared API schemas ====================

class ApiResponse(BaseModel):
    """Standard API envelope for whitelist and other JSON endpoints."""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class WhitelistEntryData(BaseModel):
    id: int
    ip_address: str
    port: Optional[int] = None
    protocol: Optional[str] = None
    reason: Optional[str] = None
    created_at: str
    in_memory: bool = Field(
        description="True if IP is active in AlertManager in-memory whitelist"
    )


class WhitelistAddRequest(BaseModel):
    ip_address: str = Field(..., min_length=1, max_length=45, examples=["192.168.1.10"])
    port: Optional[int] = Field(None, ge=1, le=65535)
    protocol: Optional[str] = Field(None, max_length=10)
    reason: Optional[str] = Field(None, max_length=500)

    @field_validator("ip_address")
    @classmethod
    def _validate_ip(cls, v: str) -> str:
        from backend.api.validation import validate_ipv4
        return validate_ipv4(v)

    @field_validator("protocol")
    @classmethod
    def _validate_protocol(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        from backend.api.validation import validate_protocol
        return validate_protocol(v)


class WhitelistRemoveRequest(BaseModel):
    whitelist_id: Optional[int] = Field(None, ge=1)
    ip_address: Optional[str] = Field(None, min_length=1, max_length=45)

    @field_validator("ip_address")
    @classmethod
    def _validate_ip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        from backend.api.validation import validate_ipv4
        return validate_ipv4(v)

    @model_validator(mode="after")
    def require_id_or_ip(self) -> "WhitelistRemoveRequest":
        if self.whitelist_id is None and not self.ip_address:
            raise ValueError("Provide either whitelist_id or ip_address")
        return self


class WhitelistListData(BaseModel):
    items: List[WhitelistEntryData]
    total: int
    in_memory_ips: List[str]


def _success(message: str, data: Optional[Dict[str, Any]] = None, status_code: int = 200) -> JSONResponse:
    body = ApiResponse(success=True, message=message, data=data).model_dump()
    return JSONResponse(status_code=status_code, content=body)


def _error(message: str, status_code: int, data: Optional[Dict[str, Any]] = None) -> JSONResponse:
    body = ApiResponse(success=False, message=message, data=data).model_dump()
    return JSONResponse(status_code=status_code, content=body)


def _whitelist_entry_to_dict(item: Whitelist) -> Dict[str, Any]:
    in_memory = item.ip_address in alert_manager.whitelist
    return WhitelistEntryData(
        id=item.id,
        ip_address=item.ip_address,
        port=item.port,
        protocol=item.protocol,
        reason=item.reason,
        created_at=item.created_at.isoformat(),
        in_memory=in_memory,
    ).model_dump()


# ==================== AttackAlert Routes ====================

@alerts_router.get("/", response_model=List[Dict[str, Any]])
async def get_alerts(
    skip: int = 0,
    limit: int = 100,
    severity: Optional[str] = None,
    alert_status: Optional[str] = Query(None, alias="status"),
    attack_type: Optional[str] = Query(None, alias="attackType"),
    db: Session = Depends(get_db),
):
    """Get all alerts with optional filtering"""
    query = db.query(AttackAlert)

    if severity:
        query = query.filter(AttackAlert.severity == severity)
    if alert_status:
        query = query.filter(AttackAlert.status == alert_status)
    if attack_type:
        query = query.filter(AttackAlert.attack_type == attack_type)

    alerts = query.order_by(AttackAlert.timestamp.desc()).offset(skip).limit(limit).all()

    return [
        {
            "id": alert.id,
            "alert_id": alert.alert_id,
            "source_ip": alert.source_ip,
            "dest_ip": alert.dest_ip,
            "source_port": alert.source_port,
            "dest_port": alert.dest_port,
            "attack_type": alert.attack_type,
            "severity": alert.severity,
            "confidence": float(alert.confidence),
            "timestamp": alert.timestamp.isoformat(),
            "status": alert.status,
            "is_resolved": alert.is_resolved,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "notes": alert.notes,
            "model_name": alert.model_name,
            "model_version": alert.model_version,
        }
        for alert in alerts
    ]


@alerts_router.get("/{alert_id}", response_model=Dict[str, Any])
async def get_alert(alert_id: str, db: Session = Depends(get_db)):
    """Get specific alert by ID"""
    alert = db.query(AttackAlert).filter(AttackAlert.alert_id == alert_id).first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AttackAlert {alert_id} not found",
        )

    return {
        "id": alert.id,
        "alert_id": alert.alert_id,
        "source_ip": alert.source_ip,
        "dest_ip": alert.dest_ip,
        "source_port": alert.source_port,
        "dest_port": alert.dest_port,
        "attack_type": alert.attack_type,
        "severity": alert.severity,
        "confidence": float(alert.confidence),
        "timestamp": alert.timestamp.isoformat(),
        "status": alert.status,
        "is_resolved": alert.is_resolved,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "notes": alert.notes,
        "model_name": alert.model_name,
        "model_version": alert.model_version,
    }


@alerts_router.put("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Resolve an alert"""
    alert = db.query(AttackAlert).filter(AttackAlert.alert_id == alert_id).first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AttackAlert {alert_id} not found",
        )

    alert.status = "resolved"
    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    if notes:
        alert.notes = notes

    db.commit()
    db.refresh(alert)

    logger.info("AttackAlert %s resolved", alert_id)
    return {"message": "AttackAlert resolved successfully", "alert_id": alert_id}


@alerts_router.delete("/{alert_id}")
async def delete_alert(alert_id: str, db: Session = Depends(get_db)):
    """Delete an alert"""
    alert = db.query(AttackAlert).filter(AttackAlert.alert_id == alert_id).first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AttackAlert {alert_id} not found",
        )

    db.delete(alert)
    db.commit()

    logger.info("AttackAlert %s deleted", alert_id)
    return {"message": "AttackAlert deleted successfully", "alert_id": alert_id}


# ==================== Prediction Routes ====================

@predictions_router.post("/")
async def predict(features: Dict[str, Any]):
    """Make prediction from features"""
    global ml_model

    if ml_model is None or not ml_model.is_trained:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML model not loaded or not trained",
        )

    try:
        import pandas as pd

        feature_df = pd.DataFrame([features])
        prediction = ml_model.predict(feature_df)
        prediction_proba = ml_model.predict_proba(feature_df)
        predicted_class = ml_model.label_encoder.inverse_transform([prediction[0]])[0]
        confidence = float(prediction_proba[0][prediction[0]])

        return {
            "class": predicted_class,
            "confidence": confidence,
            "model_name": ml_model.model_name,
            "model_version": "1.0",
            "all_probabilities": {
                ml_model.label_encoder.inverse_transform([i])[0]: float(prob)
                for i, prob in enumerate(prediction_proba[0])
            },
        }

    except Exception as e:
        logger.error("Prediction error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}",
        ) from e


@predictions_router.post("/batch")
async def batch_predict(features_list: List[Dict[str, Any]]):
    """Make batch predictions from features"""
    global ml_model

    if ml_model is None or not ml_model.is_trained:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML model not loaded or not trained",
        )

    try:
        import pandas as pd

        feature_df = pd.DataFrame(features_list)
        predictions = ml_model.predict(feature_df)
        prediction_proba = ml_model.predict_proba(feature_df)

        results = []
        for pred, proba in zip(predictions, prediction_proba):
            predicted_class = ml_model.label_encoder.inverse_transform([pred])[0]
            confidence = float(proba[pred])
            results.append(
                {
                    "class": predicted_class,
                    "confidence": confidence,
                    "model_name": ml_model.model_name,
                    "model_version": "1.0",
                }
            )

        return {"predictions": results}

    except Exception as e:
        logger.error("Batch prediction error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch prediction failed: {str(e)}",
        ) from e


# ==================== Model Routes ====================

@models_router.get("/", response_model=List[Dict[str, Any]])
async def get_models(db: Session = Depends(get_db)):
    """Get all trained models"""
    models = db.query(Model).order_by(Model.created_at.desc()).all()

    return [
        {
            "id": model.id,
            "model_name": model.model_name,
            "version": model.version,
            "algorithm": model.algorithm,
            "accuracy": float(model.accuracy) if model.accuracy else None,
            "precision": float(model.precision) if model.precision else None,
            "recall": float(model.recall) if model.recall else None,
            "f1_score": float(model.f1_score) if model.f1_score else None,
            "is_active": model.is_active,
            "created_at": model.created_at.isoformat(),
        }
        for model in models
    ]


@models_router.post("/load/{model_id}")
async def load_model(model_id: int, db: Session = Depends(get_db)):
    """Load a specific model for inference"""
    global ml_model

    model = db.query(Model).filter(Model.id == model_id).first()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found",
        )

    try:
        from backend.ml.models import RandomForestIDS, XGBoostIDS

        if model.algorithm == "RandomForest":
            ml_model = RandomForestIDS()
        elif model.algorithm == "XGBoost":
            ml_model = XGBoostIDS()
        else:
            raise ValueError(f"Unsupported algorithm: {model.algorithm}")

        ml_model.load(model.file_path)
        db.query(Model).update({"is_active": False})
        model.is_active = True
        db.commit()

        logger.info("Model %s loaded successfully", model.model_name)
        return {"message": "Model loaded successfully", "model_name": model.model_name}

    except Exception as e:
        logger.error("Model loading error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load model: {str(e)}",
        ) from e


# ==================== Whitelist Routes ====================

@whitelist_router.get(
    "/list",
    response_model=ApiResponse,
    summary="List whitelist entries (database + in-memory status)",
)
async def list_whitelist(db: Session = Depends(get_db)):
    """GET /api/whitelist/list — all whitelisted IPs from PostgreSQL."""
    rows = db.query(Whitelist).order_by(Whitelist.created_at.desc()).all()
    items = [_whitelist_entry_to_dict(row) for row in rows]
    in_memory_ips = alert_manager.get_whitelist()

    data = WhitelistListData(
        items=[WhitelistEntryData(**item) for item in items],
        total=len(items),
        in_memory_ips=in_memory_ips,
    ).model_dump()

    return _success(
        message=f"Retrieved {len(items)} whitelist entr{'y' if len(items) == 1 else 'ies'}",
        data=data,
    )


@whitelist_router.post(
    "/add",
    response_model=ApiResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add IP to whitelist",
)
async def add_whitelist_entry(
    body: WhitelistAddRequest,
    db: Session = Depends(get_db),
):
    """POST /api/whitelist/add — persist to DB and sync AlertManager in-memory set."""
    existing = (
        db.query(Whitelist)
        .filter(Whitelist.ip_address == body.ip_address, Whitelist.port == body.port)
        .first()
    )

    if existing:
        return _error(
            message="IP already whitelisted",
            status_code=status.HTTP_409_CONFLICT,
            data={"existing": _whitelist_entry_to_dict(existing)},
        )

    whitelist_item = Whitelist(
        ip_address=body.ip_address,
        port=body.port,
        protocol=body.protocol,
        reason=body.reason,
    )
    db.add(whitelist_item)
    db.commit()
    db.refresh(whitelist_item)

    alert_manager.add_to_whitelist(body.ip_address)

    logger.info("Added %s to whitelist (id=%s)", body.ip_address, whitelist_item.id)
    return _success(
        message="IP added to whitelist successfully",
        data={"entry": _whitelist_entry_to_dict(whitelist_item)},
        status_code=status.HTTP_201_CREATED,
    )


@whitelist_router.post(
    "/remove",
    response_model=ApiResponse,
    summary="Remove IP from whitelist",
)
async def remove_whitelist_entry(
    body: WhitelistRemoveRequest,
    db: Session = Depends(get_db),
):
    """POST /api/whitelist/remove — by database id and/or IP address."""
    item: Optional[Whitelist] = None

    if body.whitelist_id is not None:
        item = db.query(Whitelist).filter(Whitelist.id == body.whitelist_id).first()
    elif body.ip_address:
        item = db.query(Whitelist).filter(Whitelist.ip_address == body.ip_address).first()

    if not item:
        return _error(
            message="Whitelist entry not found",
            status_code=status.HTTP_404_NOT_FOUND,
            data={
                "whitelist_id": body.whitelist_id,
                "ip_address": body.ip_address,
            },
        )

    ip_address = item.ip_address
    entry_data = _whitelist_entry_to_dict(item)

    db.delete(item)
    db.commit()

    alert_manager.remove_from_whitelist(ip_address)

    logger.info("Removed %s from whitelist (id=%s)", ip_address, item.id)
    return _success(
        message="IP removed from whitelist successfully",
        data={"removed": entry_data},
    )


# Legacy aliases (same behavior, standard envelope where applicable)

@whitelist_router.get("/", response_model=ApiResponse, include_in_schema=False)
async def get_whitelist_legacy(db: Session = Depends(get_db)):
    """Deprecated: use GET /api/whitelist/list"""
    return await list_whitelist(db)


@whitelist_router.delete("/{whitelist_id}", response_model=ApiResponse, include_in_schema=False)
async def delete_whitelist_legacy(whitelist_id: int, db: Session = Depends(get_db)):
    """Deprecated: use POST /api/whitelist/remove with {\"whitelist_id\": ...}"""
    return await remove_whitelist_entry(
        WhitelistRemoveRequest(whitelist_id=whitelist_id),
        db=db,
    )


# ==================== Statistics Routes ====================

@stats_router.get("/alert-engine")
async def get_alert_manager_stats():
    """Get alert manager statistics (in-memory engine state)"""
    return alert_manager.get_stats()


@stats_router.get("/system")
async def get_system_stats(db: Session = Depends(get_db)):
    """Get system statistics"""
    total_alerts = db.query(AttackAlert).count()
    active_alerts = db.query(AttackAlert).filter(AttackAlert.status == "active").count()
    resolved_alerts = db.query(AttackAlert).filter(AttackAlert.is_resolved.is_(True)).count()

    severity_counts = {
        severity: db.query(AttackAlert).filter(AttackAlert.severity == severity).count()
        for severity in ["critical", "high", "medium", "low"]
    }

    return {
        "total_alerts": total_alerts,
        "active_alerts": active_alerts,
        "resolved_alerts": resolved_alerts,
        "alerts_by_severity": severity_counts,
        "whitelist_count": db.query(Whitelist).count(),
        "model_count": db.query(Model).count(),
    }


@stats_router.get("/training-report")
async def get_training_report():
    """
    GET /api/stats/training-report — Trả về training metrics từ
    backend/reports/cicids2017_training_report.json (nếu tồn tại).
    """
    import json
    from pathlib import Path

    report_path = Path("backend/reports/cicids2017_training_report.json")
    if not report_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training report not found. Run: python backend/scripts/generate_and_train.py",
        )

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load training report: {e}",
        ) from e
