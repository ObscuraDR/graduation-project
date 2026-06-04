"""
GeoIP lookup helper
Uses geoip2 + MaxMind GeoLite2-Country.mmdb if available,
falls back to ip-api.com HTTP lookup (no key required, rate-limited).
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)

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
    # Fallback: ip-api.com (free tier, 45 req/min)
    try:
        import requests
        resp = requests.get(f"http://ip-api.com/json/{ip}?fields=countryCode",
                            timeout=3)
        if resp.status_code == 200:
            return resp.json().get("countryCode") or None
    except Exception:
        pass
    return None
