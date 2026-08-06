"""
Pipeline Coordinator
Coordinates the IDS pipeline as a background task in FastAPI
"""

import logging
import asyncio
from typing import Literal, Optional

from backend.capture_engine.packet_sniffer import get_sniffer
from backend.flow_engine.flow_builder import Flow, get_flow_builder
from backend.feature_engine.feature_extractor import get_feature_extractor
from backend.detection_engine.model_loader import get_model_loader
from backend.detection_engine.predictor import get_predictor
from backend.alert_engine.alert_manager import get_alert_manager
from backend.database.connection import SessionLocal
from backend.database.repository import (
    TrafficFlowRepository,
    FlowFeatureRepository,
)
from backend.database.mongo_logger import log_flow_summary
from backend.config import settings

logger = logging.getLogger(__name__)

PredictionMode = Literal["once", "window"]


class PipelineCoordinator:
    """Coordinates the IDS pipeline as a background task"""

    def __init__(
        self,
        interface: str = "eth0",
        filter_expr: str = "ip",
        model_name: str = "ensemble",
        min_packets_per_flow: Optional[int] = None,
        prediction_mode: Optional[str] = None,
        prediction_interval_sec: Optional[float] = None,
        flow_expire_sec: Optional[int] = None,
        flow_max_lifetime_sec: Optional[int] = None,
        processed_flow_retention_sec: Optional[int] = None,
        dry_run: bool = False,
    ):
        self.interface = interface
        self.filter_expr = filter_expr
        self.model_name = model_name
        self.dry_run = dry_run

        # Inference gating configuration
        self.min_packets_per_flow = min_packets_per_flow or settings.min_packets
        self.prediction_mode: PredictionMode = (
            (prediction_mode or settings.prediction_mode).lower()  # type: ignore[assignment]
        )
        if self.prediction_mode not in ("once", "window"):
            logger.warning(
                "Unknown prediction_mode=%s, defaulting to 'once'",
                self.prediction_mode,
            )
            self.prediction_mode = "once"
        self.prediction_interval_sec = (
            prediction_interval_sec
            if prediction_interval_sec is not None
            else settings.prediction_interval_sec
        )
        self.flow_expire_sec = flow_expire_sec or settings.flow_expire_sec
        self.flow_max_lifetime_sec = (
            flow_max_lifetime_sec or settings.flow_max_lifetime_sec
        )
        self.processed_flow_retention_sec = (
            processed_flow_retention_sec or settings.processed_flow_retention_sec
        )

        self.is_running = False
        self.sniffer = None
        self.flow_builder = None
        self.feature_extractor = None
        self.predictor = None
        self.alert_manager = None
        self.broadcast_bridge = None

        self.processed_packets = 0
        self.inference_runs = 0
        self.skipped_already_processed = 0
        self.skipped_below_min_packets = 0
        self.cleanup_runs = 0
        self.orphan_inference_runs = 0

    def initialize(self) -> None:
        logger.info("Initializing IDS pipeline components...")
        logger.info(
            "Pipeline config: min_packets=%s prediction_mode=%s "
            "prediction_interval_sec=%s flow_expire_sec=%s",
            self.min_packets_per_flow,
            self.prediction_mode,
            self.prediction_interval_sec,
            self.flow_expire_sec,
        )

        model_loader = get_model_loader()
        if not model_loader.load_from_directory(self.model_name):
            logger.error("Failed to load model: %s", self.model_name)
            raise RuntimeError(f"Model not found: {self.model_name}")

        self.sniffer = get_sniffer(
            interface=self.interface, 
            filter_expr=self.filter_expr,
            dry_run=self.dry_run
        )
        self.flow_builder = get_flow_builder(
            flow_expire_sec=self.flow_expire_sec,
            flow_max_lifetime_sec=self.flow_max_lifetime_sec,
            processed_flow_retention_sec=self.processed_flow_retention_sec,
            max_flows=settings.flow_max_capacity,
        )
        self.feature_extractor = get_feature_extractor()
        self.predictor = get_predictor(model_loader=model_loader)
        self.alert_manager = get_alert_manager()
        if self.broadcast_bridge is not None:
            self.alert_manager.set_broadcast_bridge(self.broadcast_bridge)

        logger.info("IDS pipeline components initialized successfully")

    def set_broadcast_bridge(self, bridge) -> None:
        self.broadcast_bridge = bridge
        if self.alert_manager is not None:
            self.alert_manager.set_broadcast_bridge(bridge)
        logger.info("Alert broadcast bridge set for pipeline")

    def set_websocket_manager(self, manager) -> None:
        logger.warning(
            "PipelineCoordinator.set_websocket_manager() is deprecated; use set_broadcast_bridge()"
        )

    def _should_skip_inference(self, flow: Flow) -> bool:
        """Return True if this packet should not trigger inference."""
        if flow.packet_count < self.min_packets_per_flow:
            self.skipped_below_min_packets += 1
            return True

        if flow.should_run_inference(
            self.min_packets_per_flow,
            self.prediction_mode,
            self.prediction_interval_sec,
        ):
            return False

        self.skipped_already_processed += 1
        if self.prediction_mode == "once":
            logger.debug(
                "Flow %s already processed, skipping (packets=%s, predictions=%s)",
                flow.flow_key,
                flow.packet_count,
                flow.prediction_count,
            )
        else:
            logger.debug(
                "Flow %s re-prediction not due yet, skipping (interval=%ss)",
                flow.flow_key,
                self.prediction_interval_sec,
            )
        return True

    def _run_forced_inference(self, flow) -> None:
        """
        Ép phân loại ML cho flow mồ côi (timeout trước khi đủ min_packets).
        Gọi từ cleanup để không bỏ sót các port scan ngắn, kết nối bị đứt giữa chừng.
        """
        try:
            features = self.feature_extractor.extract_features(flow)
            prediction = self.predictor.predict_flow(flow)
            flow.mark_inference_complete()
            self.inference_runs += 1
            self.orphan_inference_runs += 1

            if self.predictor.is_attack(prediction):
                flow_id = self._save_flow_to_db(flow, features)
                log_flow_summary(flow_id, flow.get_stats(), features)
                alert = self.alert_manager.generate_alert(
                    prediction,
                    flow.get_stats(),
                    flow_id=flow_id,
                )
                if alert:
                    logger.warning(
                        "ORPHAN FLOW ALERT: %s from %s (severity: %s, packets=%d, flow=%s)",
                        alert["attack_type"],
                        alert["src_ip"],
                        alert["severity"],
                        flow.packet_count,
                        flow.flow_key,
                    )
        except Exception as exc:
            logger.error(
                "Error during forced inference on orphan flow %s: %s",
                flow.flow_key,
                exc,
            )

    def packet_callback(self, packet_info: dict) -> None:
        self.processed_packets += 1

        flow = self.flow_builder.add_packet(packet_info)
        if not flow:
            return

        if self._should_skip_inference(flow):
            if self.processed_packets % 500 == 0:
                _, orphans = self.flow_builder.cleanup_expired_flows()
                self.cleanup_runs += 1
                for orphan in orphans:
                    self._run_forced_inference(orphan)
            return

        try:
            features = self.feature_extractor.extract_features(flow)
            prediction = self.predictor.predict_flow(flow)
            flow.mark_inference_complete()
            self.inference_runs += 1

            if self.predictor.is_attack(prediction):
                flow_id = self._save_flow_to_db(flow, features)
                log_flow_summary(flow_id, flow.get_stats(), features)
                alert = self.alert_manager.generate_alert(
                    prediction,
                    flow.get_stats(),
                    flow_id=flow_id,
                )
                if alert:
                    logger.warning(
                        "ALERT: %s from %s (severity: %s, flow=%s, prediction #%s)",
                        alert["attack_type"],
                        alert["src_ip"],
                        alert["severity"],
                        flow.flow_key,
                        flow.prediction_count,
                    )

            if self.inference_runs % 50 == 0:
                _, orphans = self.flow_builder.cleanup_expired_flows()
                self.cleanup_runs += 1
                if orphans:
                    logger.debug("Forced inference on %d orphan flows", len(orphans))
                    for orphan in orphans:
                        self._run_forced_inference(orphan)

        except Exception as exc:
            logger.error("Error processing flow %s: %s", flow.flow_key, exc)

    def _save_flow_to_db(self, flow: Flow, features: dict) -> Optional[int]:
        try:
            db = SessionLocal()
            try:
                flow_data = flow.get_stats()
                traffic_flow = TrafficFlowRepository.create_flow(db, flow_data)
                FlowFeatureRepository.create_feature(db, features, traffic_flow.id)
                return traffic_flow.id
            finally:
                db.close()
        except Exception as exc:
            logger.error("Error saving flow to database: %s", exc)
            return None

    async def start(self) -> None:
        if self.is_running:
            logger.warning("Pipeline is already running")
            return

        logger.info("Starting IDS pipeline on interface %s", self.interface)
        self.initialize()
        self.sniffer.callback = self.packet_callback
        self.sniffer.start()
        self.is_running = True
        logger.info("IDS pipeline started successfully")

        while self.is_running:
            await asyncio.sleep(1)

    def stop(self) -> None:
        if not self.is_running:
            logger.warning("Pipeline is not running")
            return

        logger.info("Stopping IDS pipeline...")
        if self.sniffer:
            self.sniffer.stop()
        self.is_running = False
        if self.flow_builder:
            # Khi stop: ép inference tất cả flow mồ côi còn lại trước khi xóa
            _, orphans = self.flow_builder.cleanup_expired_flows()
            if orphans:
                logger.info("Stop: forcing inference on %d remaining orphan flows", len(orphans))
                for orphan in orphans:
                    self._run_forced_inference(orphan)
        logger.info("IDS pipeline stopped")

    def get_stats(self) -> dict:
        return {
            "is_running": self.is_running,
            "interface": self.interface,
            "filter_expr": self.filter_expr,
            "model_name": self.model_name,
            "min_packets": self.min_packets_per_flow,
            "prediction_mode": self.prediction_mode,
            "prediction_interval_sec": self.prediction_interval_sec,
            "flow_expire_sec": self.flow_expire_sec,
            "flow_max_lifetime_sec": self.flow_max_lifetime_sec,
            "processed_flow_retention_sec": self.processed_flow_retention_sec,
            "processed_packets": self.processed_packets,
            "inference_runs": self.inference_runs,
            "skipped_already_processed": self.skipped_already_processed,
            "skipped_below_min_packets": self.skipped_below_min_packets,
            "cleanup_runs": self.cleanup_runs,
            "orphan_inference_runs": self.orphan_inference_runs,
            "sniffer_stats": self.sniffer.get_stats() if self.sniffer else {},
            "flow_builder_stats": self.flow_builder.get_stats() if self.flow_builder else {},
            "predictor_stats": self.predictor.get_stats() if self.predictor else {},
            "alert_manager_stats": self.alert_manager.get_stats() if self.alert_manager else {},
        }


_coordinator_instance: Optional[PipelineCoordinator] = None


def get_coordinator(
    interface: str = "eth0",
    filter_expr: str = "ip",
    model_name: str = "ensemble",
    min_packets_per_flow: Optional[int] = None,
    prediction_mode: Optional[str] = None,
    prediction_interval_sec: Optional[float] = None,
    flow_expire_sec: Optional[int] = None,
    dry_run: bool = False,
) -> PipelineCoordinator:
    global _coordinator_instance

    if _coordinator_instance is None:
        _coordinator_instance = PipelineCoordinator(
            interface=interface,
            filter_expr=filter_expr,
            model_name=model_name,
            min_packets_per_flow=min_packets_per_flow,
            prediction_mode=prediction_mode,
            prediction_interval_sec=prediction_interval_sec,
            flow_expire_sec=flow_expire_sec,
            dry_run=dry_run,
        )
    else:
        _coordinator_instance.interface = interface
        _coordinator_instance.filter_expr = filter_expr
        _coordinator_instance.model_name = model_name
        _coordinator_instance.dry_run = dry_run
        if min_packets_per_flow is not None:
            _coordinator_instance.min_packets_per_flow = min_packets_per_flow
        if prediction_mode is not None:
            _coordinator_instance.prediction_mode = prediction_mode  # type: ignore[assignment]
        if prediction_interval_sec is not None:
            _coordinator_instance.prediction_interval_sec = prediction_interval_sec
        if flow_expire_sec is not None:
            _coordinator_instance.flow_expire_sec = flow_expire_sec

    return _coordinator_instance
