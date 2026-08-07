#!/usr/bin/env python3
"""
Z-Sentinel Agent (Brute-force + DDoS focused)
============================================
Phiên bản agent riêng, không sửa file agent cũ.

Mục tiêu:
- Theo dõi log web server (Apache/Nginx) trên máy chủ con.
- Phát hiện brute-force login bằng cách đếm các request login thất bại.
- Phát hiện DDoS bằng cách đếm số request đổ vào trong cửa sổ thời gian.
- Gửi event về backend để tạo alert.

Biến môi trường:
    AGENT_SERVER_ID          : ID máy chủ trong DB (0 = auto-register)
    AGENT_API_KEY            : API Key của IDS Backend
    IDS_API_URL              : URL /api/servers của backend
    AGENT_INTERVAL_SECONDS   : Khoảng gửi metrics (mặc định: 10s)
    AGENT_LOG_INTERVAL       : Khoảng quét log (mặc định: 15s)
    AGENT_SSL_VERIFY         : "false" để tắt SSL verify trong LAN
    AGENT_LOG_PATH           : Đường dẫn tới file access log (mặc định: /var/log/apache2/access.log)
    AGENT_LOG_PATHS          : Danh sách file log, cách nhau bằng dấu phẩy
    AGENT_BRUTEFORCE_THRESHOLD : Số request login thất bại để cảnh báo (mặc định: 10)
    AGENT_DDOS_THRESHOLD     : Số request tổng / IP trong cửa sổ để cảnh báo (mặc định: 100)
    AGENT_WINDOW_SECONDS     : Cửa sổ thời gian tính (mặc định: 60s)
    AGENT_COMPAT_MODE        : "true" để dùng event_type tương thích với backend hiện tại
"""

import asyncio
import gzip
import hashlib
import hmac
import json
import logging
import os
import platform
import re
import socket
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, DefaultDict, Dict, List, Optional, Tuple

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SERVER_ID = int(os.environ.get("AGENT_SERVER_ID", "0"))
API_KEY = os.environ.get("AGENT_API_KEY", "changeme-set-API_KEY-in-env")
API_URL = os.environ.get("IDS_API_URL", "http://localhost:8000/api/servers")
INTERVAL = int(os.environ.get("AGENT_INTERVAL_SECONDS", "10"))
LOG_INTERVAL = int(os.environ.get("AGENT_LOG_INTERVAL", "15"))
SSL_VERIFY = os.environ.get("AGENT_SSL_VERIFY", "true").lower() != "false"
COMPAT_MODE = os.environ.get("AGENT_COMPAT_MODE", "true").lower() == "true"
BRUTEFORCE_THRESHOLD = int(os.environ.get("AGENT_BRUTEFORCE_THRESHOLD", "10"))
DDOS_THRESHOLD = int(os.environ.get("AGENT_DDOS_THRESHOLD", "100"))
WINDOW_SECONDS = int(os.environ.get("AGENT_WINDOW_SECONDS", "60"))

ENV_LOG_PATH = os.environ.get("AGENT_LOG_PATH", "")
ENV_LOG_PATHS = os.environ.get("AGENT_LOG_PATHS", "")
LOG_PATHS = [p.strip() for p in (ENV_LOG_PATHS or ENV_LOG_PATH).split(",") if p.strip()]
if not LOG_PATHS:
    LOG_PATHS = ["/var/log/apache2/access.log", "/var/log/nginx/access.log"]

_BATCH_SEND_INTERVAL = 20.0
_EVENTS_QUEUE: List[Dict[str, Any]] = []
_LAST_BATCH_SEND = 0.0

# State trackers
_BRUTEFORCE_TRACKER: DefaultDict[str, List[datetime]] = defaultdict(list)
_DDOS_TRACKER: DefaultDict[str, List[datetime]] = defaultdict(list)
_GLOBAL_DDOS_TRACKER: List[datetime] = []
_LAST_BRUTE_ALERT: DefaultDict[str, datetime] = defaultdict(lambda: datetime.min.replace(tzinfo=timezone.utc))
_LAST_DDOS_ALERT: DefaultDict[str, datetime] = defaultdict(lambda: datetime.min.replace(tzinfo=timezone.utc))
_LAST_GLOBAL_DDOS_ALERT = datetime.min.replace(tzinfo=timezone.utc)
_LOG_LAST_POS: Dict[str, int] = {}


def sign_payload(payload: Dict[str, Any], secret_key: str) -> str:
    payload_str = json.dumps(payload, sort_keys=True)
    mac = hmac.new(secret_key.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()


def compress_payload(payload: Dict[str, Any]) -> bytes:
    json_str = json.dumps(payload)
    return gzip.compress(json_str.encode("utf-8"))


def _read_new_lines(filepath: str) -> List[str]:
    if not os.path.exists(filepath):
        return []

    try:
        last_pos = _LOG_LAST_POS.get(filepath, 0)
        current_size = os.path.getsize(filepath)
        if current_size < last_pos:
            last_pos = 0

        if current_size == last_pos:
            return []

        with open(filepath, "r", errors="ignore") as handle:
            handle.seek(last_pos)
            lines = handle.readlines()
            _LOG_LAST_POS[filepath] = handle.tell()
        return lines
    except (PermissionError, OSError) as exc:
        logger.debug("Cannot read log %s: %s", filepath, exc)
        return []


def _parse_access_line(line: str) -> Optional[Dict[str, Any]]:
    # Common Apache/Nginx access log format:
    # 192.168.1.10 - - [10/Oct/2000:13:55:36 -0700] "POST /DVWA/vulnerabilities/brute/ HTTP/1.1" 401 2326
    pattern = re.compile(
        r'^(?P<ip>\S+) \S+ \S+ \[(?P<ts>[^\]]+)\] "(?P<method>[A-Z]+) (?P<path>\S+) (?P<protocol>HTTP/\d\.\d)" '
        r'(?P<status>\d{3}) '
        r'(?P<size>\S+)'
    )
    match = pattern.match(line.strip())
    if not match:
        return None

    path = match.group("path")
    status = int(match.group("status"))
    method = match.group("method")

    is_failed_login = False
    if status in {401, 403} and (
        "/login" in path.lower() or "/brute" in path.lower() or "brute" in path.lower()
    ):
        is_failed_login = True

    return {
        "ip": match.group("ip"),
        "method": method,
        "path": path,
        "status": status,
        "is_failed_login": is_failed_login,
    }


def _prune_old_entries(entries: List[datetime], now: datetime) -> List[datetime]:
    window_start = now - timedelta(seconds=WINDOW_SECONDS)
    return [ts for ts in entries if ts >= window_start]


def _build_event(event_type: str, source_ip: str, count: int, severity: str, message: str, log_source: str) -> Dict[str, Any]:
    return {
        "event_type": event_type,
        "source_ip": source_ip,
        "count": count,
        "severity": severity,
        "message": message,
        "log_source": log_source,
        "server": platform.node(),
    }


def collect_security_events() -> List[Dict[str, Any]]:
    global _GLOBAL_DDOS_TRACKER
    now = datetime.now(timezone.utc)
    events: List[Dict[str, Any]] = []

    # Scan each configured log path
    for log_path in LOG_PATHS:
        new_lines = _read_new_lines(log_path)
        for line in new_lines:
            parsed = _parse_access_line(line)
            if not parsed:
                continue

            ip = parsed["ip"]
            if parsed["is_failed_login"]:
                _BRUTEFORCE_TRACKER[ip].append(now)
            _DDOS_TRACKER[ip].append(now)
            _GLOBAL_DDOS_TRACKER.append(now)

    # Prune trackers to current window
    for ip in list(_BRUTEFORCE_TRACKER.keys()):
        _BRUTEFORCE_TRACKER[ip] = _prune_old_entries(_BRUTEFORCE_TRACKER[ip], now)
        if not _BRUTEFORCE_TRACKER[ip]:
            del _BRUTEFORCE_TRACKER[ip]

    for ip in list(_DDOS_TRACKER.keys()):
        _DDOS_TRACKER[ip] = _prune_old_entries(_DDOS_TRACKER[ip], now)
        if not _DDOS_TRACKER[ip]:
            del _DDOS_TRACKER[ip]

    _GLOBAL_DDOS_TRACKER = _prune_old_entries(_GLOBAL_DDOS_TRACKER, now)

    # Brute-force detection
    for ip, hits in sorted(_BRUTEFORCE_TRACKER.items()):
        if len(hits) < BRUTEFORCE_THRESHOLD:
            continue
        last_alert = _LAST_BRUTE_ALERT[ip]
        if (now - last_alert).total_seconds() < 30:
            continue
        _LAST_BRUTE_ALERT[ip] = now
        brute_event_type = "ssh_brute_force" if COMPAT_MODE else "web_brute_force"
        events.append(
            _build_event(
                brute_event_type,
                ip,
                len(hits),
                "high" if len(hits) < 20 else "critical",
                f"Web brute-force detected from {ip}: {len(hits)} failed auth attempts in {WINDOW_SECONDS}s",
                ", ".join(LOG_PATHS),
            )
        )

    # DDoS detection (per IP and global)
    for ip, hits in sorted(_DDOS_TRACKER.items()):
        if len(hits) < DDOS_THRESHOLD:
            continue
        last_alert = _LAST_DDOS_ALERT[ip]
        if (now - last_alert).total_seconds() < 30:
            continue
        _LAST_DDOS_ALERT[ip] = now
        ddos_event_type = "syn_flood_inbound" if COMPAT_MODE else "ddos_suspected"
        events.append(
            _build_event(
                ddos_event_type,
                ip,
                len(hits),
                "critical",
                f"Potential DDoS traffic from {ip}: {len(hits)} requests in {WINDOW_SECONDS}s",
                ", ".join(LOG_PATHS),
            )
        )

    if len(_GLOBAL_DDOS_TRACKER) >= DDOS_THRESHOLD:
        if (now - _LAST_GLOBAL_DDOS_ALERT).total_seconds() >= 30:
            _LAST_GLOBAL_DDOS_ALERT = now
            ddos_event_type = "syn_flood_inbound" if COMPAT_MODE else "ddos_suspected"
            events.append(
                _build_event(
                    ddos_event_type,
                    "0.0.0.0",
                    len(_GLOBAL_DDOS_TRACKER),
                    "critical",
                    f"Potential DDoS traffic detected globally: {len(_GLOBAL_DDOS_TRACKER)} requests in {WINDOW_SECONDS}s",
                    ", ".join(LOG_PATHS),
                )
            )

    return events


async def auto_register_server(client: httpx.AsyncClient) -> int:
    global SERVER_ID

    hostname = platform.node()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
    except Exception:
        local_ip = "unknown"

    server_data = {
        "name": hostname,
        "ip_address": local_ip,
        "os": platform.system(),
        "description": f"Auto-registered brute-force/DDOS agent on {hostname}",
    }

    try:
        resp = await client.post(API_URL, json=server_data, headers={"X-API-Key": API_KEY}, timeout=10.0)
        resp.raise_for_status()
        result = resp.json()
        new_id = result.get("id") or result.get("server_id")
        if new_id:
            SERVER_ID = int(new_id)
            logger.info("Server registered successfully with ID %s", SERVER_ID)
            return SERVER_ID
    except Exception as exc:
        logger.error("Auto-register failed: %s", exc)
    return 0


async def send_batch_events(client: httpx.AsyncClient) -> None:
    global _EVENTS_QUEUE, _LAST_BATCH_SEND
    if not _EVENTS_QUEUE:
        return

    batch_to_send = _EVENTS_QUEUE[:50]
    _EVENTS_QUEUE = _EVENTS_QUEUE[50:]

    payload = {
        "server_id": SERVER_ID,
        "events": batch_to_send,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    compressed = compress_payload(payload)
    sig = sign_payload(payload, API_KEY)

    try:
        resp = await client.post(
            f"{API_URL}/{SERVER_ID}/logs",
            content=compressed,
            headers={
                "X-API-Key": API_KEY,
                "X-Signature": sig,
                "Content-Encoding": "gzip",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        logger.info("Sent %d events to backend", len(batch_to_send))
        _LAST_BATCH_SEND = time.monotonic()
    except Exception as exc:
        logger.error("Failed to send batch: %s", exc)
        _EVENTS_QUEUE = batch_to_send + _EVENTS_QUEUE


async def run_agent() -> None:
    logger.info("Starting Brute-force + DDoS agent")
    logger.info("Monitoring log files: %s", ", ".join(LOG_PATHS))
    logger.info("Brute-force threshold: %s | DDoS threshold: %s | Window: %ss", BRUTEFORCE_THRESHOLD, DDOS_THRESHOLD, WINDOW_SECONDS)

    async with httpx.AsyncClient(verify=SSL_VERIFY, timeout=5.0) as client:
        if SERVER_ID == 0:
            registered_id = await auto_register_server(client)
            if not registered_id:
                logger.error("Could not register server; exiting")
                return

        last_scan = 0.0
        while True:
            now = time.monotonic()
            if now - last_scan >= LOG_INTERVAL:
                last_scan = now
                try:
                    events = collect_security_events()
                    if events:
                        _EVENTS_QUEUE.extend(events)
                        logger.info("Collected %d security events", len(events))
                except Exception as exc:
                    logger.error("Error scanning logs: %s", exc)

            if _EVENTS_QUEUE and (time.monotonic() - _LAST_BATCH_SEND) >= _BATCH_SEND_INTERVAL:
                try:
                    await send_batch_events(client)
                except Exception as exc:
                    logger.error("Batch send loop failed: %s", exc)

            await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
