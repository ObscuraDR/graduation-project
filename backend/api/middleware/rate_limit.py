"""
Rate Limiting Middleware
========================
Sliding-window in-memory per-client-IP rate limiter.

Limits (requests per 60-second window):
  /api/sniffer/*   → 10
  /api/whitelist/* → 30
  /api/xai/*       → 60

Returns HTTP 429 with JSON body on breach.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Deque, Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# (max_requests, window_seconds)
_ROUTE_LIMITS: list[Tuple[str, int, int]] = [
    ("/api/sniffer/",    10, 60),
    ("/api/whitelist/",  30, 60),
    ("/api/xai/",        60, 60),
]

# ip:prefix → deque of timestamps
_windows: Dict[str, Deque[float]] = {}
_lock = Lock()

# HTTP Flood detector tracking (ip -> deque of request timestamps)
_http_requests: Dict[str, Deque[float]] = {}
_http_bad_responses: Dict[str, Deque[float]] = {}
_http_cooldown: Dict[str, float] = {}  # ip -> last alert timestamp

HTTP_FLOOD_THRESHOLD = 30     # 30 requests in 5 seconds
HTTP_FLOOD_WINDOW = 5.0       # 5 seconds
COOLDOWN_SECONDS = 30.0       # 30 seconds between alerts per IP


def _get_limit(path: str) -> Tuple[int, int] | None:
    for prefix, max_req, window in _ROUTE_LIMITS:
        if path.startswith(prefix):
            return max_req, window
    return None


def _is_rate_limited(client_ip: str, path: str) -> Tuple[bool, int, int]:
    """
    Returns (limited, limit, retry_after_seconds).
    Uses a sliding window: timestamps older than `window` are evicted.
    """
    rule = _get_limit(path)
    if rule is None:
        return False, 0, 0

    max_req, window = rule
    key = f"{client_ip}:{path.split('/')[2]}"  # e.g. "1.2.3.4:sniffer"
    now = time.monotonic()

    with _lock:
        if key not in _windows:
            _windows[key] = deque()

        dq = _windows[key]

        # evict timestamps outside the window
        cutoff = now - window
        while dq and dq[0] <= cutoff:
            dq.popleft()

        if len(dq) >= max_req:
            retry_after = int(window - (now - dq[0])) + 1
            return True, max_req, retry_after

        dq.append(now)
        return False, max_req, 0


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        ip = _client_ip(request)

        # ── HTTP Flood & Attack Detection for Remote IPs ──
        if ip not in ("127.0.0.1", "::1", "localhost", "0.0.0.0"):
            now = time.monotonic()
            with _lock:
                if ip not in _http_requests:
                    _http_requests[ip] = deque()
                dq = _http_requests[ip]
                dq.append(now)

                # Evict timestamps older than window
                cutoff = now - HTTP_FLOOD_WINDOW
                while dq and dq[0] <= cutoff:
                    dq.popleft()

                count = len(dq)
                last_alert = _http_cooldown.get(ip, 0)

                # If request rate exceeds threshold and not in cooldown
                if count >= HTTP_FLOOD_THRESHOLD and (now - last_alert) >= COOLDOWN_SECONDS:
                    _http_cooldown[ip] = now
                    dq.clear()  # reset count for this burst

                    # Trigger alert via AlertManager asynchronously
                    try:
                        from backend.alert_engine.alert_manager import get_alert_manager
                        alert_mgr = get_alert_manager()
                        synthetic_prediction = {
                            "attack_type": "DDoS",
                            "confidence": 0.96,
                            "severity": "high",
                            "all_probabilities": {"DDoS": 0.96, "Normal": 0.04},
                            "features": {"http_request_rate": count / HTTP_FLOOD_WINDOW},
                            "model_name": "http_flood_detector",
                            "model_version": "1.0",
                        }
                        synthetic_flow = {
                            "src_ip": ip,
                            "dst_ip": "server",
                            "dst_port": 8000,
                            "protocol": "http",
                            "flow_key": f"{ip}:*-server:8000-http",
                        }
                        alert_mgr.generate_alert(synthetic_prediction, synthetic_flow)
                    except Exception as exc:
                        pass

        # ── Standard Route Rate Limiting ──
        limited, limit, retry_after = _is_rate_limited(ip, request.url.path)

        if limited:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Too many requests. Limit: {limit} req/60s per IP.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        return response


def reset_all() -> None:
    """Clear all rate-limit state (test helper)."""
    with _lock:
        _windows.clear()


def reset_ip(client_ip: str) -> None:
    """Clear rate-limit state for one IP (test helper)."""
    with _lock:
        keys = [k for k in _windows if k.startswith(f"{client_ip}:")]
        for k in keys:
            del _windows[k]
