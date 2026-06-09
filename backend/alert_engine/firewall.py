from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from backend.database.connection import get_db
from backend.database.repository import BlacklistRepository
from backend.api.auth import get_current_user_from_cookie, verify_csrf_token
from backend.scripts.firewall_manager import FirewallManager

router = APIRouter(prefix="/api/firewall", tags=["firewall"])
fw_manager = FirewallManager()

@router.get("/blacklist")
def get_blacklist(db: Session = Depends(get_db)):
    """Lấy danh sách các IP đang bị chặn (Host-level)."""
    return BlacklistRepository.get_all_active(db)

@router.get("/cloudflare-blacklist")
async def get_cloudflare_blacklist(
    current_user: dict = Depends(get_current_user_from_cookie)
):
    """Lấy danh sách các IP đang bị chặn bởi Cloudflare (Edge)."""
    return await fw_manager.list_cloudflare_rules_async()

@router.post("/block")
async def manual_block(
    ip: str, reason: str, duration_mins: int = 60, 
    current_user: dict = Depends(get_current_user_from_cookie),
    _csrf_verified: bool = Depends(verify_csrf_token),
    db: Session = Depends(get_db)
):
    """Chặn IP thủ công từ Dashboard."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Admin mới có quyền chặn IP")
    if await fw_manager.block_ip(ip, reason):
        expires_at = datetime.utcnow() + timedelta(minutes=duration_mins)
        BlacklistRepository.create(db, ip_address=ip, reason=reason, expires_at=expires_at, auto_blocked=False)
        return {"status": "success", "message": f"IP {ip} blocked"}
    raise HTTPException(status_code=500, detail="Failed to apply firewall rule")

@router.delete("/unblock/{ip}")
async def manual_unblock(
    ip: str, 
    current_user: dict = Depends(get_current_user_from_cookie),
    _csrf_verified: bool = Depends(verify_csrf_token),
    db: Session = Depends(get_db)
):
    """Gỡ chặn IP thủ công."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Admin mới có quyền gỡ chặn IP")
    if await fw_manager.unblock_ip(ip):
        BlacklistRepository.remove_by_ip(db, ip)
        return {"status": "success", "message": f"IP {ip} unblocked"}
    raise HTTPException(status_code=500, detail="Failed to remove firewall rule")

@router.delete("/cloudflare-unblock/{ip}")
async def remove_cloudflare_blacklist(
    ip: str,
    current_user: dict = Depends(get_current_user_from_cookie),
    _csrf_verified: bool = Depends(verify_csrf_token)
):
    """Gỡ bỏ rule chặn IP cụ thể trên Cloudflare Edge."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Admin mới có quyền gỡ chặn IP trên Cloudflare")
    # Gọi trực tiếp logic xóa của Cloudflare và await kết quả
    if await fw_manager._cloudflare_unblock_async(ip):
        return {"status": "success", "message": f"IP {ip} removed from Cloudflare Edge"}
    raise HTTPException(status_code=500, detail="Failed to remove Cloudflare rule")