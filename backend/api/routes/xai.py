"""
XAI Router  –  POST /api/xai/explain
======================================
Provides feature-level SHAP explanations for any single prediction.

This endpoint is intentionally **separate** from the real-time sniffer
pipeline and does not affect packet-processing throughput.

Request body
------------
{
  "model_name": "ensemble",       // optional, defaults to "ensemble"
  "features": {                   // exactly the 20 features in features.json
    "flow_duration": 1.5,
    ...
  }
}

Response (success)
------------------
{
  "success": true,
  "message": "Explanation generated",
  "data": {
    "model_name": "ensemble",
    "predicted_label": "DDoS",
    "confidence": 0.91,
    "probabilities": {"Normal": 0.09, "DDoS": 0.91},
    "base_value": 0.12,
    "top_features": [
      {"feature": "packet_rate", "value": 1200.0, "shap_value": 0.34},
      ...
    ],
    "shap_values": {"flow_duration": -0.02, ...}
  }
}
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from backend.detection_engine.predictor import FeatureContractError
from backend.ml.xai import UnsupportedModelError, explain

logger = logging.getLogger(__name__)

xai_router = APIRouter()

# ---------------------------------------------------------------------------
# Paths (project-root-relative; same as ModelLoader defaults)
# ---------------------------------------------------------------------------

_FEATURES_JSON = Path("./models/features.json")
_MODELS_DIR = Path("./models")

# Cache the feature set for fast validation (populated on first request)
_EXPECTED_FEATURES: set[str] | None = None


def _get_expected_features() -> set[str]:
    """Load and cache the set of required feature names."""
    global _EXPECTED_FEATURES
    if _EXPECTED_FEATURES is None:
        if not _FEATURES_JSON.exists():
            raise HTTPException(
                status_code=500,
                detail="features.json not found – server configuration error",
            )
        with open(_FEATURES_JSON, encoding="utf-8") as fh:
            data = json.load(fh)
        _EXPECTED_FEATURES = set(data.get("feature_names", []))
    return _EXPECTED_FEATURES


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ExplainRequest(BaseModel):
    model_name: str = Field(default="ensemble", description="Model artifact name (e.g. 'ensemble')")
    features: Dict[str, float] = Field(
        ...,
        description="Exactly the 20 features defined in models/features.json",
    )

    @model_validator(mode="after")
    def _clean_values(self) -> "ExplainRequest":
        """Replace NaN / ±inf with safe finite values (mirrors Predictor._validate_features)."""
        cleaned: Dict[str, float] = {}
        for k, v in self.features.items():
            if math.isnan(v):
                cleaned[k] = 0.0
            elif math.isinf(v):
                limit = float(np.finfo(np.float64).max)
                cleaned[k] = limit if v > 0 else -limit
            else:
                cleaned[k] = v
        self.features = cleaned
        return self


class ExplainResponse(BaseModel):
    success: bool
    message: str
    data: Dict[str, Any]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@xai_router.post(
    "/explain",
    response_model=ExplainResponse,
    summary="Explain a single prediction with SHAP",
    description=(
        "Runs a SHAP TreeExplainer on the supplied feature vector and returns "
        "per-feature attributions, the predicted label, and a probability distribution. "
        "Only tree-based models (RandomForest, ensemble wrapping RF) are supported."
    ),
)
async def explain_prediction(request: ExplainRequest) -> ExplainResponse:
    """
    POST /api/xai/explain

    Validates the feature contract, runs SHAP TreeExplainer, and returns
    a structured explanation.
    """
    # ── 1. Validate feature contract ─────────────────────────────────────────
    expected = _get_expected_features()
    provided = set(request.features.keys())

    missing = expected - provided
    extra = provided - expected

    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing features: {sorted(missing)}")
        if extra:
            details.append(f"extra/unknown features: {sorted(extra)}")
        raise HTTPException(
            status_code=422,
            detail={
                "error": "FeatureContractError",
                "message": "Feature keys do not match models/features.json",
                "details": "; ".join(details),
            },
        )

    # ── 2. Run explanation ────────────────────────────────────────────────────
    try:
        result = explain(
            features=request.features,
            model_name=request.model_name,
            top_n=5,
            models_dir=_MODELS_DIR,
            features_path=_FEATURES_JSON,
        )
    except UnsupportedModelError as exc:
        logger.warning("Unsupported model requested for XAI: %s", exc)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "UnsupportedModelError",
                "message": str(exc),
            },
        )
    except FeatureContractError as exc:
        logger.error("Feature contract error during XAI: %s", exc)
        raise HTTPException(
            status_code=422,
            detail={
                "error": "FeatureContractError",
                "message": str(exc),
            },
        )
    except (FileNotFoundError, RuntimeError) as exc:
        logger.error("Model loading error during XAI: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ModelLoadError",
                "message": str(exc),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during XAI explanation")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "InternalError",
                "message": f"Unexpected error: {exc}",
            },
        )

    return ExplainResponse(
        success=True,
        message="Explanation generated",
        data=result,
    )
