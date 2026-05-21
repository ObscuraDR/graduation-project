"""
API Dependencies
================
Reusable FastAPI dependencies for the IDS backend.

Usage (in any router)
---------------------
    from fastapi import Depends
    from backend.api.dependencies import verify_api_key

    @router.post("/some-endpoint", dependencies=[Depends(verify_api_key)])
    async def my_endpoint(): ...

    # — or inject as a parameter (when you need the key value itself) —
    @router.get("/echo-key")
    async def echo(api_key: str = Depends(verify_api_key)): ...
"""

from __future__ import annotations

import logging
import secrets

from fastapi import Header, HTTPException, status

from backend.config import get_settings

logger = logging.getLogger(__name__)

# ── Error returned on auth failure ────────────────────────────────────────────
_401 = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing API key",
    # Hint clients to use a custom scheme; avoids browser Basic-Auth prompt
    headers={"WWW-Authenticate": "ApiKey"},
)


async def verify_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """
    FastAPI dependency — validates the ``X-API-Key`` request header.

    Raises:
        HTTPException 401: When the header is absent or the value does not
            match the ``API_KEY`` environment variable.

    Returns:
        The validated API key string (useful if a route needs to log/audit it).
    """
    if x_api_key is None:
        logger.warning("Request rejected: X-API-Key header missing")
        raise _401

    expected: str = get_settings().api_key

    # secrets.compare_digest prevents timing-attack on string comparison
    if not secrets.compare_digest(x_api_key, expected):
        logger.warning("Request rejected: invalid API key supplied")
        raise _401

    return x_api_key
