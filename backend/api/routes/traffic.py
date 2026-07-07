"""
Traffic API Routes
Read-only monitoring endpoints for flows and traffic statistics.

Sniffer control (start/stop/status) is ONLY available via /api/sniffer/*
(see backend/api/routes/sniffer.py) — not through this router.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)

traffic_router = APIRouter()


def _pipeline_monitoring_snapshot() -> Dict[str, Any]:
    """Aggregate monitoring stats from the ML pipeline coordinator when available."""
    from backend.pipeline.coordinator import get_coordinator

    coordinator = get_coordinator()
    if coordinator.is_running:
        return coordinator.get_stats()
    return {
        "is_running": coordinator.is_running,
        "interface": coordinator.interface,
        "model_name": coordinator.model_name,
        "processed_packets": coordinator.processed_packets,
        "inference_runs": coordinator.inference_runs,
        "skipped_already_processed": coordinator.skipped_already_processed,
        "message": "Pipeline idle — use POST /api/sniffer/start to begin capture",
    }


@traffic_router.get("/stats")
async def get_traffic_stats() -> Dict[str, Any]:
    """
    GET /api/traffic/stats — monitoring snapshot (flows + pipeline state).

    Does not start/stop capture. Use /api/sniffer/* for sniffer control.
    """
    from backend.flow_engine.flow_builder import get_flow_builder

    flow_builder = get_flow_builder()

    return {
        "flows": flow_builder.get_stats(),
        "pipeline": _pipeline_monitoring_snapshot(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@traffic_router.get("/flows")
async def get_active_flows(limit: int = 100) -> List[Dict[str, Any]]:
    """
    GET /api/traffic/flows — active flows from the in-memory flow builder.
    """
    from backend.flow_engine.flow_builder import get_flow_builder

    flow_builder = get_flow_builder()
    flows = flow_builder.get_active_flows()[:limit]

    return [
        {
            "flow_key": flow.flow_key,
            "src_ip": flow.src_ip,
            "dst_ip": flow.dst_ip,
            "src_port": flow.src_port,
            "dst_port": flow.dst_port,
            "protocol": flow.protocol,
            "packet_count": flow.packet_count,
            "byte_count": flow.byte_count,
            "flow_duration": flow.get_flow_duration(),
            "start_time": flow.start_time.isoformat(),
            "last_seen": flow.last_seen.isoformat(),
        }
        for flow in flows
    ]


@traffic_router.get("/flows/{src_ip}")
async def get_flows_by_source(src_ip: str) -> List[Dict[str, Any]]:
    """
    GET /api/traffic/flows/{src_ip} — flows for a specific source IP.
    """
    from backend.flow_engine.flow_builder import get_flow_builder

    flow_builder = get_flow_builder()
    flows = flow_builder.get_flows_by_source_ip(src_ip)

    return [
        {
            "flow_key": flow.flow_key,
            "dst_ip": flow.dst_ip,
            "dst_port": flow.dst_port,
            "protocol": flow.protocol,
            "packet_count": flow.packet_count,
            "byte_count": flow.byte_count,
        }
        for flow in flows
    ]


@traffic_router.get("/top-talkers")
async def get_top_talkers(limit: int = 10) -> List[Dict[str, Any]]:
    """
    GET /api/traffic/top-talkers — top source IPs by packet count.
    """
    from backend.flow_engine.flow_builder import get_flow_builder

    flow_builder = get_flow_builder()
    flows = flow_builder.get_active_flows()

    ip_stats: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"packet_count": 0, "byte_count": 0, "flow_count": 0}
    )

    for flow in flows:
        ip_stats[flow.src_ip]["packet_count"] += flow.packet_count
        ip_stats[flow.src_ip]["byte_count"] += flow.byte_count
        ip_stats[flow.src_ip]["flow_count"] += 1

    sorted_ips = sorted(
        ip_stats.items(),
        key=lambda item: item[1]["packet_count"],
        reverse=True,
    )

    return [
        {
            "src_ip": ip,
            "packet_count": stats["packet_count"],
            "byte_count": stats["byte_count"],
            "flow_count": stats["flow_count"],
        }
        for ip, stats in sorted_ips[:limit]
    ]


@traffic_router.post("/flows/cleanup")
async def cleanup_expired_flows() -> Dict[str, Any]:
    """
    POST /api/traffic/flows/cleanup — remove inactive flows from memory.

    Monitoring/maintenance helper; does not control the sniffer.
    """
    from backend.flow_engine.flow_builder import get_flow_builder

    flow_builder = get_flow_builder()
    expired_flows = flow_builder.cleanup_expired_flows()

    logger.info("Cleaned up %s expired flows", len(expired_flows))

    return {
        "message": "Expired flows cleaned up",
        "expired_count": len(expired_flows),
        "active_flows": flow_builder.get_stats()["active_flows"],
    }
