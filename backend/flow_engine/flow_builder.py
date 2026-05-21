"""
Flow Builder
Flow/session aggregation using 5-tuple (src_ip, dst_ip, src_port, dst_port, protocol)
"""

import logging
from datetime import datetime
from typing import Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

PredictionMode = Literal["once", "window"]


class Flow:
    """Represents a network flow (5-tuple)"""

    def __init__(
        self,
        src_ip: str,
        dst_ip: str,
        src_port: Optional[int],
        dst_port: Optional[int],
        protocol: str,
    ):
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.src_port = src_port
        self.dst_port = dst_port
        self.protocol = protocol

        self.flow_key = self._generate_flow_key()
        self.start_time = datetime.utcnow()
        self.last_seen = datetime.utcnow()
        self.packet_count = 0
        self.byte_count = 0
        self.forward_packets = 0
        self.backward_packets = 0
        self.forward_bytes = 0
        self.backward_bytes = 0

        # TCP flags
        self.syn_count = 0
        self.fin_count = 0
        self.rst_count = 0
        self.psh_count = 0
        self.ack_count = 0

        # Unique ports
        self.unique_dst_ports = set()

        # Timing
        self.inter_arrival_times: List[float] = []
        self.last_packet_time: Optional[datetime] = None

        # Inference gating (avoid re-predicting every packet on the same flow)
        self.processed: bool = False
        self.last_predicted_at: Optional[datetime] = None
        self.prediction_count: int = 0

    def _generate_flow_key(self) -> str:
        return f"{self.src_ip}:{self.src_port}:{self.dst_ip}:{self.dst_port}:{self.protocol}"

    def add_packet(self, packet_info: dict) -> None:
        self.packet_count += 1
        self.byte_count += packet_info.get("length", 0)
        self.last_seen = datetime.utcnow()

        if self.last_packet_time:
            inter_arrival = (self.last_seen - self.last_packet_time).total_seconds()
            self.inter_arrival_times.append(inter_arrival)
        self.last_packet_time = self.last_seen

        if packet_info.get("src_ip") == self.src_ip:
            self.forward_packets += 1
            self.forward_bytes += packet_info.get("length", 0)
        else:
            self.backward_packets += 1
            self.backward_bytes += packet_info.get("length", 0)

        tcp_flags = packet_info.get("tcp_flags", {})
        if tcp_flags:
            if tcp_flags.get("SYN", False):
                self.syn_count += 1
            if tcp_flags.get("FIN", False):
                self.fin_count += 1
            if tcp_flags.get("RST", False):
                self.rst_count += 1
            if tcp_flags.get("PSH", False):
                self.psh_count += 1
            if tcp_flags.get("ACK", False):
                self.ack_count += 1

        if packet_info.get("dst_port"):
            self.unique_dst_ports.add(packet_info["dst_port"])

    def get_flow_duration(self) -> float:
        return (self.last_seen - self.start_time).total_seconds()

    def should_run_inference(
        self,
        min_packets: int,
        prediction_mode: PredictionMode = "once",
        prediction_interval_sec: float = 5.0,
    ) -> bool:
        """
        Return True if this flow should run feature extraction + ML inference now.
        """
        if self.packet_count < min_packets:
            return False

        if prediction_mode == "once":
            return not self.processed

        # window mode: first time, or interval elapsed since last prediction
        if not self.processed or self.last_predicted_at is None:
            return True

        elapsed = (datetime.utcnow() - self.last_predicted_at).total_seconds()
        return elapsed >= prediction_interval_sec

    def mark_inference_complete(self) -> None:
        """Record that inference ran for this flow."""
        self.processed = True
        self.last_predicted_at = datetime.utcnow()
        self.prediction_count += 1

    def get_stats(self) -> dict:
        inter_arrival_mean = (
            sum(self.inter_arrival_times) / len(self.inter_arrival_times)
            if self.inter_arrival_times
            else 0
        )

        return {
            "flow_key": self.flow_key,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "src_port": self.src_port,
            "dst_port": self.dst_port,
            "protocol": self.protocol,
            "packet_count": self.packet_count,
            "byte_count": self.byte_count,
            "forward_packets": self.forward_packets,
            "backward_packets": self.backward_packets,
            "forward_bytes": self.forward_bytes,
            "backward_bytes": self.backward_bytes,
            "flow_duration": self.get_flow_duration(),
            "syn_count": self.syn_count,
            "fin_count": self.fin_count,
            "rst_count": self.rst_count,
            "psh_count": self.psh_count,
            "ack_count": self.ack_count,
            "unique_dst_ports": len(self.unique_dst_ports),
            "inter_arrival_time_mean": inter_arrival_mean,
            "start_time": self.start_time.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "processed": self.processed,
            "last_predicted_at": (
                self.last_predicted_at.isoformat() if self.last_predicted_at else None
            ),
            "prediction_count": self.prediction_count,
        }


class FlowBuilder:
    """Build and manage network flows from packets"""

    def __init__(
        self,
        flow_expire_sec: int = 30,
        flow_max_lifetime_sec: int = 60,
        processed_flow_retention_sec: int = 45,
    ):
        """
        Args:
            flow_expire_sec: Remove flows inactive for this many seconds
            flow_max_lifetime_sec: Remove flows older than this (absolute max age)
            processed_flow_retention_sec: Remove processed flows after this many seconds
                since last prediction (frees memory)
        """
        self.flows: Dict[str, Flow] = {}
        self.flow_expire_sec = flow_expire_sec
        self.flow_max_lifetime_sec = flow_max_lifetime_sec
        self.processed_flow_retention_sec = processed_flow_retention_sec
        self.total_flows_created = 0
        self.total_flows_expired = 0
        self.total_processed_flows_removed = 0

    def _generate_flow_key(
        self,
        src_ip: str,
        dst_ip: str,
        src_port: Optional[int],
        dst_port: Optional[int],
        protocol: str,
    ) -> str:
        return f"{src_ip}:{src_port}:{dst_ip}:{dst_port}:{protocol}"

    def add_packet(self, packet_info: dict) -> Optional[Flow]:
        src_ip = packet_info.get("src_ip")
        dst_ip = packet_info.get("dst_ip")
        src_port = packet_info.get("src_port")
        dst_port = packet_info.get("dst_port")
        protocol = packet_info.get("protocol", "unknown")

        if not src_ip or not dst_ip:
            logger.warning("Packet missing IP addresses")
            return None

        flow_key = self._generate_flow_key(src_ip, dst_ip, src_port, dst_port, protocol)

        if flow_key in self.flows:
            flow = self.flows[flow_key]
        else:
            flow = Flow(src_ip, dst_ip, src_port, dst_port, protocol)
            self.flows[flow_key] = flow
            self.total_flows_created += 1
            logger.debug("Created new flow: %s", flow_key)

        flow.add_packet(packet_info)
        return flow

    def get_flow(self, flow_key: str) -> Optional[Flow]:
        return self.flows.get(flow_key)

    def get_active_flows(self) -> List[Flow]:
        return list(self.flows.values())

    def cleanup_expired_flows(self) -> List[Flow]:
        """
        Remove flows that are inactive, exceeded max lifetime, or processed past retention.
        """
        current_time = datetime.utcnow()
        removed_flows: List[Flow] = []
        expired_keys: List[str] = []

        for flow_key, flow in self.flows.items():
            inactive_sec = (current_time - flow.last_seen).total_seconds()
            age_sec = (current_time - flow.start_time).total_seconds()

            reason: Optional[str] = None
            if inactive_sec > self.flow_expire_sec:
                reason = f"inactive {inactive_sec:.1f}s"
            elif age_sec > self.flow_max_lifetime_sec:
                reason = f"max lifetime {age_sec:.1f}s"
            elif (
                flow.processed
                and flow.last_predicted_at is not None
                and (current_time - flow.last_predicted_at).total_seconds()
                > self.processed_flow_retention_sec
            ):
                reason = "processed retention"
                self.total_processed_flows_removed += 1

            if reason:
                removed_flows.append(flow)
                expired_keys.append(flow_key)
                self.total_flows_expired += 1
                logger.debug("Expired flow %s (%s)", flow_key, reason)

        for key in expired_keys:
            del self.flows[key]

        return removed_flows

    def get_flows_by_source_ip(self, src_ip: str) -> List[Flow]:
        return [flow for flow in self.flows.values() if flow.src_ip == src_ip]

    def get_flows_by_destination_ip(self, dst_ip: str) -> List[Flow]:
        return [flow for flow in self.flows.values() if flow.dst_ip == dst_ip]

    def get_stats(self) -> dict:
        processed_active = sum(1 for f in self.flows.values() if f.processed)
        return {
            "active_flows": len(self.flows),
            "processed_active_flows": processed_active,
            "total_flows_created": self.total_flows_created,
            "total_flows_expired": self.total_flows_expired,
            "total_processed_flows_removed": self.total_processed_flows_removed,
            "flow_expire_sec": self.flow_expire_sec,
            "flow_max_lifetime_sec": self.flow_max_lifetime_sec,
            "processed_flow_retention_sec": self.processed_flow_retention_sec,
        }

    def clear_all_flows(self) -> None:
        count = len(self.flows)
        self.flows.clear()
        logger.info("Cleared %s flows", count)


_flow_builder_instance: Optional[FlowBuilder] = None


def get_flow_builder(
    flow_expire_sec: int = 30,
    flow_max_lifetime_sec: int = 60,
    processed_flow_retention_sec: int = 45,
) -> FlowBuilder:
    global _flow_builder_instance

    if _flow_builder_instance is None:
        _flow_builder_instance = FlowBuilder(
            flow_expire_sec=flow_expire_sec,
            flow_max_lifetime_sec=flow_max_lifetime_sec,
            processed_flow_retention_sec=processed_flow_retention_sec,
        )
    else:
        _flow_builder_instance.flow_expire_sec = flow_expire_sec
        _flow_builder_instance.flow_max_lifetime_sec = flow_max_lifetime_sec
        _flow_builder_instance.processed_flow_retention_sec = processed_flow_retention_sec

    return _flow_builder_instance
