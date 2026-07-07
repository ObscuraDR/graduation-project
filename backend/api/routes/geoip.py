"""
GeoIP lookup helper
Uses geoip2 + MaxMind GeoLite2-Country.mmdb if available,
falls back to ip-api.com HTTP lookup (no key required, rate-limited).
"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter

logger = logging.getLogger(__name__)

geoip_router = APIRouter()

_reader = None  # geoip2.database.Reader singleton


def _get_reader():
    global _reader
    if _reader is not None:
        return _reader
    try:
        import geoip2.database
        from pathlib import Path
        db_path = Path("backend/data/GeoLite2-Country.mmdb")
        if db_path.exists():
            _reader = geoip2.database.Reader(str(db_path))
            logger.info("GeoIP2 database loaded from %s", db_path)
    except Exception as e:
        logger.debug("geoip2 not available: %s", e)
    return _reader


def lookup_country(ip: str) -> Optional[str]:
    """Return ISO 3166-1 alpha-2 country code for *ip*, or None."""
    reader = _get_reader()
    if reader:
        try:
            resp = reader.country(ip)
            return resp.country.iso_code
        except Exception:
            pass
    # Fallback: ip-api.com (free tier, 45 req/min) — sử dụng httpx sync
    try:
        import httpx
        resp = httpx.get(
            f"http://ip-api.com/json/{ip}?fields=countryCode",
            timeout=3.0
        )
        if resp.status_code == 200:
            return resp.json().get("countryCode") or None
    except Exception:
        pass
    return None


def lookup_country_info(ip: str) -> Dict[str, Any]:
    """Return country code and name for an IP address."""
    reader = _get_reader()
    if reader:
        try:
            resp = reader.country(ip)
            return {
                "ip": ip,
                "country_code": resp.country.iso_code,
                "country_name": resp.country.name,
            }
        except Exception:
            pass
    try:
        import httpx
        resp = httpx.get(
            f"http://ip-api.com/json/{ip}?fields=status,country,countryCode",
            timeout=3.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                return {
                    "ip": ip,
                    "country_code": data.get("countryCode"),
                    "country_name": data.get("country"),
                }
    except Exception:
        pass
    return {"ip": ip, "country_code": None, "country_name": None}


@geoip_router.get("/lookup/{ip_address}")
async def geoip_lookup(ip_address: str):
    """Resolve country from IP — e.g. 185.221.20.10 → Russia."""
    return lookup_country_info(ip_address)


@geoip_router.get("/reputation/{ip_address}")
async def ip_reputation(ip_address: str):
    """
    GET /api/geoip/reputation/{ip} — tra cứu danh tiếng IP từ Threat Intelligence.
    Kết hợp GeoIP + AbuseIPDB/ip-api để biết IP có lịch sử tấn công không.
    """
    try:
        from backend.intelligence.threat_intel import get_ip_reputation
        reputation = await get_ip_reputation(ip_address)
        # Thêm thông tin GeoIP vào kết quả
        geo = lookup_country_info(ip_address)
        return {
            **reputation,
            "country_name": geo.get("country_name") or reputation.get("country"),
        }
    except Exception as e:
        logger.error("Reputation lookup error for %s: %s", ip_address, e)
        return {"ip": ip_address, "error": str(e), "threat_level": "unknown"}


@geoip_router.get("/reputation/cache/stats")
async def ti_cache_stats():
    """Thống kê cache Threat Intelligence."""
    try:
        from backend.intelligence.threat_intel import get_cache_stats
        return get_cache_stats()
    except Exception as e:
        return {"error": str(e)}
