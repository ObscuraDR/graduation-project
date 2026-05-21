"""
Unit Tests – Feature Contract
==============================
Verifies that:
  1. FeatureExtractor returns exactly 20 named features.
  2. features.json and the extractor are perfectly aligned.
  3. Predictor.validate_feature_contract() raises FeatureContractError
     when a feature is missing from the provided dict.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.detection_engine.predictor import FeatureContractError, Predictor
from backend.feature_engine.feature_extractor import get_feature_extractor

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

EXPECTED_N_FEATURES = 20


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_feature_extractor_contract(features_json_path: Path) -> None:
    """
    Extractor must return exactly 20 features and every key must match
    the feature_names list in models/features.json (same order).
    """
    extractor = get_feature_extractor()
    extractor_names = extractor.get_feature_names()

    # 1. count
    assert len(extractor_names) == EXPECTED_N_FEATURES, (
        f"Expected {EXPECTED_N_FEATURES} features, got {len(extractor_names)}"
    )

    # 2. match features.json
    with open(features_json_path, encoding="utf-8") as fh:
        data = json.load(fh)

    json_names: list[str] = data["feature_names"]
    n_features_declared: int = data["n_features"]

    assert n_features_declared == EXPECTED_N_FEATURES
    assert len(json_names) == EXPECTED_N_FEATURES
    assert json_names == extractor_names, (
        "features.json and FeatureExtractor are out of sync.\n"
        f"JSON:      {json_names}\n"
        f"Extractor: {extractor_names}"
    )


@pytest.mark.unit
def test_predictor_offline_load(models_dir: Path) -> None:
    """
    ModelLoader must successfully load the three ensemble artifacts:
      ensemble.pkl, ensemble_scaler.pkl, ensemble_encoder.pkl
    """
    from backend.detection_engine.model_loader import ModelLoader

    loader = ModelLoader(model_dir=str(models_dir))
    ok = loader.load_from_directory(model_name="ensemble")

    assert ok is True, "load_from_directory() returned False – check model artifacts"
    assert loader.is_loaded, "ModelLoader.is_loaded should be True after load"
    assert loader.model is not None, "model object should not be None"
    assert loader.scaler is not None, "scaler should not be None"
    assert loader.label_encoder is not None, "label_encoder should not be None"


@pytest.mark.unit
def test_predictor_missing_feature_error(features_json_path: Path) -> None:
    """
    Predictor._validate_features() must raise FeatureContractError when a
    feature key is removed from the dict passed to it.
    """
    from backend.detection_engine.predictor import Predictor

    predictor = Predictor(features_path=str(features_json_path))

    # Build a valid feature dict, then drop one key
    full_features = {name: 0.0 for name in predictor.feature_names}
    removed_key = predictor.feature_names[0]  # e.g. "flow_duration"
    incomplete_features = {k: v for k, v in full_features.items() if k != removed_key}

    assert len(incomplete_features) == EXPECTED_N_FEATURES - 1

    with pytest.raises(FeatureContractError):
        predictor._validate_features(incomplete_features)


@pytest.mark.unit
def test_predictor_validates_n_features_mismatch(features_json_path: Path) -> None:
    """
    Predictor.validate_feature_contract() must raise FeatureContractError when
    n_features_declared does not match the length of feature_names.
    """
    extractor_names = get_feature_extractor().get_feature_names()

    with pytest.raises(FeatureContractError, match="n_features=99"):
        Predictor.validate_feature_contract(
            extractor_names,
            extractor_names,
            n_features_declared=99,
            source="test",
        )
