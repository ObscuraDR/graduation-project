import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, ConfigDict
from backend.database.connection import get_db
from backend.database.repository import ServerRepository, ServerMetricHistoryRepository
from backend.audit.logger import record_audit, get_client_ip
from backend.api.dependencies import verify_api_key
from backend.database.models import Server as DBServer

router = APIRouter(prefix="/api/servers", tags=["servers"])
logger = logging.getLogger(__name__)

# ── Async log queue — nhận events từ nhiều agents, batch insert vào DB ────────
_log_queue: asyncio.Queue = asyncio.Queue(maxsize=10_000)
_log_worker_task: Optional[asyncio.Task] = None

# ── Firewall command queue — lưu lệnh firewall pending cho từng server ────────
_firewall_commands: Dict[int, List[Dict]] = defaultdict(list)  # server_id -> list of commands


async def start_log_worker():
    """Khởi động background worker xử lý log queue. Gọi từ lifespan."""
    global _log_worker_task
    if _log_worker_task is None or _log_worker_task.done():
        _log_worker_task = asyncio.create_task(
            _log_batch_worker(), name="server-log-batch-worker"
        )
        logger.info("Server log batch worker started")


async def stop_log_worker():
    """Dừng worker khi shutdown."""
    global _log_worker_task
    if _log_worker_task and not _log_worker_task.done():
        _log_worker_task.cancel()
        try:
            await _log_worker_task
        except asyncio.CancelledError:
            pass


async def _log_batch_worker(batch_size: int = 20, flush_interval: float = 5.0):
    """
    Background worker: gom events từ queue → batch INSERT vào DB + trigger AlertManager.
    Flush mỗi 5 giây hoặc khi đủ 20 events — tránh INSERT từng dòng.
    """
    from backend.database.security_log_store import store_security_log
    from backend.alert_engine.alert_manager import get_alert_manager

    logger.info("Log batch worker started (batch=%d, flush=%.1fs)", batch_size, flush_interval)
    batch = []
    last_flush = asyncio.get_event_loop().time()
    alert_mgr = get_alert_manager()

    while True:
        try:
            try:
                item = await asyncio.wait_for(_log_queue.get(), timeout=1.0)
                batch.append(item)
                _log_queue.task_done()
            except asyncio.TimeoutError:
                pass

            now = asyncio.get_event_loop().time()
            should_flush = len(batch) >= batch_size or (
                batch and now - last_flush >= flush_interval
            )

            if should_flush and batch:
                for event in batch:
                    try:
                        # Lưu log vào DB
                        store_security_log(
                            server=event.get("server", "unknown"),
                            source_ip=event.get("source_ip"),
                            event_type=event.get("event_type", "generic"),
                            message=event.get("message", ""),
                            log_source=event.get("log_source", "agent"),
                            extra={
                                "server_id": event.get("server_id"),
                                "count": event.get("count"),
                                "severity": event.get("severity"),
                            },
                        )

                        # Trigger AlertManager cho các event nghiêm trọng
                        event_type = event.get("event_type", "")
                        source_ip = event.get("source_ip")
                        severity = event.get("severity", "low")

                        if source_ip and event_type in ["ssh_brute_force", "cpu_spike", "ram_spike", "syn_flood_inbound", "syn_flood_outbound"]:
                            # Tạo prediction dict cho AlertManager
                            prediction = {
                                "attack_type": event_type,
                                "confidence": 0.9 if severity == "critical" else (0.8 if severity == "high" else 0.7),
                                "severity": severity,
                            }
                            flow_info = {
                                "src_ip": source_ip,
                                "dst_ip": event.get("server", "unknown"),
                                "event_type": event_type,
                                "count": event.get("count", 1),
                            }

                            # Gọi AlertManager để xử lý và auto-block nếu cần
                            try:
                                alert_mgr.generate_alert(prediction, flow_info)
                                logger.debug("AlertManager triggered for %s from %s", event_type, source_ip)
                            except Exception as e:
                                logger.error("AlertManager error: %s", e)

                    except Exception as e:
                        logger.debug("Store log error: %s", e)

                logger.debug("Flushed %d log events to DB with AlertManager processing", len(batch))
                batch.clear()
                last_flush = now

        except asyncio.CancelledError:
            for event in batch:
                try:
                    from backend.database.security_log_store import store_security_log
                    store_security_log(
                        server=event.get("server", "unknown"),
                        source_ip=event.get("source_ip"),
                        event_type=event.get("event_type", "generic"),
                        message=event.get("message", ""),
                        log_source=event.get("log_source", "agent"),
                    )
                except Exception:
                    pass
            logger.info("Log batch worker stopped")
            break
        except Exception as e:
            logger.error("Log batch worker error: %s", e)
            await asyncio.sleep(1)

router = APIRouter(prefix="/api/servers", tags=["servers"])

logger = logging.getLogger(__name__)

# Pydantic models for request/response

class ServerBase(BaseModel):
    model_config = ConfigDict(protected_namespaces=()) # Thêm dòng này để xử lý cảnh báo namespace

    name: str = Field(..., min_length=3, max_length=100)
    ip_address: str = Field(..., pattern=r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$|^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$") # IPv4 or IPv6
    os: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=500)

class ServerCreate(ServerBase):
    pass

class ServerUpdate(ServerBase):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    ip_address: Optional[str] = Field(None, pattern=r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$|^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$")
    status: Optional[str] = Field(None, max_length=20)
    cpu_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    ram_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    disk_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    firewall_status: Optional[str] = Field(None, max_length=50)

class ServerResponse(ServerBase):
    id: int
    status: str
    cpu_usage: Optional[float]
    ram_usage: Optional[float]
    disk_usage: Optional[float]
    firewall_status: Optional[str]
    last_seen: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

class ServerMetricHistoryResponse(BaseModel):
    id: int
    server_id: int
    timestamp: datetime
    cpu_usage: float
    ram_usage: float
    disk_usage: float
    firewall_status: Optional[str]
    status: str
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

@router.post("/", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
def create_server(server: ServerCreate, request: Request, db: Session = Depends(get_db)):
    db_server = ServerRepository.get_server_by_ip(db, ip_address=server.ip_address)
    if db_server:
        raise HTTPException(status_code=400, detail="IP address already registered")
    created = ServerRepository.create_server(db, **server.model_dump())
    record_audit(
        db, "system", "create_server",
        resource_type="server", resource_id=str(created.id),
        details={"name": created.name, "ip": created.ip_address},
        client_ip=get_client_ip(request),
    )
    return created

@router.get("/", response_model=List[ServerResponse])
def get_all_servers(db: Session = Depends(get_db)):
    return ServerRepository.get_all_servers(db)

@router.get("/{server_id}", response_model=ServerResponse)
def get_server(server_id: int, db: Session = Depends(get_db)):
    db_server = ServerRepository.get_server_by_id(db, server_id)
    if db_server is None:
        raise HTTPException(status_code=404, detail="Server not found")
    return db_server

@router.put("/{server_id}", response_model=ServerResponse)
def update_server(server_id: int, server: ServerUpdate, db: Session = Depends(get_db)):
    db_server = ServerRepository.update_server(db, server_id, **server.model_dump(exclude_unset=True))
    if db_server is None:
        raise HTTPException(status_code=404, detail="Server not found")
    return db_server

@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_server(server_id: int, request: Request, db: Session = Depends(get_db)):
    server = ServerRepository.get_server_by_id(db, server_id)
    if not ServerRepository.delete_server(db, server_id):
        raise HTTPException(status_code=404, detail="Server not found")
    if server:
        record_audit(
            db, "system", "delete_server",
            resource_type="server", resource_id=str(server_id),
            details={"name": server.name, "ip": server.ip_address},
            client_ip=get_client_ip(request),
        )
    return None

@router.post("/{server_id}/status", response_model=ServerResponse)
def update_server_status(
    server_id: int,
    status: str, cpu_usage: float, ram_usage: float, disk_usage: float, firewall_status: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Endpoint để agent gửi cập nhật trạng thái."""
    db_server = ServerRepository.update_server(
        db, server_id, status=status, cpu_usage=cpu_usage, ram_usage=ram_usage,
        disk_usage=disk_usage, firewall_status=firewall_status
    )
    
    # Lưu lịch sử chỉ số
    if db_server:
        from backend.database.repository import ServerMetricHistoryRepository # Moved to top-level import
        ServerMetricHistoryRepository.create_history_entry(
            db, server_id=server_id, cpu_usage=cpu_usage, ram_usage=ram_usage,
            disk_usage=disk_usage, status=status, firewall_status=firewall_status
        )
        logger.debug(f"Saved metric history for server {server_id}")
    if db_server is None:
        raise HTTPException(status_code=404, detail="Server not found")
    return db_server

@router.get("/{server_id}/history", response_model=List[ServerMetricHistoryResponse])
def get_server_history(server_id: int, limit: int = 100, db: Session = Depends(get_db)):
    """Lấy lịch sử chỉ số của một máy chủ."""
    from backend.database.repository import ServerMetricHistoryRepository # Moved to top-level import
    return ServerMetricHistoryRepository.get_history_for_server(db, server_id, limit)


class AgentLogPayload(BaseModel):
    """Payload khi agent gửi security events."""
    server_id: int
    events: List[Dict]
    timestamp: str


class FirewallCommand(BaseModel):
    """Firewall command payload."""
    action: str = Field(..., pattern="^(block|unblock)$")
    ip: str = Field(..., pattern=r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
    reason: Optional[str] = Field(None, max_length=500)


@router.post("/{server_id}/logs")
async def receive_agent_logs(
    server_id: int,
    payload: AgentLogPayload,
    api_key: str = Depends(verify_api_key)
):
    """
    Endpoint để agent gửi security events.
    Nhận vào queue async → batch insert vào DB để tránh overload.
    """
    # Validate server_id matches payload
    if payload.server_id != server_id:
        raise HTTPException(status_code=400, detail="server_id mismatch")
    
    # Get server name for logging
    from backend.database.repository import ServerRepository
    from backend.database.connection import get_db
    db_gen = get_db()
    db = next(db_gen)
    try:
        server = ServerRepository.get_server_by_id(db, server_id)
        server_name = server.name if server else f"server-{server_id}"
    finally:
        db.close()
    
    # Put events into async queue for batch processing
    event_count = 0
    for event in payload.events:
        try:
            await _log_queue.put({
                "server": server_name,
                "server_id": server_id,
                "source_ip": event.get("source_ip"),
                "event_type": event.get("event_type", "generic"),
                "message": event.get("message", ""),
                "log_source": event.get("log_source", "agent"),
                "count": event.get("count"),
                "severity": event.get("severity"),
            })
            event_count += 1
        except Exception as e:
            logger.error("Failed to queue event: %s", e)
    
    logger.debug("Queued %d security events from server %s", event_count, server_name)
    return {"status": "accepted", "queued_events": event_count}


@router.post("/{server_id}/firewall-command")
async def send_firewall_command(
    server_id: int,
    command: FirewallCommand,
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Endpoint để gửi lệnh firewall đến agent trên server cụ thể.
    Lệnh được lưu vào queue và agent sẽ fetch qua polling.
    """
    # Validate server exists
    server = ServerRepository.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    # Add command to queue
    cmd_dict = {
        "action": command.action,
        "ip": command.ip,
        "reason": command.reason or f"Manual command from {get_client_ip(request)}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    _firewall_commands[server_id].append(cmd_dict)
    
    logger.info(f"Queued firewall command for server {server_id}: {command.action} {command.ip}")
    
    record_audit(
        db, "system", "send_firewall_command",
        resource_type="server", resource_id=str(server_id),
        details={"action": command.action, "ip": command.ip, "reason": command.reason},
        client_ip=get_client_ip(request),
    )
    
    return {"status": "queued", "command": cmd_dict}


@router.get("/{server_id}/commands")
async def get_firewall_commands(
    server_id: int,
    api_key: str = Depends(verify_api_key)
):
    """
    Endpoint để agent fetch các lệnh firewall pending.
    Agent sẽ gọi endpoint này định kỳ (polling).
    """
    # Validate server exists
    from backend.database.repository import ServerRepository
    from backend.database.connection import get_db
    db_gen = get_db()
    db = next(db_gen)
    try:
        server = ServerRepository.get_server_by_id(db, server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
    finally:
        db.close()
    
    # Get and clear commands for this server
    commands = _firewall_commands.get(server_id, [])
    _firewall_commands[server_id] = []  # Clear after fetching
    
    logger.debug(f"Agent fetched {len(commands)} commands for server {server_id}")
    
    return {"commands": commands}