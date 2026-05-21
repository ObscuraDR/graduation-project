#!/usr/bin/env python3
"""
Offline validation for the ML inference pipeline (no packet sniffing).

Validates:
  - Required artifact files exist on disk
  - ModelLoader loads model + scaler + encoder (no silent fallback)
  - Predictor honors features.json order and feature contract
  - Prediction confidence in [0, 1]
  - attack_type is a label from the encoder
  - Missing feature keys raise FeatureContractError

Prints a single JSON report to stdout (thesis appendix). Exit 0 if all pass, 1 otherwise.
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.detection_engine.model_loader import ModelLoader
from backend.detection_engine.predictor import FeatureContractError, Predictor
from backend.feature_engine.feature_extractor import get_feature_extractor
from backend.flow_engine.flow_builder import Flow

MODEL_NAME = "ensemble"
MODEL_DIR = ROOT / "models"
FEATURES_JSON = MODEL_DIR / "features.json"
REQUIRED_ARTIFACTS = (
    MODEL_DIR / f"{MODEL_NAME}.pkl",
    MODEL_DIR / f"{MODEL_NAME}_scaler.pkl",
    MODEL_DIR / f"{MODEL_NAME}_encoder.pkl",
    FEATURES_JSON,
)


class ValidationFailure(Exception):
    """Raised when a validation step fails."""

    def __init__(self, message: str, report: dict | None = None):
        super().__init__(message)
        self.report = report


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _str_labels(classes: list) -> list[str]:
    return [str(c) for c in classes]


def _fail(report: dict, step: str, message: str) -> None:
    report["status"] = "failed"
    report["failed_step"] = step
    report["error"] = message
    report.setdefault("summary", {})["all_passed"] = False
    raise ValidationFailure(message, report=report)


def _check_artifacts_exist(report: dict) -> None:
    step = "artifact_files"
    artifacts: list[dict[str, Any]] = []
    missing: list[str] = []

    for path in REQUIRED_ARTIFACTS:
        exists = path.is_file()
        artifacts.append(
            {
                "path": str(path.relative_to(ROOT)),
                "exists": exists,
                "size_bytes": path.stat().st_size if exists else None,
            }
        )
        if not exists:
            missing.append(str(path.relative_to(ROOT)))

    report["checks"][step] = {
        "passed": len(missing) == 0,
        "artifacts": artifacts,
        "missing": missing,
    }

    if missing:
        _fail(
            report,
            step,
            f"Missing required artifact(s): {', '.join(missing)}",
        )


def _load_model_strict(report: dict) -> ModelLoader:
    step = "model_loader"
    loader = ModelLoader(model_dir=str(MODEL_DIR))

    if not loader.load_from_directory(MODEL_NAME):
        _fail(report, step, f"load_from_directory('{MODEL_NAME}') returned False")

    if loader.model is None:
        _fail(report, step, "Model object is None after load")
    if loader.scaler is None:
        _fail(
            report,
            step,
            f"{MODEL_NAME}_scaler.pkl was not loaded (would fall back to unscaled inference)",
        )
    if loader.label_encoder is None:
        _fail(
            report,
            step,
            f"{MODEL_NAME}_encoder.pkl was not loaded (would fall back to default class names)",
        )

    classes = _str_labels(loader.get_class_names())
    if classes == ["Normal", "Attack"]:
        _fail(
            report,
            step,
            "Encoder appears to use default fallback classes ['Normal', 'Attack']",
        )

    n_features_scaler = getattr(loader.scaler, "n_features_in_", None)
    if n_features_scaler is None and hasattr(loader.scaler, "mean_"):
        n_features_scaler = len(loader.scaler.mean_)

    report["checks"][step] = {
        "passed": True,
        "model_type": loader.model_type,
        "is_loaded": loader.is_loaded,
        "scaler_loaded": loader.scaler is not None,
        "encoder_loaded": loader.label_encoder is not None,
        "encoder_classes": classes,
        "encoder_n_classes": len(classes),
        "scaler_n_features": int(n_features_scaler) if n_features_scaler is not None else None,
    }
    return loader


def _validate_predictor_contract(report: dict, loader: ModelLoader) -> Predictor:
    step = "predictor_contract"
    extractor = get_feature_extractor()

    with open(FEATURES_JSON, encoding="utf-8") as f:
        features_meta = json.load(f)

    json_feature_names = list(features_meta["feature_names"])
    json_n_features = int(features_meta["n_features"])

    predictor = Predictor(
        model_loader=loader,
        feature_extractor=extractor,
        features_path=str(FEATURES_JSON),
    )

    if predictor.feature_names != json_feature_names:
        _fail(
            report,
            step,
            "Predictor feature order does not match features.json feature_names",
        )

    if len(predictor.feature_names) != json_n_features:
        _fail(
            report,
            step,
            f"Predictor has {len(predictor.feature_names)} features, features.json n_features={json_n_features}",
        )

    if predictor.feature_names != extractor.get_feature_names():
        _fail(
            report,
            step,
            "Predictor feature order does not match feature_extractor.py",
        )

    report["checks"][step] = {
        "passed": True,
        "features_path": str(FEATURES_JSON.relative_to(ROOT)),
        "n_features": len(predictor.feature_names),
        "feature_names": predictor.feature_names,
        "matches_extractor": True,
    }
    return predictor


def _build_sample_flow() -> Flow:
    flow = Flow("10.0.0.1", "10.0.0.2", 1234, 80, "tcp")
    packet = {
        "src_ip": "10.0.0.1",
        "dst_ip": "10.0.0.2",
        "src_port": 1234,
        "dst_port": 80,
        "protocol": "tcp",
        "length": 100,
        "tcp_flags": {
            "SYN": True,
            "FIN": False,
            "RST": False,
            "PSH": False,
            "ACK": True,
        },
    }
    for _ in range(15):
        flow.add_packet(packet)
    return flow


def _run_happy_path_inference(
    report: dict, predictor: Predictor, loader: ModelLoader
) -> None:
    step = "happy_path_inference"
    flow = _build_sample_flow()
    features = predictor.feature_extractor.extract_features(flow)

    # Strict vector build (same path as predict_flow, without model call)
    feature_vector = predictor._validate_features(features)

    result = predictor.predict_flow(flow)
    attack_type = str(result["attack_type"])
    confidence = float(result["confidence"])
    allowed_classes = _str_labels(loader.get_class_names())

    errors: list[str] = []
    if attack_type not in allowed_classes:
        errors.append(
            f"attack_type '{attack_type}' not in encoder classes {allowed_classes}"
        )
    if not (0.0 <= confidence <= 1.0):
        errors.append(f"confidence {confidence} is outside [0, 1]")
    if len(feature_vector) != len(predictor.feature_names):
        errors.append(
            f"feature vector length {len(feature_vector)} != {len(predictor.feature_names)}"
        )

    all_probs = result.get("all_probabilities") or {}
    if all_probs:
        prob_sum = sum(float(v) for v in all_probs.values())
        if not np.isclose(prob_sum, 1.0, atol=1e-3):
            errors.append(f"all_probabilities sum to {prob_sum:.6f}, expected ~1.0")
        for label, prob in all_probs.items():
            if not (0.0 <= float(prob) <= 1.0):
                errors.append(f"probability for '{label}' is {prob}, outside [0, 1]")

    report["checks"][step] = {
        "passed": len(errors) == 0,
        "errors": errors,
        "prediction": {
            "attack_type": attack_type,
            "confidence": confidence,
            "severity": result.get("severity"),
            "model_name": result.get("model_name"),
            "feature_vector_length": int(len(feature_vector)),
            "feature_order_source": str(Path(predictor.features_path).relative_to(ROOT)),
            "all_probabilities": {str(k): float(v) for k, v in all_probs.items()},
        },
    }

    if errors:
        _fail(report, step, "; ".join(errors))


def _run_missing_feature_test(report: dict, predictor: Predictor) -> None:
    step = "missing_feature_guard"
    flow = _build_sample_flow()
    features = predictor.feature_extractor.extract_features(flow)

    if not features:
        _fail(report, step, "Could not build feature dict from sample flow")

    # Remove one required key to simulate contract violation
    removed_key = predictor.feature_names[0]
    broken = dict(features)
    del broken[removed_key]

    raised: str | None = None

    try:
        predictor._validate_features(broken)
    except FeatureContractError as exc:
        raised = str(exc)
    except Exception as exc:
        _fail(
            report,
            step,
            f"Expected FeatureContractError, got {type(exc).__name__}: {exc}",
        )

    if raised is None:
        _fail(report, step, "Expected FeatureContractError but no exception was raised")

    # Predictor may report either explicit missing keys or a feature-count mismatch.
    key_absent = removed_key not in broken
    mentions_key = removed_key in raised
    count_mismatch = "expected 20" in raised and len(broken) == len(predictor.feature_names) - 1

    if not key_absent or not (mentions_key or count_mismatch):
        _fail(
            report,
            step,
            f"FeatureContractError did not clearly indicate missing '{removed_key}': {raised}",
        )

    report["checks"][step] = {
        "passed": True,
        "removed_feature": removed_key,
        "raised_error": raised,
        "guard_type": "explicit_missing_keys" if mentions_key else "feature_count_mismatch",
    }


def run_validation() -> dict:
    report: dict[str, Any] = {
        "validation": "offline_ml_inference",
        "status": "passed",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(ROOT),
        "model_name": MODEL_NAME,
        "checks": {},
        "failed_step": None,
        "error": None,
    }

    _check_artifacts_exist(report)
    loader = _load_model_strict(report)
    predictor = _validate_predictor_contract(report, loader)
    _run_happy_path_inference(report, predictor, loader)
    _run_missing_feature_test(report, predictor)

    report["summary"] = {
        "total_checks": len(report["checks"]),
        "passed_checks": sum(1 for c in report["checks"].values() if c.get("passed")),
        "all_passed": True,
    }
    return report


def main() -> int:
    report: dict[str, Any]
    try:
        report = run_validation()
    except ValidationFailure as exc:
        report = exc.report or {
            "validation": "offline_ml_inference",
            "status": "failed",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
            "checks": {},
            "summary": {"all_passed": False},
        }
        print(json.dumps(report, indent=2, default=_json_default))
        print(f"\nVALIDATION FAILED: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        report = {
            "validation": "offline_ml_inference",
            "status": "failed",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "failed_step": "unexpected_exception",
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "checks": {},
            "summary": {"all_passed": False},
        }
        print(json.dumps(report, indent=2, default=_json_default))
        print(f"\nVALIDATION FAILED (unexpected): {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, default=_json_default))
    print("\nVALIDATION PASSED: offline ML inference pipeline is consistent.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
