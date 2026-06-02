"""
Live-attack demo replay engine.

Streams REAL labelled CICIDS2017 attack flows through the SAME inference and
alerting path used by the live sniffer pipeline:

    dataset row (20 features)
        -> Predictor.predict_features()      (same model + scaler + classes)
        -> Predictor.is_attack()             (same confidence gate)
        -> AlertManager.generate_alert()     (same cooldown/correlation/DB/email)
        -> AlertBroadcastBridge.enqueue_alert()
        -> WebSocket /ws -> frontend Overview "Live Alert Feed"

This gives a deterministic, privilege-free, tool-free demonstration of
end-to-end real-time detection + WebSocket broadcast for the thesis defense.
Every alert shown is the actual ensemble model classifying a genuine,
labelled attack flow — nothing is faked.

Safety:
    - Disabled by default. Enable with ENABLE_DEMO_REPLAY=true.
    - The API surface that drives it is API-key protected.
    - Source IPs are synthetic, lab-style addresses so demo alerts are easy to
      distinguish from real captured traffic.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLES_CSV = Path(__file__).resolve().parent / "attack_samples.csv"
LABEL_COLUMN = "Label"

# Synthetic, clearly-fake attacker IPs per class so demo alerts are obvious.
# (RFC 5737 TEST-NET / documentation ranges — never real hosts.)
DEMO_SRC_IPS = {
    "DDoS": "203.0.113.10",
    "PortScan": "203.0.113.20",
    "BruteForce": "203.0.113.30",
    "Botnet": "203.0.113.40",
    "Abnormal": "203.0.113.50",
}
DEMO_DST_IP = "192.0.2.100"  # synthetic "victim" host
DEMO_DST_PORTS = {
    "DDoS": 80,
    "PortScan": 0,  # scans hit many ports; 0 = unspecified
    "BruteForce": 22,
    "Botnet": 8080,
    "Abnormal": 443,
}


@dataclass
class ReplayStats:
    """Running statistics for a replay session."""

    running: bool = False
    samples_total: int = 0
    replayed: int = 0
    detected_attacks: int = 0
    alerts_broadcast: int = 0
    suppressed: int = 0  # below confidence / cooldown / whitelist
    by_class: Dict[str, int] = field(default_factory=dict)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    last_error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "samples_total": self.samples_total,
            "replayed": self.replayed,
            "detected_attacks": self.detected_attacks,
            "alerts_broadcast": self.alerts_broadcast,
            "suppressed": self.suppressed,
            "by_class": dict(self.by_class),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "last_error": self.last_error,
        }


class AttackReplayDemo:
    """Replays curated attack flows through the real detection/alert pipeline."""

    def __init__(self, samples_csv: Optional[Path] = None):
        self.samples_csv = Path(samples_csv) if samples_csv else DEFAULT_SAMPLES_CSV
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.stats = ReplayStats()
        self._feature_names: Optional[List[str]] = None

    # ── public API ────────────────────────────────────────────────────────────
    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            self.stats.running = self.is_running
            return self.stats.as_dict()

    def start(
        self,
        rounds: int = 1,
        delay_sec: float = 1.0,
        classes: Optional[List[str]] = None,
        shuffle: bool = False,
        unique_src: bool = True,
    ) -> Dict[str, Any]:
        """
        Start replaying curated attack samples in a background thread.

        Args:
            rounds: How many times to loop over the sample set.
            delay_sec: Delay between consecutive replayed flows (paces the demo).
            classes: Optional subset of attack classes to replay.
            shuffle: Randomise sample order each round.
            unique_src: Vary attacker source IP per flow so the AlertManager
                per-IP cooldown does not suppress the live stream.

        Returns:
            A status dict (also raises ValueError on misconfiguration).
        """
        if self.is_running:
            return {"status": "error", "message": "Replay already running"}

        samples = self._load_samples(classes=classes)
        if not samples:
            raise ValueError(
                f"No demo samples available (looked in {self.samples_csv}). "
                "Run `python -m backend.demo.build_attack_samples` first."
            )

        # Reset stats for the new session.
        with self._lock:
            self.stats = ReplayStats()
            self.stats.samples_total = len(samples) * max(1, rounds)

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(samples, rounds, delay_sec, shuffle, unique_src),
            name="attack-replay-demo",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Attack replay demo started (samples=%d, rounds=%d, delay=%.2fs, unique_src=%s)",
            len(samples), rounds, delay_sec, unique_src,
        )
        return {
            "status": "success",
            "message": "Attack replay started",
            "samples_per_round": len(samples),
            "rounds": rounds,
            "delay_sec": delay_sec,
            "unique_src": unique_src,
        }

    def stop(self) -> Dict[str, Any]:
        """Signal the replay thread to stop and wait briefly for it to finish."""
        if not self.is_running:
            return {"status": "error", "message": "Replay is not running"}
        self._stop_event.set()
        self._thread.join(timeout=5.0)  # type: ignore[union-attr]
        logger.info("Attack replay demo stopped")
        return {"status": "success", "message": "Attack replay stopped"}

    # ── internals ───────────────────────────────────────────────────────────--
    def _load_samples(self, classes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Load curated samples CSV into a list of {features, label} dicts."""
        if not self.samples_csv.exists():
            logger.error("Demo samples CSV not found: %s", self.samples_csv)
            return []

        import pandas as pd

        feature_names = self._load_feature_names()
        df = pd.read_csv(self.samples_csv, low_memory=False)

        missing = [c for c in feature_names + [LABEL_COLUMN] if c not in df.columns]
        if missing:
            logger.error("Demo samples CSV missing columns: %s", missing)
            return []

        if classes:
            df = df[df[LABEL_COLUMN].isin(classes)]

        samples: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            features = {name: float(row[name]) for name in feature_names}
            samples.append({"features": features, "label": str(row[LABEL_COLUMN])})
        return samples

    def _load_feature_names(self) -> List[str]:
        if self._feature_names is not None:
            return self._feature_names
        import json

        features_json = REPO_ROOT / "backend" / "models" / "features.json"
        with open(features_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._feature_names = list(data["feature_names"])
        return self._feature_names

    def _build_flow_info(
        self,
        label: str,
        features: Dict[str, float],
        index: int,
        unique_src: bool,
    ) -> Dict[str, Any]:
        """
        Construct the flow_info dict AlertManager expects for an alert.

        When ``unique_src`` is True the source IP varies per flow (a /24 of
        attackers per class). This both reflects real DDoS/scan/botnet
        behaviour and avoids the AlertManager per-IP cooldown silently
        suppressing every alert after the first, so the demo shows a live
        stream on the Overview page.
        """
        base_ip = DEMO_SRC_IPS.get(label, "203.0.113.99")
        if unique_src:
            prefix = base_ip.rsplit(".", 1)[0]
            src_ip = f"{prefix}.{(index % 254) + 1}"
        else:
            src_ip = base_ip
        dst_port = DEMO_DST_PORTS.get(label, 0)
        return {
            "src_ip": src_ip,
            "dst_ip": DEMO_DST_IP,
            "src_port": random.randint(1024, 65535),
            "dst_port": dst_port,
            "protocol": "tcp",
            "flow_key": f"demo-{label}-{src_ip}:{dst_port}",
            "is_demo": True,
        }

    def _run(
        self,
        samples: List[Dict[str, Any]],
        rounds: int,
        delay_sec: float,
        shuffle: bool,
        unique_src: bool,
    ) -> None:
        """Background worker: replay each sample through the real pipeline."""
        from datetime import datetime

        # Import inside the thread so import errors surface in stats, not at module load.
        try:
            from backend.detection_engine.model_loader import get_model_loader
            from backend.detection_engine.predictor import get_predictor
            from backend.alert_engine.alert_manager import get_alert_manager
            from backend.api.websocket import get_broadcast_bridge

            model_loader = get_model_loader()
            if not model_loader.is_loaded:
                model_loader.load_from_directory("ensemble")
            predictor = get_predictor(model_loader=model_loader)
            alert_manager = get_alert_manager()
            # Ensure alerts can reach the WebSocket even if no sniffer was started.
            if alert_manager.broadcast_bridge is None:
                alert_manager.set_broadcast_bridge(get_broadcast_bridge())
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Replay worker failed to initialise: %s", exc)
            with self._lock:
                self.stats.last_error = f"init failed: {exc}"
            return

        with self._lock:
            self.stats.started_at = datetime.utcnow().isoformat()

        try:
            flow_index = 0
            for round_idx in range(max(1, rounds)):
                if self._stop_event.is_set():
                    break

                order = list(samples)
                if shuffle:
                    random.shuffle(order)

                for sample in order:
                    if self._stop_event.is_set():
                        break

                    label = sample["label"]
                    features = sample["features"]
                    flow_index += 1

                    try:
                        prediction = predictor.predict_features(features)
                    except Exception as exc:
                        logger.error("Replay prediction error (%s): %s", label, exc)
                        with self._lock:
                            self.stats.last_error = str(exc)
                        continue

                    with self._lock:
                        self.stats.replayed += 1
                        self.stats.by_class[label] = self.stats.by_class.get(label, 0) + 1

                    if predictor.is_attack(prediction):
                        with self._lock:
                            self.stats.detected_attacks += 1

                        flow_info = self._build_flow_info(
                            label, features, flow_index, unique_src
                        )
                        alert = alert_manager.generate_alert(prediction, flow_info)
                        if alert:
                            with self._lock:
                                self.stats.alerts_broadcast += 1
                            logger.info(
                                "DEMO ALERT: %s from %s (pred=%s conf=%.2f sev=%s)",
                                label,
                                flow_info["src_ip"],
                                prediction["attack_type"],
                                prediction["confidence"],
                                alert["severity"],
                            )
                        else:
                            # Suppressed by cooldown/whitelist/threshold.
                            with self._lock:
                                self.stats.suppressed += 1
                    else:
                        with self._lock:
                            self.stats.suppressed += 1

                    if delay_sec > 0:
                        self._stop_event.wait(delay_sec)
        finally:
            with self._lock:
                self.stats.finished_at = datetime.utcnow().isoformat()
                self.stats.running = False
            logger.info(
                "Replay finished: replayed=%d detected=%d broadcast=%d suppressed=%d",
                self.stats.replayed,
                self.stats.detected_attacks,
                self.stats.alerts_broadcast,
                self.stats.suppressed,
            )


# Singleton
_demo_instance: Optional[AttackReplayDemo] = None


def get_attack_replay_demo() -> AttackReplayDemo:
    global _demo_instance
    if _demo_instance is None:
        _demo_instance = AttackReplayDemo()
    return _demo_instance
