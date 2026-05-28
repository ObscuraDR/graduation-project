"""
Integration Tests – IDS Pipeline (no real sniffer / server / SMTP)
===================================================================

Coverage
--------
A. Flow → Feature extraction → Prediction (end-to-end, in-process)
B. Alert generation when confidence >= threshold
C. AlertManager writes alerts via repository (DB insert verified on SQLite)
D. WebSocket broadcast bridge enqueue_alert is triggered
E. Email dispatch triggered ONLY for high/critical + confidence >= 0.85
F. Pipeline coordinator – once mode
G. Repository layer – direct SQLite insert
H. Pipeline coordinator – window mode

Strategy
--------
- SQLite in-memory via SQLAlchemy (no Postgres required)
- Real ML artifacts built in a tmp dir (tiny RandomForest + StandardScaler + LabelEncoder)
- No FastAPI server, no real SMTP
- All external I/O (DB SessionLocal, email dispatch) is patched per-test
"""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Generator
from unittest.mock import MagicMock, patch

import joblib
import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
from backend.database.models import AttackAlert, Base
from backend.database.repository import AttackAlertRepository
from backend.feature_engine.feature_extractor import FeatureExtractor
from backend.flow_engine.flow_builder import FlowBuilder

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_CLASSES = ["Normal", "DDoS", "PortScan", "BruteForce", "Botnet", "Abnormal"]
_N_FEATURES = 20
_FEATURE_NAMES = [
    "flow_duration", "total_fwd_packets", "total_bwd_packets",
    "total_fwd_bytes", "total_bwd_bytes", "avg_packet_size",
    "packet_rate", "byte_rate", "syn_count", "fin_count",
    "rst_count", "psh_count", "ack_count", "unique_dst_ports",
    "inter_arrival_time_mean", "fwd_packet_rate", "bwd_packet_rate",
    "fwd_byte_rate", "bwd_byte_rate", "packet_length_mean",
]

# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def tmp_models_dir() -> Generator[Path, None, None]:
    """Build minimal sklearn artifacts in a temp directory once per session."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)

        scaler = StandardScaler()
        rng = np.random.default_rng(42)
        X_dummy = rng.random((50, _N_FEATURES))
        scaler.fit(X_dummy)

        y_dummy = np.array([i % len(_CLASSES) for i in range(50)])
        clf = RandomForestClassifier(n_estimators=5, random_state=42)
        clf.fit(X_dummy, y_dummy)

        le = LabelEncoder()
        le.fit(_CLASSES)

        joblib.dump(clf, d / "ensemble.pkl")
        joblib.dump(scaler, d / "ensemble_scaler.pkl")
        joblib.dump(le, d / "ensemble_encoder.pkl")

        features_json = {
            "feature_names": _FEATURE_NAMES,
            "n_features": _N_FEATURES,
            "description": "test fixture",
            "version": "1.0",
        }
        (d / "features.json").write_text(json.dumps(features_json))

        yield d


@pytest.fixture(scope="session")
def tmp_reports_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


# ---------------------------------------------------------------------------
# Function-scoped fixtures
# ---------------------------------------------------------------------------

# sqlite_session fixture is inherited from conftest.py


@pytest.fixture
def mock_bridge() -> MagicMock:
    """Mock AlertBroadcastBridge with a real queue for inspection."""
    bridge = MagicMock()
    bridge._captured: list = []

    def _enqueue(alert: Dict[str, Any]) -> bool:
        bridge._captured.append(alert)
        return True

    bridge.enqueue_alert.side_effect = _enqueue
    return bridge


@pytest.fixture
def mock_email() -> MagicMock:
    """Mock for email_service.dispatch_alert_email."""
    return MagicMock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_packet(
    src_ip: str = "10.0.0.1",
    dst_ip: str = "192.168.1.1",
    src_port: int = 54321,
    dst_port: int = 80,
    protocol: str = "TCP",
    length: int = 512,
    syn: bool = False,
) -> Dict[str, Any]:
    return {
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "src_port": src_port,
        "dst_port": dst_port,
        "protocol": protocol,
        "length": length,
        "tcp_flags": {"SYN": syn, "ACK": not syn, "FIN": False, "RST": False, "PSH": False},
    }


def _build_predictor(models_dir: Path):
    """Return a fresh Predictor backed by the tmp model artifacts."""
    from backend.detection_engine.model_loader import ModelLoader
    from backend.detection_engine.predictor import Predictor

    loader = ModelLoader(model_dir=str(models_dir))
    assert loader.load_from_directory("ensemble"), "Fixture model load failed"
    return Predictor(
        model_loader=loader,
        feature_extractor=FeatureExtractor(),
        confidence_threshold=0.75,
        features_path=str(models_dir / "features.json"),
    )


def _build_alert_manager(
    bridge: MagicMock,
    enable_db: bool = False,
    enable_email: bool = True,
):
    from backend.alert_engine.alert_manager import AlertManager

    mgr = AlertManager(
        confidence_threshold=0.75,
        alert_cooldown=0,
        enable_db_save=enable_db,
        enable_websocket=True,
        enable_email=enable_email,
    )
    mgr.set_broadcast_bridge(bridge)
    return mgr


def _import_coordinator_with_scapy_mock():
    """
    Import PipelineCoordinator while mocking the scapy-dependent packet_sniffer
    module so tests run without Scapy/Npcap installed.
    Uses setdefault to avoid mutating sys.modules for already-imported modules.
    """
    import sys
    import types

    class _FakeSniffer:
        def __init__(self, **kwargs):
            self.callback = None
            self.is_running = False

        def start(self): self.is_running = True
        def stop(self):  self.is_running = False
        def get_stats(self): return {}

    fake_sniffer_mod = types.ModuleType("backend.capture_engine.packet_sniffer")
    fake_sniffer_mod.PacketSniffer = _FakeSniffer
    fake_sniffer_mod.get_sniffer = lambda **kw: _FakeSniffer(**kw)

    fake_capture_pkg = types.ModuleType("backend.capture_engine")
    sys.modules.setdefault("backend.capture_engine", fake_capture_pkg)
    sys.modules.setdefault("backend.capture_engine.packet_sniffer", fake_sniffer_mod)

    from backend.pipeline.coordinator import PipelineCoordinator  # noqa: PLC0415
    return PipelineCoordinator


def _build_coord(
    tmp_models_dir: Path,
    mock_bridge: MagicMock,
    prediction_mode: str,
    prediction_interval_sec: float = 0.0,
    min_packets: int = 5,
):
    """Helper: build a fully wired PipelineCoordinator without a real sniffer."""
    from backend.detection_engine.model_loader import ModelLoader
    from backend.detection_engine.predictor import Predictor
    from backend.alert_engine.alert_manager import AlertManager

    PipelineCoordinator = _import_coordinator_with_scapy_mock()

    coord = PipelineCoordinator(
        interface="lo",
        model_name="ensemble",
        min_packets_per_flow=min_packets,
        prediction_mode=prediction_mode,
        prediction_interval_sec=prediction_interval_sec,
        dry_run=True,
    )

    loader = ModelLoader(model_dir=str(tmp_models_dir))
    loader.load_from_directory("ensemble")

    coord.flow_builder = FlowBuilder()
    coord.feature_extractor = FeatureExtractor()
    coord.predictor = Predictor(
        model_loader=loader,
        feature_extractor=coord.feature_extractor,
        confidence_threshold=0.75,
        features_path=str(tmp_models_dir / "features.json"),
    )
    coord.alert_manager = AlertManager(
        confidence_threshold=0.75,
        alert_cooldown=0,
        enable_db_save=False,
        enable_websocket=True,
        enable_email=False,
    )
    coord.alert_manager.set_broadcast_bridge(mock_bridge)
    coord.broadcast_bridge = mock_bridge
    return coord


# ---------------------------------------------------------------------------
# A. Flow → Feature extraction → Prediction (end-to-end)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_flow_feature_prediction_pipeline(tmp_models_dir: Path) -> None:
    """Packets → FlowBuilder → FeatureExtractor → Predictor returns a valid prediction."""
    flow_builder = FlowBuilder()
    extractor = FeatureExtractor()
    predictor = _build_predictor(tmp_models_dir)

    packet = _make_packet()
    for _ in range(15):
        flow = flow_builder.add_packet(packet)

    assert flow is not None
    features = extractor.extract_features(flow)
    assert len(features) == _N_FEATURES

    prediction = predictor.predict_flow(flow)

    assert "attack_type" in prediction
    assert "confidence" in prediction
    assert "severity" in prediction
    assert 0.0 <= prediction["confidence"] <= 1.0
    assert prediction["attack_type"] in _CLASSES


# ---------------------------------------------------------------------------
# B. Alert generation when confidence >= threshold
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_alert_generated_above_threshold(tmp_models_dir: Path, mock_bridge: MagicMock) -> None:
    """AlertManager.generate_alert returns an alert dict when confidence >= threshold."""
    mgr = _build_alert_manager(mock_bridge, enable_email=False)

    prediction = {
        "attack_type": "DDoS",
        "confidence": 0.92,
        "severity": "critical",
        "all_probabilities": {"Normal": 0.08, "DDoS": 0.92},
        "features": {},
        "model_name": "ensemble",
        "model_version": "1.0",
    }
    flow_info = {
        "src_ip": "10.0.0.1",
        "dst_ip": "192.168.1.1",
        "src_port": 54321,
        "dst_port": 80,
        "protocol": "TCP",
        "flow_key": "10.0.0.1:54321:192.168.1.1:80:TCP",
    }

    alert = mgr.generate_alert(prediction, flow_info)

    assert alert is not None
    assert alert["attack_type"] == "DDoS"
    assert alert["confidence"] == 0.92
    assert alert["src_ip"] == "10.0.0.1"


@pytest.mark.integration
def test_alert_suppressed_below_threshold(mock_bridge: MagicMock) -> None:
    """AlertManager suppresses alerts when confidence < threshold."""
    mgr = _build_alert_manager(mock_bridge, enable_email=False)

    prediction = {
        "attack_type": "PortScan",
        "confidence": 0.50,
        "severity": "medium",
        "all_probabilities": {},
        "features": {},
        "model_name": "ensemble",
        "model_version": "1.0",
    }
    flow_info = {
        "src_ip": "10.0.0.2",
        "dst_ip": "192.168.1.1",
        "src_port": 1234,
        "dst_port": 22,
        "protocol": "TCP",
        "flow_key": "10.0.0.2:1234:192.168.1.1:22:TCP",
    }

    alert = mgr.generate_alert(prediction, flow_info)
    assert alert is None


# ---------------------------------------------------------------------------
# C. AlertManager writes alerts into repository (SQLite in-memory)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_alert_manager_db_insert(sqlite_session: Session, mock_bridge: MagicMock) -> None:
    """generate_alert with enable_db_save=True inserts exactly one row via repository."""
    from backend.alert_engine.alert_manager import AlertManager

    mgr = AlertManager(
        confidence_threshold=0.75,
        alert_cooldown=0,
        enable_db_save=True,
        enable_websocket=True,
        enable_email=False,
    )
    mgr.set_broadcast_bridge(mock_bridge)

    prediction = {
        "attack_type": "BruteForce",
        "confidence": 0.88,
        "severity": "high",
        "all_probabilities": {"Normal": 0.12, "BruteForce": 0.88},
        "features": {},
        "model_name": "ensemble",
        "model_version": "1.0",
    }
    flow_info = {
        "src_ip": "172.16.0.5",
        "dst_ip": "10.10.10.1",
        "src_port": 9999,
        "dst_port": 22,
        "protocol": "TCP",
        "flow_key": "172.16.0.5:9999:10.10.10.1:22:TCP",
    }

    count_before = sqlite_session.query(func.count(AttackAlert.id)).scalar()

    sqlite_engine = sqlite_session.bind
    SQLiteSession = sessionmaker(bind=sqlite_engine)

    with patch("backend.alert_engine.alert_manager.SessionLocal", SQLiteSession):
        alert = mgr.generate_alert(prediction, flow_info)

    assert alert is not None, "Alert should have been generated"

    count_after = sqlite_session.query(func.count(AttackAlert.id)).scalar()
    assert count_after == count_before + 1, (
        f"Expected 1 new row, got {count_after - count_before}"
    )


# ---------------------------------------------------------------------------
# D. WebSocket broadcast bridge enqueue is triggered
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_broadcast_bridge_enqueue_called(mock_bridge: MagicMock) -> None:
    """generate_alert enqueues the alert on the broadcast bridge."""
    mgr = _build_alert_manager(mock_bridge, enable_email=False)

    prediction = {
        "attack_type": "Botnet",
        "confidence": 0.91,
        "severity": "critical",
        "all_probabilities": {},
        "features": {},
        "model_name": "ensemble",
        "model_version": "1.0",
    }
    flow_info = {
        "src_ip": "192.168.50.10",
        "dst_ip": "8.8.8.8",
        "src_port": 443,
        "dst_port": 53,
        "protocol": "UDP",
        "flow_key": "192.168.50.10:443:8.8.8.8:53:UDP",
    }

    mgr.generate_alert(prediction, flow_info)

    mock_bridge.enqueue_alert.assert_called_once()
    enqueued = mock_bridge._captured[0]
    assert enqueued["attack_type"] == "Botnet"


@pytest.mark.integration
def test_broadcast_bridge_not_called_for_normal(mock_bridge: MagicMock) -> None:
    """Normal traffic does not trigger a broadcast."""
    mgr = _build_alert_manager(mock_bridge, enable_email=False)

    prediction = {
        "attack_type": "Normal",
        "confidence": 0.99,
        "severity": "low",
        "all_probabilities": {},
        "features": {},
        "model_name": "ensemble",
        "model_version": "1.0",
    }
    flow_info = {
        "src_ip": "10.0.0.3",
        "dst_ip": "10.0.0.4",
        "src_port": 80,
        "dst_port": 443,
        "protocol": "TCP",
        "flow_key": "10.0.0.3:80:10.0.0.4:443:TCP",
    }

    alert = mgr.generate_alert(prediction, flow_info)
    assert alert is None
    mock_bridge.enqueue_alert.assert_not_called()


# ---------------------------------------------------------------------------
# E. Email dispatch gating (high/critical + confidence >= 0.85)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.parametrize("severity,confidence,should_send", [
    ("critical", 0.92, True),
    ("high",     0.85, True),
    ("high",     0.84, False),
    ("medium",   0.92, False),
    ("low",      0.99, False),
])
def test_email_dispatch_gating(
    severity: str,
    confidence: float,
    should_send: bool,
    mock_bridge: MagicMock,
) -> None:
    from backend.notifications.email import EmailNotificationService

    svc = EmailNotificationService(cooldown_seconds=0)

    alert = {
        "alert_id": str(uuid.uuid4()),
        "src_ip": f"10.1.2.{int(confidence * 100) % 254 + 1}",
        "dst_ip": "192.168.1.1",
        "src_port": 1111,
        "dst_port": 80,
        "protocol": "TCP",
        "attack_type": "DDoS",
        "confidence": confidence,
        "severity": severity,
    }

    with patch("backend.notifications.email.settings") as mock_settings:
        mock_settings.enable_email_alerts = True
        mock_settings.email_cooldown_seconds = 0
        result = svc.should_send_email(alert)

    assert result == should_send, (
        f"should_send_email({severity}, {confidence}) expected {should_send}, got {result}"
    )


# ---------------------------------------------------------------------------
# F. Pipeline coordinator – once mode
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_coordinator_inference_fires_after_min_packets(
    tmp_models_dir: Path,
    mock_bridge: MagicMock,
) -> None:
    """Feeding min_packets packets via packet_callback triggers exactly one inference run."""
    coord = _build_coord(tmp_models_dir, mock_bridge, prediction_mode="once")

    packet = _make_packet()

    for _ in range(4):
        coord.packet_callback(packet)
    assert coord.inference_runs == 0

    coord.packet_callback(packet)
    assert coord.inference_runs == 1


@pytest.mark.integration
def test_coordinator_once_mode_no_duplicate_inference(
    tmp_models_dir: Path,
    mock_bridge: MagicMock,
) -> None:
    """In 'once' mode, additional packets on the same flow do NOT trigger more inference runs."""
    coord = _build_coord(tmp_models_dir, mock_bridge, prediction_mode="once")

    packet = _make_packet()
    for _ in range(20):
        coord.packet_callback(packet)

    assert coord.inference_runs == 1, (
        f"Expected 1 inference run in 'once' mode, got {coord.inference_runs}"
    )


@pytest.mark.integration
def test_coordinator_no_duplicate_alerts_same_flow(
    tmp_models_dir: Path,
    mock_bridge: MagicMock,
) -> None:
    """Duplicate packets on the same flow produce at most one alert."""
    from backend.alert_engine.alert_manager import AlertManager
    from backend.detection_engine.model_loader import ModelLoader
    from backend.detection_engine.predictor import Predictor

    PipelineCoordinator = _import_coordinator_with_scapy_mock()
    coord = PipelineCoordinator(
        interface="lo",
        model_name="ensemble",
        min_packets_per_flow=5,
        prediction_mode="once",
        dry_run=True,
    )

    loader = ModelLoader(model_dir=str(tmp_models_dir))
    loader.load_from_directory("ensemble")

    coord.flow_builder = FlowBuilder()
    coord.feature_extractor = FeatureExtractor()
    coord.predictor = Predictor(
        model_loader=loader,
        feature_extractor=coord.feature_extractor,
        confidence_threshold=0.75,
        features_path=str(tmp_models_dir / "features.json"),
    )
    coord.alert_manager = AlertManager(
        confidence_threshold=0.75,
        alert_cooldown=60,
        enable_db_save=False,
        enable_websocket=True,
        enable_email=False,
    )
    coord.alert_manager.set_broadcast_bridge(mock_bridge)
    coord.broadcast_bridge = mock_bridge

    packet = _make_packet()
    for _ in range(30):
        coord.packet_callback(packet)

    assert mock_bridge.enqueue_alert.call_count <= 1


# ---------------------------------------------------------------------------
# G. Repository layer – direct SQLite insert (no AlertManager)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_repository_create_alert_sqlite(sqlite_session: Session) -> None:
    """AttackAlertRepository.create_alert persists a row in SQLite."""
    dummy = {
        "alert_id": str(uuid.uuid4()),
        "src_ip": "10.20.30.40",
        "dst_ip": "192.168.0.1",
        "src_port": 55000,
        "dst_port": 443,
        "protocol": "TCP",
        "attack_type": "PortScan",
        "severity": "high",
        "confidence": 0.88,
        "correlated": False,
        "original_severity": "high",
        "status": "active",
        "model_name": "ensemble",
        "model_version": "1.0",
        "all_probabilities": {"Normal": 0.12, "PortScan": 0.88},
        "timestamp": "2024-01-01T00:00:00",
    }

    count_before = sqlite_session.query(func.count(AttackAlert.id)).scalar()
    AttackAlertRepository.create_alert(sqlite_session, dummy, flow_id=None)
    count_after = sqlite_session.query(func.count(AttackAlert.id)).scalar()

    assert count_after == count_before + 1
    row = sqlite_session.query(AttackAlert).filter_by(alert_id=dummy["alert_id"]).first()
    assert row is not None
    assert row.attack_type == "PortScan"
    assert row.source_ip == "10.20.30.40"


# ---------------------------------------------------------------------------
# H. Pipeline coordinator – window mode
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_coordinator_window_mode_fires_multiple_times(
    tmp_models_dir: Path,
    mock_bridge: MagicMock,
) -> None:
    """
    In 'window' mode with prediction_interval_sec=0, every packet after
    min_packets should trigger a new inference run (interval already elapsed).
    """
    coord = _build_coord(
        tmp_models_dir,
        mock_bridge,
        prediction_mode="window",
        prediction_interval_sec=0.0,
    )

    packet = _make_packet()
    for _ in range(10):
        coord.packet_callback(packet)

    assert coord.inference_runs > 1, (
        f"Expected >1 inference run in 'window' mode with interval=0, got {coord.inference_runs}"
    )


@pytest.mark.integration
def test_coordinator_window_mode_respects_interval(
    tmp_models_dir: Path,
    mock_bridge: MagicMock,
) -> None:
    """
    In 'window' mode with a very large prediction_interval_sec, inference fires
    only once even after many packets (interval not yet elapsed).
    """
    coord = _build_coord(
        tmp_models_dir,
        mock_bridge,
        prediction_mode="window",
        prediction_interval_sec=9999.0,
    )

    packet = _make_packet()
    for _ in range(20):
        coord.packet_callback(packet)

    assert coord.inference_runs == 1, (
        f"Expected exactly 1 inference run when interval not elapsed, got {coord.inference_runs}"
    )
