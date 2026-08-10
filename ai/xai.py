"""
Mô-đun Explainable AI (XAI) - Giải thích quyết định mô hình AI
==============================================================
Sử dụng thư viện SHAP (SHapley Additive exPlanations) với TreeExplainer để giải thích 
tại sao mô hình AI đưa ra cảnh báo tấn công cho một luồng dữ liệu mạng cụ thể.

Thiết kế & Tối ưu hóa:
-----------------------
* Sử dụng `shap.TreeExplainer` (tối ưu tốc độ cho mô hình cây như Random Forest / XGBoost).
* Bộ nhớ đệm Cache `_EXPLAINER_CACHE` theo từng mô hình giúp phản hồi tức thì (~1ms) ở các lần gọi tiếp theo.
* Cache thứ tự đặc trưng `_FEATURE_ORDER_CACHE` từ file `features.json`.
* Tách biệt hoàn toàn với pipeline bắt gói tin real-time, được gọi qua REST API `/api/xai/explain`.
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
# Bộ nhớ tạm (Cache) cấp mô-đun nhằm tránh khởi tạo lại Explainer cho mỗi request
# ---------------------------------------------------------------------------

_EXPLAINER_CACHE: Dict[str, shap.TreeExplainer] = {}
_FEATURE_ORDER_CACHE: Optional[List[str]] = None

# Đường dẫn mặc định đến file mô hình và cấu hình đặc trưng
_DEFAULT_FEATURES_JSON = Path("./backend/models/features.json")
_DEFAULT_MODELS_DIR = Path("./backend/models")


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

    # SHAP output format khác nhau giữa các versions:
    # - SHAP cũ (multi-class): list[n_classes] of (n_samples, n_features)
    # - SHAP mới (>=0.45, multi-class): np.ndarray shape (n_samples, n_features, n_classes)
    # - Binary/single: np.ndarray shape (n_samples, n_features)
    n_features = len(feature_order)

    if isinstance(raw_shap, list):
        # Format cũ: list theo class
        idx = predicted_idx if predicted_idx < len(raw_shap) else 0
        shap_for_pred = np.asarray(raw_shap[idx][0], dtype=np.float64).ravel()
    else:
        arr = np.asarray(raw_shap, dtype=np.float64)
        if arr.ndim == 3:
            # (n_samples, n_features, n_classes) → lấy sample 0, class predicted
            cls = predicted_idx if predicted_idx < arr.shape[2] else 0
            shap_for_pred = arr[0, :, cls].ravel()
        elif arr.ndim == 2:
            # (n_samples, n_features)
            shap_for_pred = arr[0].ravel()
        else:
            shap_for_pred = arr.ravel()

    # Đảm bảo đúng độ dài feature
    shap_for_pred = np.asarray(shap_for_pred, dtype=np.float64).ravel()[:n_features]

    # base_value: scalar hoặc per-class array
    ev = explainer.expected_value
    ev_arr = np.atleast_1d(np.asarray(ev, dtype=np.float64))
    if ev_arr.size > 1:
        base_value = float(ev_arr[predicted_idx] if predicted_idx < ev_arr.size else ev_arr[0])
    else:
        base_value = float(ev_arr[0])

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
