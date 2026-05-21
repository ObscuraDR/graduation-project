#!/usr/bin/env python3
"""
Validate that models/features.json matches backend/feature_engine/feature_extractor.py.
Exit 0 on success, 1 on mismatch.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.detection_engine.predictor import FeatureContractError, Predictor
from backend.feature_engine.feature_extractor import get_feature_extractor

FEATURES_JSON = ROOT / "models" / "features.json"


def main() -> int:
    extractor_names = get_feature_extractor().get_feature_names()

    with open(FEATURES_JSON, encoding="utf-8") as f:
        data = json.load(f)

    feature_names = data.get("feature_names", [])
    n_features = data.get("n_features")

    try:
        Predictor.validate_feature_contract(
            feature_names,
            extractor_names,
            n_features_declared=n_features,
            source=str(FEATURES_JSON),
        )
        Predictor(features_path=str(FEATURES_JSON))
    except FeatureContractError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    print(f"OK: {len(feature_names)} features aligned with feature_extractor.py")
    print("Feature order:")
    for i, name in enumerate(feature_names):
        print(f"  {i:2d}. {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
