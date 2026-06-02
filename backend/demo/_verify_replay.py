"""
Offline end-to-end verification for the live-attack replay demo.

Runs the curated attack_samples.csv through the SAME inference + alert path the
WebSocket demo uses (predict_features -> is_attack -> AlertManager.generate_alert
-> broadcast bridge), but with DB/email side effects disabled and a fake bridge
that simply records broadcast alerts. This proves the pipeline emits real-time
alerts without needing a running server, database, or Redis.

Run (with the demo venv so the pickled models deserialize):
    .venv_demo\\Scripts\\python.exe -m backend.demo._verify_replay
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES = Path(__file__).resolve().parent / "attack_samples.csv"
FEATURES_JSON = REPO_ROOT / "backend" / "models" / "features.json"


class FakeBridge:
    """Stand-in for AlertBroadcastBridge: records what would be broadcast."""

    def __init__(self) -> None:
        self.alerts = []

    def enqueue_alert(self, alert) -> bool:
        self.alerts.append(alert)
        return True


def main() -> int:
    from backend.detection_engine.model_loader import get_model_loader
    from backend.detection_engine.predictor import get_predictor
    from backend.alert_engine.alert_manager import AlertManager

    with open(FEATURES_JSON, "r", encoding="utf-8") as f:
        feature_names = list(json.load(f)["feature_names"])

    if not SAMPLES.exists():
        print(f"FAIL: curated samples not found at {SAMPLES}")
        return 1

    model_loader = get_model_loader()
    if not model_loader.load_from_directory("ensemble"):
        print("FAIL: could not load ensemble model")
        return 1
    predictor = get_predictor(model_loader=model_loader)

    # Isolated AlertManager: no DB, no email; capture broadcasts via fake bridge.
    bridge = FakeBridge()
    alert_manager = AlertManager(
        enable_db_save=False,
        enable_websocket=True,
        enable_email=False,
    )
    alert_manager.set_broadcast_bridge(bridge)

    df = pd.read_csv(SAMPLES, low_memory=False)

    total = 0
    detected = 0
    correct_class = 0
    per_class_detected: Counter = Counter()
    per_class_total: Counter = Counter()

    for index, row in df.iterrows():
        label = str(row["Label"])
        features = {name: float(row[name]) for name in feature_names}
        per_class_total[label] += 1
        total += 1

        prediction = predictor.predict_features(features)
        if prediction["attack_type"] == label:
            correct_class += 1

        if predictor.is_attack(prediction):
            detected += 1
            # Unique src IP per flow so per-IP cooldown does not suppress.
            flow_info = {
                "src_ip": f"203.0.113.{(index % 254) + 1}",
                "dst_ip": "192.0.2.100",
                "src_port": 40000 + int(index),
                "dst_port": 80,
                "protocol": "tcp",
                "flow_key": f"verify-{label}-{index}",
                "is_demo": True,
            }
            alert = alert_manager.generate_alert(prediction, flow_info)
            if alert:
                per_class_detected[label] += 1

    print("=" * 60)
    print("REPLAY PIPELINE VERIFICATION")
    print("=" * 60)
    print(f"samples replayed     : {total}")
    print(f"classified correctly : {correct_class}/{total}")
    print(f"flagged as attack    : {detected}/{total}")
    print(f"alerts broadcast     : {len(bridge.alerts)}")
    print("-" * 60)
    print("per-class alerts broadcast:")
    for cls in sorted(per_class_total):
        print(f"  {cls:<12} {per_class_detected[cls]}/{per_class_total[cls]}")
    print("=" * 60)

    # Sanity: every curated sample should broadcast an alert.
    ok = len(bridge.alerts) == total and correct_class == total
    print("RESULT:", "PASS" if ok else "PARTIAL")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
