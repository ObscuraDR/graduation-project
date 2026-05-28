"""
Create Dummy Models
Generate ensemble artifacts for testing that match model_loader naming rules.

ModelLoader.load_from_directory("ensemble") expects:
  models/ensemble.pkl
  models/ensemble_scaler.pkl
  models/ensemble_encoder.pkl
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_DIR = Path("./backend/models")
FEATURES_JSON = MODEL_DIR / "features.json"
MODEL_NAME = "ensemble"

# Must match model_loader.load_from_directory("{name}") naming convention.
ARTIFACT_MODEL = MODEL_DIR / f"{MODEL_NAME}.pkl"
ARTIFACT_SCALER = MODEL_DIR / f"{MODEL_NAME}_scaler.pkl"
ARTIFACT_ENCODER = MODEL_DIR / f"{MODEL_NAME}_encoder.pkl"

CLASS_LABELS = [
    "Normal",
    "DDoS",
    "PortScan",
    "BruteForce",
    "Botnet",
    "Abnormal",
]

# Legacy filenames from older scripts — removed on each regenerate.
LEGACY_ARTIFACTS = [
    MODEL_DIR / "scaler.pkl",
    MODEL_DIR / "label_encoder.pkl",
    MODEL_DIR / "random_forest.pkl",
    MODEL_DIR / "xgboost.pkl",
    MODEL_DIR / "lstm.pkl",
]

N_SAMPLES_PER_CLASS = 80
RANDOM_STATE = 42


def load_n_features() -> int:
    """Read feature count from models/features.json (do not modify that file here)."""
    if not FEATURES_JSON.exists():
        raise FileNotFoundError(
            f"{FEATURES_JSON} not found. Run from project root after features.json exists."
        )
    with open(FEATURES_JSON, encoding="utf-8") as f:
        data = json.load(f)
    names = data.get("feature_names", [])
    n_features = data.get("n_features", len(names))
    if n_features != len(names):
        raise ValueError(
            f"{FEATURES_JSON}: n_features={n_features} but len(feature_names)={len(names)}"
        )
    return int(n_features)


def _build_training_data(n_features: int) -> tuple[np.ndarray, np.ndarray]:
    """Synthetic scaled-ready features and string labels for all classes."""
    rng = np.random.default_rng(RANDOM_STATE)
    rows: list[np.ndarray] = []
    labels: list[str] = []

    for class_index, label in enumerate(CLASS_LABELS):
        # Slightly different distributions per class so the dummy model can learn.
        base = rng.normal(loc=class_index * 0.35, scale=1.0, size=(N_SAMPLES_PER_CLASS, n_features))
        if label != "Normal":
            base[:, :4] += rng.uniform(2.0, 6.0, size=(N_SAMPLES_PER_CLASS, 4))
        rows.append(base.astype(np.float64))
        labels.extend([label] * N_SAMPLES_PER_CLASS)

    X = np.vstack(rows)
    y = np.array(labels)
    perm = rng.permutation(len(y))
    return X[perm], y[perm]


def _remove_legacy_artifacts() -> None:
    for path in LEGACY_ARTIFACTS:
        if path.exists():
            path.unlink()
            logger.info("Removed legacy artifact: %s", path.name)


def create_dummy_models(model_dir: Path | None = None) -> None:
    """
    Write ensemble.pkl, ensemble_scaler.pkl, and ensemble_encoder.pkl.

    The classifier is trained on StandardScaler-transformed features and
    LabelEncoder-encoded integer labels.
    """
    global MODEL_DIR, ARTIFACT_MODEL, ARTIFACT_SCALER, ARTIFACT_ENCODER, LEGACY_ARTIFACTS

    if model_dir is not None:
        MODEL_DIR = Path(model_dir)
        ARTIFACT_MODEL = MODEL_DIR / f"{MODEL_NAME}.pkl"
        ARTIFACT_SCALER = MODEL_DIR / f"{MODEL_NAME}_scaler.pkl"
        ARTIFACT_ENCODER = MODEL_DIR / f"{MODEL_NAME}_encoder.pkl"
        LEGACY_ARTIFACTS = [
            MODEL_DIR / "scaler.pkl",
            MODEL_DIR / "label_encoder.pkl",
            MODEL_DIR / "random_forest.pkl",
            MODEL_DIR / "xgboost.pkl",
            MODEL_DIR / "lstm.pkl",
        ]

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    n_features = load_n_features()
    logger.info("Using n_features=%d from %s", n_features, FEATURES_JSON)

    X_raw, y_strings = _build_training_data(n_features)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)

    label_encoder = LabelEncoder()
    label_encoder.fit(CLASS_LABELS)
    y_encoded = label_encoder.transform(y_strings)

    if len(label_encoder.classes_) != len(CLASS_LABELS):
        raise RuntimeError("LabelEncoder class count mismatch")

    classifier = RandomForestClassifier(
        n_estimators=50,
        max_depth=12,
        random_state=RANDOM_STATE,
        class_weight="balanced",
    )
    classifier.fit(X_scaled, y_encoded)

    # Sanity checks before writing artifacts.
    probe = X_raw[:1]
    probe_scaled = scaler.transform(probe)
    pred = classifier.predict(probe_scaled)
    proba = classifier.predict_proba(probe_scaled)
    if probe_scaled.shape[1] != n_features:
        raise RuntimeError(
            f"Scaler output has {probe_scaled.shape[1]} features, expected {n_features}"
        )
    if proba.shape[1] != len(CLASS_LABELS):
        raise RuntimeError(
            f"Model predicts {proba.shape[1]} classes, expected {len(CLASS_LABELS)}"
        )
    if int(pred[0]) >= len(CLASS_LABELS):
        raise RuntimeError(f"Invalid predicted class index: {pred[0]}")

    _remove_legacy_artifacts()

    joblib.dump(classifier, ARTIFACT_MODEL)
    joblib.dump(scaler, ARTIFACT_SCALER)
    joblib.dump(label_encoder, ARTIFACT_ENCODER)

    logger.info("Created %s", ARTIFACT_MODEL.name)
    logger.info("Created %s", ARTIFACT_SCALER.name)
    logger.info("Created %s", ARTIFACT_ENCODER.name)
    logger.info("Classes: %s", list(label_encoder.classes_))
    logger.info(
        "Probe prediction: %s (index=%s, confidence=%.4f)",
        label_encoder.inverse_transform(pred)[0],
        pred[0],
        float(proba.max()),
    )
    logger.info(
        "\nAll ensemble artifacts created. "
        "These are dummy models for testing only — train on real data for production."
    )


if __name__ == "__main__":
    create_dummy_models()
