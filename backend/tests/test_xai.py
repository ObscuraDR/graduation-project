"""
Unit Tests – XAI Endpoint
===========================
Tests for POST /api/xai/explain.

Strategy
--------
* All tests mock ``backend.api.routes.xai.explain`` (the XAI core) and
  ``backend.api.routes.xai._get_expected_features`` so no real model I/O
  or SHAP computation is performed.
* The TestClient exercises the full FastAPI request/response cycle.

Test matrix
-----------
test_explain_success              – happy path, all 20 features → 200 + payload
test_explain_missing_feature_fails – drop one feature → 422 FeatureContractError
test_explain_model_not_supported   – mock raises UnsupportedModelError → 400
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── The 20 canonical feature names (mirrors models/features.json) ─────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FEATURES_JSON = PROJECT_ROOT / "models" / "features.json"


def _load_feature_names() -> list[str]:
    with open(FEATURES_JSON, encoding="utf-8") as fh:
        return json.load(fh)["feature_names"]


FEATURE_NAMES: list[str] = _load_feature_names()

# A valid 20-feature payload (all zeros – SHAP is mocked so values don't matter)
VALID_FEATURES: Dict[str, float] = {name: 0.0 for name in FEATURE_NAMES}

# ── Mock return value for explain() ──────────────────────────────────────────
MOCK_EXPLAIN_RESULT = {
    "model_name": "ensemble",
    "predicted_label": "DDoS",
    "confidence": 0.91,
    "probabilities": {"Normal": 0.09, "DDoS": 0.91},
    "base_value": 0.12,
    "top_features": [
        {"feature": "packet_rate", "value": 0.0, "shap_value": 0.34},
        {"feature": "byte_rate", "value": 0.0, "shap_value": 0.21},
        {"feature": "syn_count", "value": 0.0, "shap_value": 0.18},
        {"feature": "flow_duration", "value": 0.0, "shap_value": -0.10},
        {"feature": "total_fwd_packets", "value": 0.0, "shap_value": 0.08},
    ],
    "shap_values": {name: 0.0 for name in FEATURE_NAMES},
}


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def test_client():
    """
    Create a TestClient for the main FastAPI app with XAI dependencies mocked.

    We patch ``_get_expected_features`` so tests don't need a live server or
    filesystem lookup during import of the router.
    """
    from backend.main import app

    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_explain_success(test_client: TestClient) -> None:
    """
    POST /api/xai/explain with all 20 valid features must return HTTP 200
    and a well-structured JSON payload.
    """
    expected_features_set = set(FEATURE_NAMES)

    with (
        patch(
            "backend.api.routes.xai._get_expected_features",
            return_value=expected_features_set,
        ),
        patch(
            "backend.api.routes.xai.explain",
            return_value=MOCK_EXPLAIN_RESULT,
        ) as mock_explain,
    ):
        response = test_client.post(
            "/api/xai/explain",
            json={"model_name": "ensemble", "features": VALID_FEATURES},
        )

    assert response.status_code == 200, response.text

    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Explanation generated"

    data = body["data"]
    assert data["model_name"] == "ensemble"
    assert data["predicted_label"] == "DDoS"
    assert 0.0 <= data["confidence"] <= 1.0
    assert isinstance(data["probabilities"], dict)
    assert isinstance(data["base_value"], float)
    assert isinstance(data["top_features"], list)
    assert len(data["top_features"]) == 5
    assert isinstance(data["shap_values"], dict)

    # Verify explain() was called with the cleaned feature dict
    mock_explain.assert_called_once()
    call_kwargs = mock_explain.call_args
    assert call_kwargs.kwargs["model_name"] == "ensemble"
    assert set(call_kwargs.kwargs["features"].keys()) == expected_features_set


@pytest.mark.unit
def test_explain_missing_feature_fails(test_client: TestClient) -> None:
    """
    POST /api/xai/explain with one feature removed must return HTTP 422
    and a FeatureContractError payload.
    """
    expected_features_set = set(FEATURE_NAMES)

    # Drop the first feature
    incomplete_features = {k: v for k, v in VALID_FEATURES.items() if k != FEATURE_NAMES[0]}
    assert len(incomplete_features) == len(FEATURE_NAMES) - 1

    with patch(
        "backend.api.routes.xai._get_expected_features",
        return_value=expected_features_set,
    ):
        response = test_client.post(
            "/api/xai/explain",
            json={"model_name": "ensemble", "features": incomplete_features},
        )

    assert response.status_code == 422, response.text

    body = response.json()
    # FastAPI wraps HTTPException detail in {"detail": ...}
    detail = body.get("detail", body)
    assert detail["error"] == "FeatureContractError"
    assert "missing features" in detail["message"].lower() or "missing features" in detail.get("details", "").lower()


@pytest.mark.unit
def test_explain_extra_feature_fails(test_client: TestClient) -> None:
    """
    POST /api/xai/explain with an extra unknown feature must return HTTP 422.
    """
    expected_features_set = set(FEATURE_NAMES)

    extra_features = dict(VALID_FEATURES)
    extra_features["totally_unknown_feature_xyz"] = 99.9

    with patch(
        "backend.api.routes.xai._get_expected_features",
        return_value=expected_features_set,
    ):
        response = test_client.post(
            "/api/xai/explain",
            json={"model_name": "ensemble", "features": extra_features},
        )

    assert response.status_code == 422, response.text

    body = response.json()
    detail = body.get("detail", body)
    assert detail["error"] == "FeatureContractError"
    assert "extra" in detail.get("details", "").lower()


@pytest.mark.unit
def test_explain_model_not_supported(test_client: TestClient) -> None:
    """
    POST /api/xai/explain where the model does not support TreeExplainer
    must return HTTP 400 with UnsupportedModelError.
    """
    from backend.ml.xai import UnsupportedModelError

    expected_features_set = set(FEATURE_NAMES)

    with (
        patch(
            "backend.api.routes.xai._get_expected_features",
            return_value=expected_features_set,
        ),
        patch(
            "backend.api.routes.xai.explain",
            side_effect=UnsupportedModelError(
                "Model type 'LSTM' is not supported by SHAP TreeExplainer."
            ),
        ),
    ):
        response = test_client.post(
            "/api/xai/explain",
            json={"model_name": "lstm", "features": VALID_FEATURES},
        )

    assert response.status_code == 400, response.text

    body = response.json()
    detail = body.get("detail", body)
    assert detail["error"] == "UnsupportedModelError"
    assert "TreeExplainer" in detail["message"] or "not supported" in detail["message"].lower()


@pytest.mark.unit
def test_explain_nan_inf_cleaning(test_client: TestClient) -> None:
    """
    NaN and ±inf values submitted in features must be silently sanitized
    before reaching the explain() function.
    """
    import math

    expected_features_set = set(FEATURE_NAMES)

    dirty_features = dict(VALID_FEATURES)
    dirty_features[FEATURE_NAMES[0]] = "NaN"
    dirty_features[FEATURE_NAMES[1]] = "Infinity"
    dirty_features[FEATURE_NAMES[2]] = "-Infinity"

    with (
        patch(
            "backend.api.routes.xai._get_expected_features",
            return_value=expected_features_set,
        ),
        patch(
            "backend.api.routes.xai.explain",
            return_value=MOCK_EXPLAIN_RESULT,
        ) as mock_explain,
    ):
        response = test_client.post(
            "/api/xai/explain",
            json={"model_name": "ensemble", "features": dirty_features},
        )

    # Should succeed – NaN/inf should have been cleaned by the Pydantic validator
    assert response.status_code == 200, response.text

    received_features = mock_explain.call_args.kwargs["features"]
    assert received_features[FEATURE_NAMES[0]] == 0.0, "NaN should be replaced with 0.0"
    assert math.isfinite(received_features[FEATURE_NAMES[1]]), "+inf should be replaced with finite max"
    assert math.isfinite(received_features[FEATURE_NAMES[2]]), "-inf should be replaced with finite min"
