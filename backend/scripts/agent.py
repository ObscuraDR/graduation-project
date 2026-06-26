"""
Z-Sentinel Agent
================
Agent chạy trên máy chủ con, thu thập metrics và gửi về IDS Backend định kỳ.

Cài đặt trên máy chủ con:
    pip install psutil httpx

Chạy:
    python agent.py

Hoặc với biến môi trường:
    AGENT_SERVER_ID=2 AGENT_API_KEY=your_key IDS_API_URL=http://192.168.1.100:8000/api/servers python agent.py

Biến môi trường:
    AGENT_SERVER_ID       : ID máy chủ trong database IDS (mặc định: 1)
    AGENT_API_KEY         : API Key của IDS Backend
    IDS_API_URL           : URL endpoint /api/servers của IDS Backend
    AGENT_INTERVAL_SECONDS: Khoảng thời gian gửi metrics (mặc định: 10s)
    AGENT_SSL_VERIFY      : "false" để tắt SSL verify (dùng trong LAN)
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import platform
import time

import httpx
import psutil

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Cấu hình ────────────────────────────────────────────────────────────────
SERVER_ID = int(os.environ.get("AGENT_SERVER_ID", 1))
API_KEY   = os.environ.get("AGENT_API_KEY", "changeme-set-API_KEY-in-env")
API_URL   = os.environ.get("IDS_API_URL", "http://localhost:8000/api/servers")
INTERVAL  = int(os.environ.get("AGENT_INTERVAL_SECONDS", 10))

_ssl_env  = os.environ.get("AGENT_SSL_VERIFY", "true")
SSL_VERIFY = False if _ssl_env.lower() == "false" else True


def get_system_stats() -> dict:
    """Thu thập các chỉ số hệ thống hiện tại. Xử lý gracefully khi thiếu quyền."""
    # CPU — có thể lỗi trong container/NetHunter
    try:
        cpu = psutil.cpu_percent(interval=1)
    except Exception:
        try:
            # Fallback: đọc /proc/stat thủ công
            with open('/proc/stat', 'r') as f:
                line = f.readline()
            fields = [float(x) for x in line.strip().split()[1:]]
            idle = fields[3]
            total = sum(fields)
            cpu = round((1.0 - idle / total) * 100, 1) if total > 0 else 0.0
        except Exception:
            cpu = 0.0

    # RAM
    try:
        ram = psutil.virtual_memory().percent
    except Exception:
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
            mem = {}
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    mem[parts[0].rstrip(':')] = int(parts[1])
            total_mem = mem.get('MemTotal', 1)
            avail_mem = mem.get('MemAvailable', mem.get('MemFree', 0))
            ram = round((1 - avail_mem / total_mem) * 100, 1) if total_mem > 0 else 0.0
        except Exception:
            ram = 0.0

    # Disk
    disk_path = 'C:\\' if platform.system() == 'Windows' else '/'
    try:
        disk = psutil.disk_usage(disk_path).percent
    except Exception:
        try:
            import subprocess
            out = subprocess.check_output(['df', '-h', '/'], text=True).splitlines()
            if len(out) > 1:
                parts = out[1].split()
                disk = float(parts[4].replace('%', ''))
            else:
                disk = 0.0
        except Exception:
            disk = 0.0

    fw_status = "active" if platform.system() == "Linux" else "enabled"

    return {
        "status":           "online",
        "cpu_usage":        cpu,
        "ram_usage":        ram,
        "disk_usage":       disk,
        "firewall_status":  fw_status,
    }


def sign_payload(payload: dict, secret_key: str) -> str:
    """Tạo chữ ký HMAC-SHA256 cho payload để chống giả mạo."""
    payload_str = json.dumps(payload, sort_keys=True)
    mac = hmac.new(secret_key.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()


async def run_agent() -> None:
    logger.info("=" * 50)
    logger.info("Z-SENTINEL AGENT STARTING")
    logger.info("Server ID : %s", SERVER_ID)
    logger.info("Endpoint  : %s/%s/status", API_URL, SERVER_ID)
    logger.info("Interval  : %ss", INTERVAL)
    logger.info("=" * 50)

    if not SSL_VERIFY:
        logger.warning("SSL verification DISABLED — only use in private LAN")

    async with httpx.AsyncClient(verify=SSL_VERIFY, timeout=5.0) as client:
        while True:
            try:
                stats     = get_system_stats()
                signature = sign_payload(stats, API_KEY)

                resp = await client.post(
                    f"{API_URL}/{SERVER_ID}/status",
                    params=stats,
                    headers={
                        "X-API-Key":   API_KEY,
                        "X-Signature": signature,
                    },
                )
                resp.raise_for_status()
                logger.info(
                    "[%s] OK — CPU=%.1f%% RAM=%.1f%% Disk=%.1f%%",
                    time.strftime("%H:%M:%S"),
                    stats["cpu_usage"],
                    stats["ram_usage"],
                    stats["disk_usage"],
                )
            except httpx.HTTPStatusError as e:
                logger.error("HTTP error %s: %s", e.response.status_code, e.response.text[:200])
            except httpx.RequestError as e:
                logger.error("Connection error: %s — backend unreachable?", e)
            except Exception as e:
                logger.error("Unexpected error: %s", e)

            await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_agent())
