"""
Flow Builder
Flow/session aggregation using 5-tuple (src_ip, dst_ip, src_port, dst_port, protocol)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

PredictionMode = Literal["once", "window"]


def canonical_flow_key(
    src_ip: str,
    dst_ip: str,
    src_port: Optional[int],
    dst_port: Optional[int],
    protocol: str,
) -> str:
    """
    Build a DIRECTION-INDEPENDENT (canonical) 5-tuple flow key.

    Request packets (A->B) and their replies (B->A) must aggregate into the
    SAME bidirectional flow so that forward/backward features (total_bwd_*,
    bwd_packet_rate, bwd_byte_rate, ...) are populated. This matches how the
    model was trained on CICIDS2017 bidirectional flows; keying on raw
    direction left every live flow one-directional and skewed inference.

    The two endpoints (ip, port) are sorted so the key is identical regardless
    of which side initiated the packet.
    """
    proto = str(protocol).lower()
    endpoint_a = (str(src_ip), src_port if src_port is not None else -1)
    endpoint_b = (str(dst_ip), dst_port if dst_port is not None else -1)
    low, high = sorted((endpoint_a, endpoint_b))
    return f"{low[0]}:{low[1]}-{high[0]}:{high[1]}-{proto}"


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
        self.start_time = datetime.now(timezone.utc)
        self.last_seen = datetime.now(timezone.utc)
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
        return canonical_flow_key(
            self.src_ip, self.dst_ip, self.src_port, self.dst_port, self.protocol
        )

    def add_packet(self, packet_info: dict) -> None:
        # CICIDS2017 byte features are PAYLOAD-ONLY (its "Total Length of
        # Fwd/Bwd Packet" = sum of L4 payload lengths; this is verifiable:
        # (total_fwd_bytes + total_bwd_bytes) / packet_count == avg_packet_size
        # in the training data). The live sniffer provides both full-frame
        # 'length' (incl. Ethernet/IP/TCP headers ~54B) and L4 'payload_size'.
        # Use payload_size to match training semantics and avoid a train/serve
        # skew that inflates byte features at inference time. Fall back to
        # 'length' when payload_size is absent (e.g. unit-test packets).
        byte_len = (
            packet_info["payload_size"]
            if "payload_size" in packet_info
            else packet_info.get("length", 0)
        )

        self.packet_count += 1
        self.byte_count += byte_len
        self.last_seen = datetime.now(timezone.utc)

        if self.last_packet_time:
            inter_arrival = (self.last_seen - self.last_packet_time).total_seconds()
            self.inter_arrival_times.append(inter_arrival)
        self.last_packet_time = self.last_seen

        is_forward = packet_info.get("src_ip") == self.src_ip
        if is_forward:
            self.forward_packets += 1
            self.forward_bytes += byte_len
        else:
            self.backward_packets += 1
            self.backward_bytes += byte_len

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

        # Count destination ports for forward-direction packets only. Backward
        # (reply) packets carry the initiator's ephemeral port as their
        # dst_port, which would otherwise inflate unique_dst_ports now that
        # both directions share one canonical flow.
        if is_forward and packet_info.get("dst_port"):
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

        elapsed = (datetime.now(timezone.utc) - self.last_predicted_at).total_seconds()
        return elapsed >= prediction_interval_sec

    def mark_inference_complete(self) -> None:
        """Record that inference ran for this flow."""
        self.processed = True
        self.last_predicted_at = datetime.now(timezone.utc)
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
        return canonical_flow_key(src_ip, dst_ip, src_port, dst_port, protocol)

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
        """Remove flows that are inactive, exceeded max lifetime, or processed past retention."""
        current_time = datetime.now(timezone.utc)
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
