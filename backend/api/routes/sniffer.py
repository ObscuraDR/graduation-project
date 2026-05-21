"""
Sniffer control API — official IDS pipeline start/stop/status.

This is the ONLY API surface for starting/stopping packet capture with ML inference.
Do not add duplicate sniffer routes under /api/traffic.

All endpoints require a valid  X-API-Key  header.
WebSocket (/ws) is defined in main.py and remains public.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import verify_api_key
from backend.api.validation import require_valid_interface

logger = logging.getLogger(__name__)

# All routes in this router require a valid API key.
# Using router-level dependency keeps individual endpoints clean.
sniffer_router = APIRouter(dependencies=[Depends(verify_api_key)])

# Shared with main lifespan shutdown (module-level coordinator task)
pipeline_task: Optional[asyncio.Task] = None
pipeline_coordinator = None


@sniffer_router.post("/start")
async def start_sniffer(
    interface: str = "eth0",
    filter_expr: str = "ip",
    model_name: str = "ensemble",
    min_packets: int = 10,
    prediction_mode: str = "once",
    prediction_interval_sec: float = 5.0,
    flow_expire_sec: int = 30,
    dry_run: bool = False,
):
    """
    POST /api/sniffer/start — start full IDS pipeline (capture → flows → ML → alerts).

    Requires header:  X-API-Key: <key>

    Parameters:
    - interface: Network interface to capture from
    - dry_run: If True, capture for 3 seconds then stop (for testing)
    """
    global pipeline_task, pipeline_coordinator

    if pipeline_coordinator and pipeline_coordinator.is_running:
        return {"status": "error", "message": "Sniffer is already running"}

    # Validate interface name is safe (no injection chars) before OS lookup
    require_valid_interface(interface)

    # Validate min_packets range
    if not (1 <= min_packets <= 10_000):
        raise HTTPException(status_code=422, detail="min_packets must be 1–10000")

    # Validate prediction_mode
    if prediction_mode not in ("once", "window"):
        raise HTTPException(status_code=422, detail="prediction_mode must be 'once' or 'window'")

    # Validate interface exists on the host
    from backend.capture_engine.packet_sniffer import validate_interface as hw_validate_interface
    is_valid, error_msg, available_interfaces = hw_validate_interface(interface)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "error": error_msg,
                "requested_interface": interface,
                "available_interfaces": available_interfaces,
            },
        )

    from backend.pipeline.coordinator import get_coordinator
    from backend.api.websocket import get_broadcast_bridge
    from backend.alert_engine.alert_manager import get_alert_manager

    bridge = get_broadcast_bridge()
    get_alert_manager().set_broadcast_bridge(bridge)

    pipeline_coordinator = get_coordinator(
        interface=interface,
        filter_expr=filter_expr,
        model_name=model_name,
        min_packets_per_flow=min_packets,
        prediction_mode=prediction_mode,
        prediction_interval_sec=prediction_interval_sec,
        flow_expire_sec=flow_expire_sec,
        dry_run=dry_run,
    )
    pipeline_coordinator.set_broadcast_bridge(bridge)

    pipeline_task = asyncio.create_task(pipeline_coordinator.start())

    logger.info("IDS pipeline started on interface %s (dry_run=%s)", interface, dry_run)
    return {
        "status": "success",
        "message": f"Sniffer started on interface {interface}" + (" (dry run mode)" if dry_run else ""),
        "interface": interface,
        "filter": filter_expr,
        "model": model_name,
        "min_packets": min_packets,
        "prediction_mode": prediction_mode,
        "prediction_interval_sec": prediction_interval_sec,
        "flow_expire_sec": flow_expire_sec,
        "dry_run": dry_run,
    }


@sniffer_router.post("/stop")
async def stop_sniffer():
    """
    POST /api/sniffer/stop — stop the IDS pipeline and background capture task.

    Requires header:  X-API-Key: <key>
    """
    global pipeline_coordinator, pipeline_task

    if not pipeline_coordinator or not pipeline_coordinator.is_running:
        return {"status": "error", "message": "Sniffer is not running"}

    pipeline_coordinator.stop()

    if pipeline_task:
        pipeline_task.cancel()
        pipeline_task = None

    logger.info("IDS pipeline stopped")
    return {"status": "success", "message": "Sniffer stopped"}


@sniffer_router.get("/status")
async def sniffer_status():
    """
    GET /api/sniffer/status — pipeline running state and processing statistics.

    Requires header:  X-API-Key: <key>
    """
    global pipeline_coordinator

    if not pipeline_coordinator:
        return {
            "status": "stopped",
            "message": "Sniffer not initialized",
            "is_running": False,
        }

    stats = pipeline_coordinator.get_stats()
    stats["status"] = "running" if pipeline_coordinator.is_running else "stopped"
    return stats
