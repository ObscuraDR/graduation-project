from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
import logging
from backend.database.connection import get_db
from backend.database.repository import ServerRepository
from backend.audit.logger import record_audit, get_client_ip
from backend.api.dependencies import verify_api_key
from backend.database.models import Server as DBServer

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