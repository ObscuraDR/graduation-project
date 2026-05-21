"""
Explainable AI (XAI) Module
============================
SHAP-based feature explanations for Z-Sentinel IDS ensemble model.

Design decisions
----------------
* Only ``shap.TreeExplainer`` is used (fast, exact, tree-native).
* One explainer instance is cached per ``model_name`` in ``_EXPLAINER_CACHE``
  so repeated calls within a server session are ~1 ms after warm-up.
* Feature order is loaded once and cached in ``_FEATURE_ORDER_CACHE``.
* This module is **completely decoupled** from the real-time sniffer
  pipeline and is called only from ``backend/api/routes/xai.py``.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import shap
from sklearn.ensemble import RandomForestClassifier, VotingClassifier

from backend.detection_engine.model_loader import ModelLoader

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level caches  (avoids re-initialising the explainer on every request)
# ---------------------------------------------------------------------------

_EXPLAINER_CACHE: Dict[str, shap.TreeExplainer] = {}
_FEATURE_ORDER_CACHE: Optional[List[str]] = None

# Default features.json location (relative to project root)
_DEFAULT_FEATURES_JSON = Path("./models/features.json")
_DEFAULT_MODELS_DIR = Path("./models")


# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------


class UnsupportedModelError(ValueError):
    """Raised when the loaded model does not support TreeExplainer."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_feature_order(features_path: Path = _DEFAULT_FEATURES_JSON) -> List[str]:
    """Load and cache the feature name list from ``features.json``."""
    global _FEATURE_ORDER_CACHE

    if _FEATURE_ORDER_CACHE is not None:
        return _FEATURE_ORDER_CACHE

    if not features_path.exists():
        raise FileNotFoundError(f"features.json not found at {features_path}")

    with open(features_path, encoding="utf-8") as fh:
        data = json.load(fh)

    feature_names: List[str] = data.get("feature_names", [])
    if not feature_names:
        raise ValueError("features.json: 'feature_names' is empty or missing")

    _FEATURE_ORDER_CACHE = feature_names
    logger.debug("Feature order cached: %d features", len(_FEATURE_ORDER_CACHE))
    return _FEATURE_ORDER_CACHE


def _get_raw_classifier(model: Any) -> Any:
    """
    Drill through VotingClassifier wrappers to find the first
    RandomForestClassifier-compatible estimator that SHAP TreeExplainer
    can handle natively.

    Returns the raw classifier, or raises ``UnsupportedModelError``.
    """
    # Case 1: direct RF or any tree estimator
    if isinstance(model, RandomForestClassifier):
        return model

    # Case 2: VotingClassifier wrapping multiple estimators
    if isinstance(model, VotingClassifier):
        for _name, estimator in model.estimators_:
            if isinstance(estimator, RandomForestClassifier):
                return estimator
        # Fall through – try the VotingClassifier itself
        # (some versions expose predict_proba and SHAP can wrap it)

    # Case 3: joblib bundle dict (ensemble.pkl stores a raw dict)
    # already unwrapped by ModelLoader.model → this branch is for safety
    if hasattr(model, "estimators_"):
        for est in model.estimators_:
            if isinstance(est, RandomForestClassifier):
                return est

    raise UnsupportedModelError(
        f"Model type '{type(model).__name__}' is not supported by SHAP TreeExplainer. "
        "Only RandomForestClassifier (or VotingClassifier wrapping one) is supported."
    )


def _build_explainer(model_name: str, models_dir: Path) -> shap.TreeExplainer:
    """
    Load model artifacts and build a cached SHAP TreeExplainer.

    The explainer is associated with the raw RandomForestClassifier
    extracted from the ensemble pickle.
    """
    loader = ModelLoader(model_dir=str(models_dir))
    ok = loader.load_from_directory(model_name=model_name)
    if not ok or loader.model is None:
        raise RuntimeError(
            f"Failed to load model artifacts for '{model_name}' "
            f"from {models_dir}. Check that {model_name}.pkl, "
            f"{model_name}_scaler.pkl, and {model_name}_encoder.pkl exist."
        )

    raw_clf = _get_raw_classifier(loader.model)

    logger.info(
        "Building SHAP TreeExplainer for model '%s' (raw type: %s)",
        model_name,
        type(raw_clf).__name__,
    )
    t0 = time.perf_counter()
    explainer = shap.TreeExplainer(raw_clf)
    logger.info(
        "SHAP TreeExplainer ready for '%s' in %.3fs", model_name, time.perf_counter() - t0
    )
    return explainer


def get_explainer(
    model_name: str = "ensemble",
    models_dir: Path = _DEFAULT_MODELS_DIR,
) -> Tuple[shap.TreeExplainer, ModelLoader]:
    """
    Return a cached SHAP TreeExplainer and a fully loaded ModelLoader for
    ``model_name``.  The explainer is built once per server lifetime.
    """
    if model_name not in _EXPLAINER_CACHE:
        explainer = _build_explainer(model_name, models_dir)
        _EXPLAINER_CACHE[model_name] = explainer
        logger.info("Explainer cached for model '%s'", model_name)

    # Always return a fresh ModelLoader for inference (cheap – no retraining)
    loader = ModelLoader(model_dir=str(models_dir))
    loader.load_from_directory(model_name=model_name)

    return _EXPLAINER_CACHE[model_name], loader


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def explain(
    features: Dict[str, float],
    model_name: str = "ensemble",
    top_n: int = 5,
    models_dir: Path = _DEFAULT_MODELS_DIR,
    features_path: Path = _DEFAULT_FEATURES_JSON,
) -> Dict[str, Any]:
    """
    Generate a SHAP explanation for a single feature vector.

    Parameters
    ----------
    features:
        Exactly 20 features in any order; values must already be
        NaN/inf-cleaned (the API route performs that step).
    model_name:
        Key for the model artifacts (e.g. ``"ensemble"``).
    top_n:
        Number of top-|SHAP| features to surface in ``top_features``.
    models_dir:
        Directory that contains the pkl artifacts.
    features_path:
        Path to ``features.json`` for canonical feature order.

    Returns
    -------
    dict with keys:
        model_name, predicted_label, confidence, probabilities,
        base_value, top_features, shap_values
    """
    feature_order = _load_feature_order(features_path)

    # ── Build the input vector in canonical order ────────────────────────────
    x = np.array([features[name] for name in feature_order], dtype=np.float64).reshape(1, -1)

    # ── Get explainer + loader ───────────────────────────────────────────────
    explainer, loader = get_explainer(model_name=model_name, models_dir=models_dir)

    # ── Run inference (using ModelLoader which applies scaler) ───────────────
    predicted_classes = loader.predict(x.copy())          # scaler applied inside
    probabilities_raw = loader.predict_proba(x.copy())    # scaler applied inside

    predicted_idx = int(predicted_classes[0])
    class_names = loader.get_class_names()
    predicted_label = (
        class_names[predicted_idx] if predicted_idx < len(class_names) else "Unknown"
    )
    confidence = float(probabilities_raw[0][predicted_idx])
    prob_dict = {
        class_names[i]: float(p) for i, p in enumerate(probabilities_raw[0])
    }

    # ── SHAP values (on scaled input) ────────────────────────────────────────
    # ModelLoader.predict already calls scaler.transform; we must replicate
    # that for SHAP so the values align with what the model received.
    x_scaled = loader.scaler.transform(x) if loader.scaler else x

    t0 = time.perf_counter()
    raw_shap = explainer.shap_values(x_scaled)
    logger.debug("SHAP values computed in %.3fs", time.perf_counter() - t0)

    # raw_shap: list[n_classes] of shape (1, n_features)  or  (1, n_features)
    if isinstance(raw_shap, list):
        # Multi-class RF → use the predicted class slice
        shap_for_pred = np.array(raw_shap[predicted_idx][0])
    else:
        shap_for_pred = np.array(raw_shap[0])

    # base_value: scalar or per-class array
    ev = explainer.expected_value
    if isinstance(ev, (list, np.ndarray)):
        base_value = float(ev[predicted_idx])
    else:
        base_value = float(ev)

    # ── Assemble response payload ─────────────────────────────────────────────
    shap_dict = {
        name: float(shap_for_pred[i]) for i, name in enumerate(feature_order)
    }

    abs_shap = np.abs(shap_for_pred)
    top_indices = np.argsort(abs_shap)[::-1][:top_n]
    top_features = [
        {
            "feature": feature_order[i],
            "value": float(features[feature_order[i]]),
            "shap_value": float(shap_for_pred[i]),
        }
        for i in top_indices
    ]

    return {
        "model_name": model_name,
        "predicted_label": predicted_label,
        "confidence": confidence,
        "probabilities": prob_dict,
        "base_value": base_value,
        "top_features": top_features,
        "shap_values": shap_dict,
    }
