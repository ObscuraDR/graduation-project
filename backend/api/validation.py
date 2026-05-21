"""
Input Validation
================
Reusable validators for IPv4 addresses, ports, protocols, and interface names.
Import these into Pydantic models or use validate_* directly in route handlers.
"""

from __future__ import annotations

import re
from typing import Optional

from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_IPV4_RE = re.compile(
    r"^((25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)\.){3}"
    r"(25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)$"
)

# Allow alphanumeric, hyphen, underscore, dot, space (covers "Wi-Fi", "eth0", "Ethernet 2")
# Reject shell-injection chars: ; & | ` $ ( ) < > \ / newline
_INTERFACE_SAFE_RE = re.compile(r"^[A-Za-z0-9 _\-\.]{1,64}$")

_ALLOWED_PROTOCOLS = frozenset({"tcp", "udp", "icmp"})

# ---------------------------------------------------------------------------
# Validators (raise ValueError — compatible with Pydantic field_validator)
# ---------------------------------------------------------------------------

def validate_ipv4(value: str) -> str:
    """Raise ValueError if *value* is not a valid dotted-decimal IPv4 address."""
    if not value or not _IPV4_RE.match(value.strip()):
        raise ValueError(f"Invalid IPv4 address: '{value}'")
    return value.strip()


def validate_port(value: int) -> int:
    """Raise ValueError if *value* is outside 1–65535."""
    if not (1 <= value <= 65535):
        raise ValueError(f"Port must be 1–65535, got {value}")
    return value


def validate_protocol(value: str) -> str:
    """Raise ValueError if *value* is not tcp|udp|icmp (case-insensitive)."""
    lower = value.strip().lower()
    if lower not in _ALLOWED_PROTOCOLS:
        raise ValueError(
            f"Protocol must be one of {sorted(_ALLOWED_PROTOCOLS)}, got '{value}'"
        )
    return lower


def validate_interface(value: str) -> str:
    """
    Raise ValueError if *value* contains shell-injection characters or is
    longer than 64 characters.
    """
    if not value or not _INTERFACE_SAFE_RE.match(value):
        raise ValueError(
            f"Interface name '{value}' contains invalid characters. "
            "Only alphanumeric, space, hyphen, underscore, and dot are allowed."
        )
    return value


# ---------------------------------------------------------------------------
# HTTP-layer helpers (raise HTTPException 422 — use in route handlers)
# ---------------------------------------------------------------------------

def require_valid_ipv4(value: str, field: str = "ip_address") -> str:
    try:
        return validate_ipv4(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def require_valid_interface(value: str) -> str:
    try:
        return validate_interface(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
