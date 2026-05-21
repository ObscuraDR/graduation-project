#!/usr/bin/env python3
"""
Smoke-test: verify the real trained model loads and predicts correctly.

Loads artifacts via ModelLoader.load_from_directory("ensemble"),
runs a prediction on a synthetic Flow, and prints attack_type + confidence.

Exit 0 on success, 1 on any failure.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.detection_engine.model_loader import ModelLoader
from backend.detection_engine.predictor import Predictor
from backend.feature_engine.feature_extractor import get_feature_extractor
from backend.flow_engine.flow_builder import Flow

MODEL_DIR = ROOT / "models"
FEATURES_JSON = MODEL_DIR / "features.json"


def build_synthetic_flow(attack_hint: str = "ddos") -> Flow:
    """Build a synthetic Flow that resembles a specific attack pattern."""
    flow = Flow("192.168.1.100", "10.0.0.1", 54321, 80, "tcp")

    if attack_hint == "ddos":
        # High packet rate, many SYN flags
        pkt = {
            "src_ip": "192.168.1.100", "dst_ip": "10.0.0.1",
            "src_port": 54321, "dst_port": 80, "protocol": "tcp",
            "length": 64,
            "tcp_flags": {"SYN": True, "FIN": False, "RST": False, "PSH": False, "ACK": False},
        }
        for _ in range(50):
            flow.add_packet(pkt)
    elif attack_hint == "portscan":
        # Small packets, many destinations
        for port in range(80, 130):
            pkt = {
                "src_ip": "192.168.1.100", "dst_ip": "10.0.0.1",
                "src_port": 54321, "dst_port": port, "protocol": "tcp",
                "length": 40,
                "tcp_flags": {"SYN": True, "FIN": False, "RST": False, "PSH": False, "ACK": False},
            }
            flow.add_packet(pkt)
    else:
        # Normal-ish traffic
        pkt = {
            "src_ip": "192.168.1.100", "dst_ip": "10.0.0.1",
            "src_port": 54321, "dst_port": 443, "protocol": "tcp",
            "length": 512,
            "tcp_flags": {"SYN": False, "FIN": False, "RST": False, "PSH": True, "ACK": True},
        }
        for _ in range(10):
            flow.add_packet(pkt)

    return flow


def verify() -> int:
    print("=" * 60)
    print("SMOKE TEST: verify_real_model.py")
    print("=" * 60)

    # 1. Check artifacts exist
    required = [
        MODEL_DIR / "ensemble.pkl",
        MODEL_DIR / "ensemble_scaler.pkl",
        MODEL_DIR / "ensemble_encoder.pkl",
        FEATURES_JSON,
    ]
    for path in required:
        if not path.exists():
            print(f"[FAIL] Missing artifact: {path.relative_to(ROOT)}")
            return 1
        print(f"[OK]   {path.relative_to(ROOT)}  ({path.stat().st_size:,} bytes)")

    # 2. Load model
    loader = ModelLoader(model_dir=str(MODEL_DIR))
    if not loader.load_from_directory("ensemble"):
        print("[FAIL] ModelLoader.load_from_directory('ensemble') returned False")
        return 1

    classes = loader.get_class_names()
    print(f"\n[OK]   Model loaded | classes: {classes}")

    # Reject dummy fallback classes
    if classes == ["Normal", "Attack"]:
        print("[FAIL] Encoder is using default fallback classes — real model not trained yet.")
        return 1

    # 3. Build predictor
    extractor = get_feature_extractor()
    predictor = Predictor(
        model_loader=loader,
        feature_extractor=extractor,
        features_path=str(FEATURES_JSON),
    )
    print(f"[OK]   Predictor ready | {len(predictor.feature_names)} features")

    # 4. Run predictions on three synthetic flows
    scenarios = [
        ("DDoS-like",    build_synthetic_flow("ddos")),
        ("PortScan-like", build_synthetic_flow("portscan")),
        ("Normal-like",  build_synthetic_flow("normal")),
    ]

    print("\nPredictions:")
    print("-" * 60)
    for label, flow in scenarios:
        result = predictor.predict_flow(flow)
        attack_type = result["attack_type"]
        confidence  = result["confidence"]
        severity    = result["severity"]
        print(f"  {label:<16} -> attack_type={attack_type:<12} confidence={confidence:.4f}  severity={severity}")

    # 5. Verify features.json contract
    with open(FEATURES_JSON) as f:
        contract = json.load(f)
    n = contract["n_features"]
    names = contract["feature_names"]
    if n != 20 or len(names) != 20:
        print(f"\n[FAIL] features.json declares {n} features, expected 20")
        return 1
    print(f"\n[OK]   features.json: {n} features, version={contract.get('version')}, "
          f"trained_with={contract.get('trained_with')}")

    print("\n" + "=" * 60)
    print("SMOKE TEST PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(verify())
