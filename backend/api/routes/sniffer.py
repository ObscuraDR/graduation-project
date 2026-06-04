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

sniffer_router = APIRouter(dependencies=[Depends(verify_api_key)])

pipeline_task: Optional[asyncio.Task] = None
pipeline_coordinator = None
_extra_pipelines: dict = {}


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
    - interface: Network interface to capture from (can be called multiple times for different interfaces)
    - dry_run: If True, capture for 3 seconds then stop (for testing)
    """
    global pipeline_task, pipeline_coordinator

    if pipeline_coordinator and pipeline_coordinator.is_running:
        if interface == pipeline_coordinator.interface:
            return {"status": "error", "message": "Sniffer is already running on this interface"}
        if interface in _extra_pipelines and _extra_pipelines[interface].is_running:
            return {"status": "error", "message": f"Sniffer already running on {interface}"}

    require_valid_interface(interface)

    if not (1 <= min_packets <= 10_000):
        raise HTTPException(status_code=422, detail="min_packets must be 1–10000")

    if prediction_mode not in ("once", "window"):
        raise HTTPException(status_code=422, detail="prediction_mode must be 'once' or 'window'")

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

    from backend.pipeline.coordinator import get_coordinator, PipelineCoordinator
    from backend.api.websocket import get_broadcast_bridge
    from backend.alert_engine.alert_manager import get_alert_manager

    bridge = get_broadcast_bridge()
    get_alert_manager().set_broadcast_bridge(bridge)

    is_primary = not (pipeline_coordinator and pipeline_coordinator.is_running)

    if is_primary:
        coordinator = get_coordinator(
            interface=interface,
            filter_expr=filter_expr,
            model_name=model_name,
            min_packets_per_flow=min_packets,
            prediction_mode=prediction_mode,
            prediction_interval_sec=prediction_interval_sec,
            flow_expire_sec=flow_expire_sec,
            dry_run=dry_run,
        )
        coordinator.set_broadcast_bridge(bridge)
        pipeline_coordinator = coordinator
        pipeline_task = asyncio.create_task(coordinator.start())
    else:
        coordinator = PipelineCoordinator(
            interface=interface,
            filter_expr=filter_expr,
            model_name=model_name,
            min_packets_per_flow=min_packets,
            prediction_mode=prediction_mode,
            prediction_interval_sec=prediction_interval_sec,
            flow_expire_sec=flow_expire_sec,
            dry_run=dry_run,
        )
        coordinator.set_broadcast_bridge(bridge)
        _extra_pipelines[interface] = coordinator
        asyncio.create_task(coordinator.start())

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
async def stop_sniffer(interface: Optional[str] = None):
    """
    POST /api/sniffer/stop — stop the IDS pipeline.
    If interface query param is specified, stop only that interface; otherwise stop all.

    Requires header:  X-API-Key: <key>
    """
    global pipeline_coordinator, pipeline_task

    stopped = []

    if interface:
        if pipeline_coordinator and pipeline_coordinator.interface == interface and pipeline_coordinator.is_running:
            pipeline_coordinator.stop()
            if pipeline_task:
                pipeline_task.cancel()
                pipeline_task = None
            stopped.append(interface)
        elif interface in _extra_pipelines and _extra_pipelines[interface].is_running:
            _extra_pipelines[interface].stop()
            del _extra_pipelines[interface]
            stopped.append(interface)
        else:
            return {"status": "error", "message": f"No running sniffer on interface {interface}"}
    else:
        if pipeline_coordinator and pipeline_coordinator.is_running:
            pipeline_coordinator.stop()
            if pipeline_task:
                pipeline_task.cancel()
                pipeline_task = None
            stopped.append(pipeline_coordinator.interface)
        for iface, coord in list(_extra_pipelines.items()):
            if coord.is_running:
                coord.stop()
                stopped.append(iface)
        _extra_pipelines.clear()
        if not stopped:
            return {"status": "error", "message": "Sniffer is not running"}

    logger.info("IDS pipeline stopped: %s", stopped)
    return {"status": "success", "message": f"Sniffer stopped: {', '.join(stopped)}"}


@sniffer_router.get("/interfaces")
async def list_interfaces():
    """GET /api/sniffer/interfaces — list available network interfaces."""
    from backend.capture_engine.packet_sniffer import get_available_interfaces
    interfaces = get_available_interfaces()
    return {"interfaces": interfaces}


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

    if _extra_pipelines:
        stats["extra_interfaces"] = {
            iface: coord.get_stats()
            for iface, coord in _extra_pipelines.items()
            if coord.is_running
        }

    return stats
