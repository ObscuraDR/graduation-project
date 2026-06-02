"""
Build a small, committable "golden" attack-sample CSV for the live-attack demo.

Why:
    The full CICIDS2017 processed dataset is large and git-ignored, so it is not
    available on a fresh checkout. This script distils it into a tiny CSV
    (a handful of rows per attack class) containing ONLY flows that the CURRENT
    ensemble model classifies correctly with high confidence. The demo replay
    engine streams these rows, guaranteeing reliable, reproducible real-time
    alerts during a thesis defense without needing the full dataset or live
    packet capture.

Usage (from repo root, full dataset present):
    python -m backend.demo.build_attack_samples
    python -m backend.demo.build_attack_samples --per-class 8 --min-confidence 0.85

Output:
    backend/demo/attack_samples.csv   (committed, ~tens of KB)
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("build_attack_samples")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = REPO_ROOT / "backend" / "data" / "cicids2017_processed.csv"
DEFAULT_OUTPUT = REPO_ROOT / "backend" / "demo" / "attack_samples.csv"
FEATURES_JSON = REPO_ROOT / "backend" / "models" / "features.json"
LABEL_COLUMN = "Label"

# Attack classes we want to demonstrate (Normal is excluded — we want alerts).
DEMO_ATTACK_CLASSES = ["DDoS", "PortScan", "BruteForce", "Botnet", "Abnormal"]


def load_feature_names() -> List[str]:
    with open(FEATURES_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data["feature_names"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Build golden attack-sample CSV for the demo.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET,
                        help="Path to processed CICIDS2017 CSV (with Label column).")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Output curated CSV path.")
    parser.add_argument("--per-class", type=int, default=8,
                        help="Max correctly-classified samples to keep per attack class.")
    parser.add_argument("--min-confidence", type=float, default=0.80,
                        help="Minimum model confidence required to keep a sample.")
    parser.add_argument("--scan-rows", type=int, default=20000,
                        help="Max rows to score per class while searching (perf cap).")
    args = parser.parse_args()

    if not args.dataset.exists():
        logger.error("Dataset not found: %s", args.dataset)
        logger.error("This builder needs the full processed dataset. Run preprocessing first.")
        return 1

    # Import here so the module import is cheap when only the replay engine is used.
    from backend.detection_engine.model_loader import get_model_loader
    from backend.detection_engine.predictor import get_predictor

    feature_names = load_feature_names()
    logger.info("Loaded %d feature names from contract", len(feature_names))

    model_loader = get_model_loader()
    if not model_loader.load_from_directory("ensemble"):
        logger.error("Failed to load ensemble model from backend/models/")
        return 1
    predictor = get_predictor(model_loader=model_loader)
    class_names = model_loader.get_class_names()
    logger.info("Model loaded. Classes: %s", class_names)

    logger.info("Loading dataset: %s", args.dataset)
    df = pd.read_csv(args.dataset, low_memory=False)
    logger.info("Dataset shape: %s", df.shape)

    if LABEL_COLUMN not in df.columns:
        logger.error("Dataset missing '%s' column", LABEL_COLUMN)
        return 1

    kept_frames: List[pd.DataFrame] = []
    summary = {}

    for attack_class in DEMO_ATTACK_CLASSES:
        if attack_class not in class_names:
            logger.warning("Class %s not in model classes; skipping", attack_class)
            continue

        class_rows = df[df[LABEL_COLUMN] == attack_class]
        if class_rows.empty:
            logger.warning("No rows labelled %s in dataset; skipping", attack_class)
            continue

        # Cap the scan for performance; shuffle for representativeness.
        scan = class_rows.sample(
            n=min(len(class_rows), args.scan_rows),
            random_state=42,
        )

        scored = []
        for _, row in scan.iterrows():
            features = {name: float(row[name]) for name in feature_names}
            try:
                pred = predictor.predict_features(features)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Prediction failed for a %s row: %s", attack_class, exc)
                continue
            if pred["attack_type"] == attack_class and pred["confidence"] >= args.min_confidence:
                scored.append((pred["confidence"], features))

        if not scored:
            logger.warning(
                "No %s rows classified correctly at confidence >= %.2f (scanned %d). "
                "Lower --min-confidence to include this class.",
                attack_class, args.min_confidence, len(scan),
            )
            summary[attack_class] = 0
            continue

        # Highest-confidence first, keep top N.
        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[: args.per_class]
        frame = pd.DataFrame([feat for _, feat in top], columns=feature_names)
        frame[LABEL_COLUMN] = attack_class
        kept_frames.append(frame)
        summary[attack_class] = len(top)
        logger.info(
            "%-12s kept %d/%d (best conf %.3f, worst kept %.3f)",
            attack_class, len(top), len(scored), top[0][0], top[-1][0],
        )

    if not kept_frames:
        logger.error("No samples kept for any class. Demo CSV not written.")
        return 1

    out = pd.concat(kept_frames, ignore_index=True)
    out = out[feature_names + [LABEL_COLUMN]]  # enforce column order
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)

    logger.info("=" * 60)
    logger.info("Wrote %d curated attack samples -> %s", len(out), args.output)
    for cls, n in summary.items():
        logger.info("  %-12s %d", cls, n)
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
