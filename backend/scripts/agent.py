"""
Z-Sentinel Agent v2
====================
Agent chạy trên máy chủ con:
  1. Thu thập metrics (CPU/RAM/Disk) mỗi 10 giây
  2. Phân tích log bảo mật LOCAL → chỉ gửi events đáng ngờ
     (lọc tại nguồn để tránh overload backend)

Biến môi trường:
    AGENT_SERVER_ID          : ID máy chủ trong DB (mặc định: 1)
    AGENT_API_KEY            : API Key của IDS Backend
    IDS_API_URL              : URL /api/servers của backend
    AGENT_INTERVAL_SECONDS   : Khoảng gửi metrics (mặc định: 10s)
    AGENT_LOG_INTERVAL       : Khoảng quét log bảo mật (mặc định: 30s)
    AGENT_SSL_VERIFY         : "false" để tắt SSL verify trong LAN
    AGENT_LOG_PATH           : Path file auth.log (mặc định: /var/log/auth.log)
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
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

import httpx
import psutil

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Cấu hình ────────────────────────────────────────────────────────────────
SERVER_ID    = int(os.environ.get("AGENT_SERVER_ID", 1))
API_KEY      = os.environ.get("AGENT_API_KEY", "changeme-set-API_KEY-in-env")
API_URL      = os.environ.get("IDS_API_URL", "http://localhost:8000/api/servers")
INTERVAL     = int(os.environ.get("AGENT_INTERVAL_SECONDS", 10))
LOG_INTERVAL = int(os.environ.get("AGENT_LOG_INTERVAL", 30))
LOG_PATH     = os.environ.get("AGENT_LOG_PATH", "/var/log/auth.log")

_ssl_env     = os.environ.get("AGENT_SSL_VERIFY", "true")
SSL_VERIFY   = False if _ssl_env.lower() == "false" else True

# ── Ngưỡng phát hiện (lọc tại nguồn) ────────────────────────────────────────
SSH_FAIL_THRESHOLD    = 5    # Số lần fail SSH trong 60s → alert
CPU_SPIKE_THRESHOLD   = 85.0 # CPU% vượt ngưỡng → alert
RAM_SPIKE_THRESHOLD   = 90.0 # RAM% vượt ngưỡng → alert
SYN_CONN_THRESHOLD    = 100  # Số kết nối SYN cùng lúc → alert

# ── State tracking ────────────────────────────────────────────────────────────
_ssh_fail_tracker: Dict[str, List[datetime]] = defaultdict(list)
_log_last_pos: Dict[str, int] = {}  # file path → last read position
_events_queue: List[Dict] = []      # batch queue chưa gửi
_last_batch_send: float = 0.0       # timestamp lần gửi batch cuối
_BATCH_SEND_INTERVAL = 30.0         # Gom batch mỗi 30 giây (Tier 2)
_command_queue: List[Dict] = []     # queue lệnh firewall từ trung tâm
_last_command_fetch: float = 0.0    # timestamp lần fetch lệnh cuối
_COMMAND_FETCH_INTERVAL = 5.0       # Fetch lệnh mỗi 5 giây


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_system_stats() -> dict:
    """Thu thập metrics hệ thống, xử lý gracefully khi thiếu quyền."""
    # CPU
    try:
        cpu = psutil.cpu_percent(interval=1)
    except Exception:
        try:
            with open('/proc/stat', 'r') as f:
                line = f.readline()
            fields = [float(x) for x in line.strip().split()[1:]]
            idle = fields[3]; total = sum(fields)
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
            disk = float(out[1].split()[4].replace('%', '')) if len(out) > 1 else 0.0
        except Exception:
            disk = 0.0

    fw_status = "active" if platform.system() == "Linux" else "enabled"
    return {
        "status": "online",
        "cpu_usage": cpu,
        "ram_usage": ram,
        "disk_usage": disk,
        "firewall_status": fw_status,
    }


def sign_payload(payload: dict, secret_key: str) -> str:
    """HMAC-SHA256 signature để chống giả mạo."""
    payload_str = json.dumps(payload, sort_keys=True)
    mac = hmac.new(secret_key.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()


def compress_payload(payload: dict) -> bytes:
    """Compress JSON payload với gzip để giảm bandwidth (Tier 2)."""
    json_str = json.dumps(payload)
    return gzip.compress(json_str.encode("utf-8"))


# ── Local Firewall Execution ─────────────────────────────────────────────────────

def block_ip_local(ip: str, reason: str = "Remote command") -> bool:
    """Chặn IP tại local firewall (iptables/netsh)."""
    try:
        if platform.system() == "Linux":
            # Check if already blocked
            check = subprocess.run(
                ["iptables", "-C", "INPUT", "-s", ip, "-j", "DROP"],
                capture_output=True, text=True
            )
            if check.returncode == 0:
                logger.info(f"IP {ip} already blocked locally")
                return True
            
            # Block with comment
            result = subprocess.run(
                ["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP",
                 "-m", "comment", "--comment", f"Z-Sentinel: {reason}"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                logger.info(f"Blocked {ip} locally: {reason}")
                return True
            else:
                logger.error(f"Failed to block {ip}: {result.stderr}")
                return False
                
        elif platform.system() == "Windows":
            rule_name = f"Z-Sentinel-Block-{ip}"
            # Check if rule exists
            check = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}"],
                capture_output=True, text=True
            )
            if check.returncode == 0:
                logger.info(f"IP {ip} already blocked locally")
                return True
            
            # Add rule
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "add", "rule",
                 f"name={rule_name}", "dir=in", "action=block", f"remoteip={ip}",
                 f"description=Z-Sentinel Remote Block: {reason}"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                logger.info(f"Blocked {ip} locally: {reason}")
                return True
            else:
                logger.error(f"Failed to block {ip}: {result.stderr}")
                return False
        return False
    except Exception as e:
        logger.error(f"Error blocking IP locally: {e}")
        return False


def unblock_ip_local(ip: str) -> bool:
    """Gỡ chặn IP tại local firewall."""
    try:
        if platform.system() == "Linux":
            result = subprocess.run(
                ["iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                logger.info(f"Unblocked {ip} locally")
                return True
            else:
                logger.error(f"Failed to unblock {ip}: {result.stderr}")
                return False
                
        elif platform.system() == "Windows":
            rule_name = f"Z-Sentinel-Block-{ip}"
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                logger.info(f"Unblocked {ip} locally")
                return True
            else:
                logger.error(f"Failed to unblock {ip}: {result.stderr}")
                return False
        return False
    except Exception as e:
        logger.error(f"Error unblocking IP locally: {e}")
        return False


# ── Security Log Scanner (lọc tại nguồn) ─────────────────────────────────────

def _read_new_lines(filepath: str) -> List[str]:
    """
    Đọc chỉ các dòng MỚI từ file log kể từ lần đọc trước.
    Dùng file position để không đọc lại từ đầu → tiết kiệm CPU/IO.
    """
    if not os.path.exists(filepath):
        return []
    try:
        last_pos = _log_last_pos.get(filepath, 0)
        current_size = os.path.getsize(filepath)

        # File bị rotate (shrink) → đọc lại từ đầu
        if current_size < last_pos:
            last_pos = 0

        if current_size == last_pos:
            return []  # Không có gì mới

        with open(filepath, 'r', errors='ignore') as f:
            f.seek(last_pos)
            new_lines = f.readlines()
            _log_last_pos[filepath] = f.tell()

        return new_lines
    except (PermissionError, OSError) as e:
        logger.debug("Cannot read log %s: %s", filepath, e)
        return []


def scan_ssh_bruteforce(log_path: str) -> Optional[Dict]:
    """
    Phát hiện SSH brute force bằng cách đếm 'Failed password' trong cửa sổ 60 giây.
    Chỉ trả về event nếu vượt ngưỡng — không gửi từng dòng log.
    """
    new_lines = _read_new_lines(log_path)
    if not new_lines:
        return None

    # Regex extract IP từ dòng auth.log
    pattern = re.compile(r'Failed password.*from\s+(\d+\.\d+\.\d+\.\d+)', re.IGNORECASE)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=60)

    new_failures: Dict[str, int] = defaultdict(int)

    for line in new_lines:
        m = pattern.search(line)
        if m:
            ip = m.group(1)
            _ssh_fail_tracker[ip].append(now)
            new_failures[ip] += 1

    # Dọn dẹp entries cũ ngoài cửa sổ 60s
    for ip in list(_ssh_fail_tracker.keys()):
        _ssh_fail_tracker[ip] = [t for t in _ssh_fail_tracker[ip] if t >= window_start]
        if not _ssh_fail_tracker[ip]:
            del _ssh_fail_tracker[ip]

    # Kiểm tra vượt ngưỡng
    for ip, timestamps in _ssh_fail_tracker.items():
        count = len(timestamps)
        if count >= SSH_FAIL_THRESHOLD:
            logger.warning("SSH brute force detected from %s: %d attempts/60s", ip, count)
            return {
                "event_type": "ssh_brute_force",
                "source_ip": ip,
                "count": count,
                "severity": "high" if count < 20 else "critical",
                "message": f"SSH brute force: {count} failed attempts from {ip} in 60s",
                "log_source": "auth.log",
            }

    return None


def scan_cpu_spike(cpu: float, ram: float) -> Optional[Dict]:
    """Phát hiện CPU/RAM spike bất thường (dấu hiệu DDoS hoặc cryptomining)."""
    if cpu >= CPU_SPIKE_THRESHOLD:
        return {
            "event_type": "cpu_spike",
            "source_ip": None,
            "count": 1,
            "severity": "medium" if cpu < 95 else "high",
            "message": f"CPU spike detected: {cpu:.1f}% (threshold: {CPU_SPIKE_THRESHOLD}%)",
            "log_source": "psutil",
        }
    if ram >= RAM_SPIKE_THRESHOLD:
        return {
            "event_type": "ram_spike",
            "source_ip": None,
            "count": 1,
            "severity": "medium",
            "message": f"RAM spike detected: {ram:.1f}% (threshold: {RAM_SPIKE_THRESHOLD}%)",
            "log_source": "psutil",
        }
    return None


def scan_network_anomaly() -> Optional[Dict]:
    """Phát hiện lượng kết nối SYN bất thường (dấu hiệu đang bị tấn công hoặc đang tấn công)."""
    try:
        conns = psutil.net_connections(kind='tcp')
        syn_sent  = sum(1 for c in conns if c.status == 'SYN_SENT')
        syn_recv  = sum(1 for c in conns if c.status == 'SYN_RECV')
        time_wait = sum(1 for c in conns if c.status == 'TIME_WAIT')

        if syn_recv >= SYN_CONN_THRESHOLD:
            return {
                "event_type": "syn_flood_inbound",
                "source_ip": None,
                "count": syn_recv,
                "severity": "high",
                "message": f"SYN flood (inbound): {syn_recv} SYN_RECV connections",
                "log_source": "psutil.net_connections",
            }
        if syn_sent >= SYN_CONN_THRESHOLD:
            return {
                "event_type": "syn_flood_outbound",
                "source_ip": None,
                "count": syn_sent,
                "severity": "medium",
                "message": f"Abnormal outbound SYN: {syn_sent} SYN_SENT connections",
                "log_source": "psutil.net_connections",
            }
    except (psutil.AccessDenied, PermissionError):
        pass
    except Exception as e:
        logger.debug("Network scan error: %s", e)
    return None


def collect_security_events(cpu: float, ram: float) -> List[Dict]:
    """
    Gom tất cả security events từ nhiều nguồn.
    Chỉ trả về events vượt ngưỡng — KHÔNG gửi log bình thường.
    Đây là bộ lọc tại nguồn để giảm tải backend.
    """
    events = []

    # 1. SSH brute force (chỉ trên Linux)
    if platform.system() == "Linux" and os.path.exists(LOG_PATH):
        ev = scan_ssh_bruteforce(LOG_PATH)
        if ev:
            events.append(ev)

    # 2. Resource spike
    ev = scan_cpu_spike(cpu, ram)
    if ev:
        events.append(ev)

    # 3. Network anomaly
    ev = scan_network_anomaly()
    if ev:
        events.append(ev)

    return events


# ── Command Fetching from Central Server ─────────────────────────────────────────

async def fetch_firewall_commands(client: httpx.AsyncClient) -> List[Dict]:
    """Fetch pending firewall commands from central server."""
    try:
        resp = await client.get(
            f"{API_URL}/{SERVER_ID}/commands",
            headers={"X-API-Key": API_KEY},
            timeout=5.0
        )
        if resp.status_code == 200:
            commands = resp.json()
            return commands.get("commands", [])
        else:
            logger.debug("No pending commands or error fetching")
            return []
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error fetching commands: %s", e.response.status_code)
        return []
    except httpx.RequestError as e:
        logger.error("Connection error fetching commands: %s", e)
        return []
    except Exception as e:
        logger.error("Error fetching commands: %s", e)
        return []


async def execute_firewall_command(command: Dict) -> bool:
    """Execute a firewall command from central server."""
    action = command.get("action")
    ip = command.get("ip")
    reason = command.get("reason", "Remote command")
    
    if action == "block":
        return block_ip_local(ip, reason)
    elif action == "unblock":
        return unblock_ip_local(ip)
    else:
        logger.warning(f"Unknown command action: {action}")
        return False


async def process_pending_commands(client: httpx.AsyncClient) -> None:
    """Fetch and execute pending firewall commands."""
    commands = await fetch_firewall_commands(client)
    if not commands:
        return
    
    logger.info(f"Received {len(commands)} firewall commands from central server")
    executed = 0
    for cmd in commands:
        try:
            if await execute_firewall_command(cmd):
                executed += 1
                logger.info(f"Executed command: {cmd.get('action')} {cmd.get('ip')}")
        except Exception as e:
            logger.error(f"Error executing command {cmd}: {e}")
    
    if executed > 0:
        logger.info(f"Successfully executed {executed}/{len(commands)} commands")


# ── Main Agent Loop ───────────────────────────────────────────────────────────

async def run_agent() -> None:
    logger.info("=" * 55)
    logger.info("Z-SENTINEL AGENT v2 STARTING")
    logger.info("Server ID     : %s", SERVER_ID)
    logger.info("Metrics URL   : %s/%s/status", API_URL, SERVER_ID)
    logger.info("Logs URL      : %s/%s/logs", API_URL, SERVER_ID)
    logger.info("Commands URL : %s/%s/commands", API_URL, SERVER_ID)
    logger.info("Metric interval: %ss | Log interval: %ss", INTERVAL, LOG_INTERVAL)
    logger.info("=" * 55)

    if not SSL_VERIFY:
        logger.warning("SSL verification DISABLED — only use in private LAN")

    last_log_scan = 0.0

    async with httpx.AsyncClient(verify=SSL_VERIFY, timeout=5.0) as client:
        while True:
            loop_start = time.monotonic()

            # ── 1. Gửi metrics mỗi INTERVAL giây ──────────────────────────
            try:
                stats = get_system_stats()
                sig = sign_payload(stats, API_KEY)
                resp = await client.post(
                    f"{API_URL}/{SERVER_ID}/status",
                    params=stats,
                    headers={"X-API-Key": API_KEY, "X-Signature": sig},
                )
                resp.raise_for_status()
                logger.info(
                    "[%s] Metrics OK — CPU=%.1f%% RAM=%.1f%% Disk=%.1f%%",
                    time.strftime("%H:%M:%S"),
                    stats["cpu_usage"], stats["ram_usage"], stats["disk_usage"],
                )
            except httpx.HTTPStatusError as e:
                logger.error("HTTP error %s: %s", e.response.status_code, e.response.text[:100])
            except httpx.RequestError as e:
                logger.error("Connection error: %s — backend unreachable?", e)
            except Exception as e:
                logger.error("Unexpected metrics error: %s", e)

            # ── 2. Quét log bảo mật mỗi LOG_INTERVAL giây ─────────────────
            now = time.monotonic()
            if now - last_log_scan >= LOG_INTERVAL:
                last_log_scan = now
                try:
                    events = collect_security_events(
                        stats.get("cpu_usage", 0),
                        stats.get("ram_usage", 0)
                    )

                    # Tier 2: Gom events vào batch queue thay vì gửi ngay
                    if events:
                        _events_queue.extend(events)
                        logger.debug(
                            "[%s] Added %d events to batch queue (total: %d)",
                            time.strftime("%H:%M:%S"), len(events), len(_events_queue)
                        )
                    else:
                        logger.debug("[%s] Log scan: no anomalies", time.strftime("%H:%M:%S"))

                except Exception as e:
                    logger.error("Log scan error: %s", e)

            # ── 3. Gửi batch events mỗi _BATCH_SEND_INTERVAL giây (Tier 2) ──
            batch_elapsed = time.monotonic() - _last_batch_send
            if _events_queue and batch_elapsed >= _BATCH_SEND_INTERVAL:
                try:
                    # Lấy batch tối đa 50 events để tránh payload quá lớn
                    batch_to_send = _events_queue[:50]
                    _events_queue = _events_queue[50:]

                    payload = {
                        "server_id": SERVER_ID,
                        "events": batch_to_send,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    sig_log = sign_payload(payload, API_KEY)

                    # Tier 2: Gửi với gzip compression
                    compressed_data = compress_payload(payload)
                    log_resp = await client.post(
                        f"{API_URL}/{SERVER_ID}/logs",
                        content=compressed_data,
                        headers={
                            "X-API-Key": API_KEY,
                            "X-Signature": sig_log,
                            "Content-Encoding": "gzip",
                            "Content-Type": "application/json",
                        },
                    )
                    log_resp.raise_for_status()
                    logger.warning(
                        "[%s] Batch sent: %d events (compressed)",
                        time.strftime("%H:%M:%S"), len(batch_to_send)
                    )
                    for ev in batch_to_send[:3]:  # Chỉ log 3 events đầu để tránh spam
                        logger.warning("  → [%s] %s", ev["event_type"], ev["message"])
                    if len(batch_to_send) > 3:
                        logger.warning("  → ... and %d more", len(batch_to_send) - 3)

                    _last_batch_send = time.monotonic()

                except httpx.HTTPStatusError as e:
                    logger.error("HTTP error sending batch: %s", e.response.text[:100])
                    # Rollback: đưa lại vào queue để thử lại sau
                    _events_queue = batch_to_send + _events_queue
                except Exception as e:
                    logger.error("Batch send error: %s", e)
                    # Rollback: đưa lại vào queue
                    _events_queue = batch_to_send + _events_queue

            # ── 4. Fetch và thực hiện lệnh firewall từ trung tâm ─────────────
            command_elapsed = time.monotonic() - _last_command_fetch
            if command_elapsed >= _COMMAND_FETCH_INTERVAL:
                _last_command_fetch = time.monotonic()
                try:
                    await process_pending_commands(client)
                except Exception as e:
                    logger.error("Error processing firewall commands: %s", e)

            # ── 5. Sleep đến lần gửi tiếp theo ─────────────────────────────
            elapsed = time.monotonic() - loop_start
            sleep_time = max(0, INTERVAL - elapsed)
            await asyncio.sleep(sleep_time)


if __name__ == "__main__":
    asyncio.run(run_agent())
