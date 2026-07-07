"""
Threat Intelligence Module
==========================
Tra cứu danh tiếng IP từ các nguồn bên ngoài để tăng độ chính xác phát hiện.

Nguồn hỗ trợ:
  1. AbuseIPDB — tra cứu IP có lịch sử tấn công
  2. Cache nội bộ (in-memory TTL) — tránh gọi API lặp lại

Sử dụng:
  from backend.intelligence.threat_intel import get_ip_reputation, enrich_alert

Tích hợp vào AlertManager:
  Khi generate_alert() → enrich_alert() tự động tăng severity nếu IP xấu
"""

from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# ── In-memory cache với TTL ────────────────────────────────────────────────────
_reputation_cache: Dict[str, Dict] = {}
_CACHE_TTL_HOURS = 6  # cache 6 giờ


def _is_cache_valid(entry: Dict) -> bool:
    """Kiểm tra cache entry còn hiệu lực không."""
    cached_at = entry.get("cached_at")
    if not cached_at:
        return False
    age = datetime.now(timezone.utc) - cached_at
    return age < timedelta(hours=_CACHE_TTL_HOURS)


def _get_from_cache(ip: str) -> Optional[Dict]:
    """Lấy reputation từ cache nếu còn hiệu lực."""
    entry = _reputation_cache.get(ip)
    if entry and _is_cache_valid(entry):
        return entry
    return None


def _set_cache(ip: str, data: Dict) -> None:
    """Lưu vào cache với timestamp."""
    _reputation_cache[ip] = {
        **data,
        "cached_at": datetime.now(timezone.utc),
    }
    # Dọn cache cũ khi > 1000 entries
    if len(_reputation_cache) > 1000:
        _cleanup_cache()


def _cleanup_cache() -> None:
    """Xóa các entries hết TTL."""
    expired = [ip for ip, entry in _reputation_cache.items() if not _is_cache_valid(entry)]
    for ip in expired:
        del _reputation_cache[ip]
    if expired:
        logger.debug("Threat intel cache cleanup: removed %d expired entries", len(expired))


# ── AbuseIPDB Lookup ───────────────────────────────────────────────────────────

async def _lookup_abuseipdb(ip: str, api_key: str) -> Optional[Dict]:
    """
    Tra cứu IP trên AbuseIPDB API.
    Trả về None nếu không có API key hoặc lỗi.

    API docs: https://docs.abuseipdb.com/#check-endpoint
    """
    if not api_key:
        return None

    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.abuseipdb.com/api/v2/check",
                params={"ipAddress": ip, "maxAgeInDays": 90},
                headers={
                    "Key": api_key,
                    "Accept": "application/json",
                },
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                return {
                    "ip": ip,
                    "abuse_score": data.get("abuseConfidenceScore", 0),
                    "total_reports": data.get("totalReports", 0),
                    "country_code": data.get("countryCode"),
                    "usage_type": data.get("usageType"),
                    "isp": data.get("isp"),
                    "is_tor": data.get("isTor", False),
                    "is_public": data.get("isPublic", True),
                    "last_reported": data.get("lastReportedAt"),
                    "source": "abuseipdb",
                }
            logger.debug("AbuseIPDB returned %s for %s", resp.status_code, ip)
    except Exception as e:
        logger.debug("AbuseIPDB lookup failed for %s: %s", ip, e)
    return None


# ── ip-api.com enrichment (no key needed) ─────────────────────────────────────

async def _lookup_ipapi(ip: str) -> Optional[Dict]:
    """
    Tra cứu thông tin cơ bản từ ip-api.com (free, no key, 45 req/min).
    Trả về ASN, ISP, country để enrich alert.
    """
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,country,countryCode,isp,org,as,hosting,proxy,vpn,tor"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    return {
                        "ip": ip,
                        "country_code": data.get("countryCode"),
                        "country": data.get("country"),
                        "isp": data.get("isp"),
                        "org": data.get("org"),
                        "asn": data.get("as"),
                        "is_hosting": data.get("hosting", False),
                        "is_proxy": data.get("proxy", False),
                        "is_vpn": data.get("vpn", False),
                        "is_tor": data.get("tor", False),
                        "source": "ip-api",
                        "abuse_score": 0,  # ip-api không có score
                    }
    except Exception as e:
        logger.debug("ip-api lookup failed for %s: %s", ip, e)
    return None


# ── Public API ─────────────────────────────────────────────────────────────────

async def get_ip_reputation(ip: str) -> Dict[str, Any]:
    """
    Tra cứu danh tiếng của IP từ cache hoặc external API.

    Ưu tiên: Cache → AbuseIPDB (nếu có key) → ip-api.com → fallback

    Returns:
        dict với keys: ip, abuse_score, country_code, is_tor, is_vpn,
                       is_proxy, is_hosting, isp, source, threat_level
    """
    # 1. Kiểm tra private/reserved IPs — không cần tra cứu
    try:
        import ipaddress
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_reserved:
            return {"ip": ip, "abuse_score": 0, "threat_level": "safe", "source": "local"}
    except ValueError:
        pass

    # 2. Cache hit
    cached = _get_from_cache(ip)
    if cached:
        return cached

    # 3. External lookup
    from backend.config import get_settings
    settings = get_settings()
    abuseipdb_key = getattr(settings, "abuseipdb_api_key", "") or ""

    result = None

    # Thử AbuseIPDB trước nếu có key
    if abuseipdb_key:
        result = await _lookup_abuseipdb(ip, abuseipdb_key)

    # Fallback ip-api
    if not result:
        result = await _lookup_ipapi(ip)

    # Fallback mặc định
    if not result:
        result = {"ip": ip, "abuse_score": 0, "source": "unknown"}

    # Tính threat_level từ các signals
    result["threat_level"] = _calculate_threat_level(result)

    _set_cache(ip, result)
    return result


def _calculate_threat_level(data: Dict) -> str:
    """
    Tính mức độ nguy hiểm từ các tín hiệu.
    Returns: "critical" | "high" | "medium" | "low" | "safe"
    """
    score = data.get("abuse_score", 0)
    is_tor = data.get("is_tor", False)
    is_vpn = data.get("is_vpn", False)
    is_proxy = data.get("is_proxy", False)
    is_hosting = data.get("is_hosting", False)
    total_reports = data.get("total_reports", 0)

    if score >= 80 or (is_tor and score >= 20):
        return "critical"
    if score >= 50 or total_reports >= 100:
        return "high"
    if score >= 20 or is_tor or (is_vpn and score > 0) or total_reports >= 10:
        return "medium"
    if is_proxy or is_hosting or score > 0:
        return "low"
    return "safe"


def enrich_alert_sync(alert: Dict, reputation: Dict) -> Dict:
    """
    Enrich alert với thông tin reputation (synchronous version cho AlertManager).
    Điều chỉnh severity nếu IP có lịch sử xấu.

    Args:
        alert: Alert dict từ AlertManager.generate_alert()
        reputation: Dict từ get_ip_reputation()

    Returns:
        Alert dict đã được enrich
    """
    threat_level = reputation.get("threat_level", "safe")
    abuse_score = reputation.get("abuse_score", 0)
    current_severity = alert.get("severity", "low")

    # Tăng severity nếu IP có danh tiếng xấu
    severity_order = ["low", "medium", "high", "critical"]
    threat_to_severity = {
        "critical": "critical",
        "high":     "high",
        "medium":   "medium",
        "low":      "low",
        "safe":     None,
    }

    threat_severity = threat_to_severity.get(threat_level)
    if threat_severity:
        current_idx = severity_order.index(current_severity) if current_severity in severity_order else 0
        threat_idx = severity_order.index(threat_severity)
        if threat_idx > current_idx:
            alert["severity"] = threat_severity
            alert["severity_escalated_by_ti"] = True
            logger.info(
                "TI escalated severity for %s: %s → %s (abuse_score=%d)",
                alert.get("src_ip"), current_severity, threat_severity, abuse_score
            )

    # Thêm thông tin TI vào alert
    alert["threat_intel"] = {
        "abuse_score": abuse_score,
        "threat_level": threat_level,
        "country_code": reputation.get("country_code"),
        "isp": reputation.get("isp"),
        "is_tor": reputation.get("is_tor", False),
        "is_vpn": reputation.get("is_vpn", False),
        "is_proxy": reputation.get("is_proxy", False),
        "source": reputation.get("source", "unknown"),
    }

    return alert


def get_cache_stats() -> Dict:
    """Thống kê cache để monitoring."""
    valid = sum(1 for entry in _reputation_cache.values() if _is_cache_valid(entry))
    return {
        "total_entries": len(_reputation_cache),
        "valid_entries": valid,
        "expired_entries": len(_reputation_cache) - valid,
        "ttl_hours": _CACHE_TTL_HOURS,
    }
