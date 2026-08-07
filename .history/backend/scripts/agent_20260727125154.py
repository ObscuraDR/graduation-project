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
SERVER_ID    = int(os.environ.get("AGENT_SERVER_ID", 0))  # 0 = auto-register
API_KEY      = os.environ.get("AGENT_API_KEY", "changeme-set-API_KEY-in-env")
API_URL      = os.environ.get("IDS_API_URL", "http://localhost:8000/api/servers")
INTERVAL     = int(os.environ.get("AGENT_INTERVAL_SECONDS", 10))
LOG_INTERVAL = int(os.environ.get("AGENT_LOG_INTERVAL", 5))
LOG_PATH     = os.environ.get("AGENT_LOG_PATH", "/var/log/auth.log")

_ssl_env     = os.environ.get("AGENT_SSL_VERIFY", "true")
SSL_VERIFY   = False if _ssl_env.lower() == "false" else True

# Auto-register settings
AUTO_REGISTER = SERVER_ID == 0


def _detect_tailscale_url() -> str:
    """
    Tự động phát hiện Tailscale IP của backend trong Tailnet.
    Ưu tiên:
      1. IDS_API_URL env
      2. Quét các thiết bị trong mạng Tailscale (qua local API hoặc CLI) để tìm IDS Backend (port 8000)
      3. Fallback: http://localhost:8000/api/servers
    """
    env_url = os.environ.get("IDS_API_URL", "")
    if env_url:
        return env_url  # Env đã set → dùng luôn

    peers_ips = []

    # 1. Thử gọi Tailscale Local API (hỗ trợ tốt trên Windows/macOS/Linux khi service đang chạy)
    try:
        response = httpx.get("http://localhost:41112/localapi/v0/status", timeout=1.5)
        if response.status_code == 200:
            data = response.json()
            peer_dict = data.get("Peer", {})
            for peer_id, peer_info in peer_dict.items():
                ips = peer_info.get("TailscaleIPs", [])
                if ips:
                    peers_ips.append(ips[0])
    except Exception:
        pass

    # 2. Nếu local API thất bại, thử gọi tailscale CLI để lấy thông tin
    if not peers_ips:
        try:
            import json
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True, text=True, timeout=3, shell=(platform.system() == "Windows")
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                peer_dict = data.get("Peer", {})
                for peer_id, peer_info in peer_dict.items():
                    ips = peer_info.get("TailscaleIPs", [])
                    if ips:
                        peers_ips.append(ips[0])
        except Exception:
            pass

    # 3. Quét các peers để tìm backend đang lắng nghe trên cổng 8000
    if peers_ips:
        logger.info("Phát hiện mạng Tailscale. Đang quét các peer để tự động kết nối backend...")
        for ip in peers_ips:
            # Bỏ qua IPv6 để quét nhanh hơn và tránh lỗi phân giải trên một số hệ thống
            if ":" in ip:
                continue
            try:
                test_url = f"http://{ip}:8000/health"
                resp = httpx.get(test_url, timeout=1.0)
                if resp.status_code == 200:
                    resp_data = resp.json()
                    if resp_data.get("service") == "IDS Backend":
                        resolved_url = f"http://{ip}:8000/api/servers"
                        logger.info("Đã tự động kết nối đến backend trên Tailscale: %s", resolved_url)
                        return resolved_url
            except Exception:
                pass

    return "http://localhost:8000/api/servers"  # fallback


# Resolve URL (Tailscale auto-detect hoặc env)
if not os.environ.get("IDS_API_URL"):
    API_URL = _detect_tailscale_url()
    logger.info("API_URL resolved to: %s", API_URL)

# ── Ngưỡng phát hiện (lọc tại nguồn) ────────────────────────────────────────
SSH_FAIL_THRESHOLD    = 5    # Số lần fail SSH trong 60s → alert
CPU_SPIKE_THRESHOLD   = 85.0 # CPU% vượt ngưỡng → alert
RAM_SPIKE_THRESHOLD   = 90.0 # RAM% vượt ngưỡng → alert
SYN_CONN_THRESHOLD    = 100  # Số kết nối SYN cùng lúc → alert

# ── State tracking ────────────────────────────────────────────────────────────
_ssh_fail_tracker: Dict[str, List[datetime]] = defaultdict(list)
_web_fail_tracker: Dict[str, List[datetime]] = defaultdict(list)
_log_last_pos: Dict[str, int] = {}  # file path → last read position
_events_queue: List[Dict] = []      # batch queue chưa gửi
_last_batch_send: float = 0.0       # timestamp lần gửi batch cuối
_BATCH_SEND_INTERVAL = 30.0         # Gom batch mỗi 30 giây (Tier 2)
_command_queue: List[Dict] = []     # queue lệnh firewall từ trung tâm
_last_command_fetch: float = 0.0    # timestamp lần fetch lệnh cuối
_COMMAND_FETCH_INTERVAL = 5.0       # Fetch lệnh mỗi 5 giây

# Optional custom web access log paths, separated by ':' or ';'
WEB_LOG_PATHS = [
    path for path in re.split(r'[:;]', os.environ.get("AGENT_WEB_LOG_PATHS", "/var/log/nginx/access.log:/var/log/apache2/access.log"))
    if path
]

# DVWA/web brute force detection thresholds
WEB_ATTACK_SQLI_THRESHOLD = 3
WEB_ATTACK_TRAVERSAL_THRESHOLD = 2
WEB_ATTACK_HTTP_FLOOD_THRESHOLD = 20
DVWA_LOGIN_FAIL_THRESHOLD = 5
DVWA_LOGIN_FAIL_WINDOW_SECONDS = 60


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

# Track các IP đã được local-block và thời điểm hết hạn
# Format: {ip: expires_at_timestamp}
_local_blocks: Dict[str, float] = {}
LOCAL_AUTO_BLOCK_DURATION_HOURS = float(os.environ.get("AGENT_AUTO_BLOCK_HOURS", "1"))
LOCAL_BLOCKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_blocks.json")


def _save_local_blocks_to_file():
    try:
        with open(LOCAL_BLOCKS_FILE, "w") as f:
            json.dump(_local_blocks, f)
    except Exception as e:
        logger.error("Failed to save local blocks to file: %s", e)


def _load_local_blocks_from_file():
    global _local_blocks
    if os.path.exists(LOCAL_BLOCKS_FILE):
        try:
            with open(LOCAL_BLOCKS_FILE, "r") as f:
                data = json.load(f)
                _local_blocks = {ip: float(expiry) for ip, expiry in data.items()}
            logger.info("Loaded %d active local blocks from disk", len(_local_blocks))
        except Exception as e:
            logger.error("Failed to load local blocks from file: %s", e)


def block_ip_local(ip: str, reason: str = "Remote command", duration_hours: float = None) -> bool:
    """
    Chặn IP tại local firewall (iptables/netsh) với thời hạn tự động.
    Lưu vào _local_blocks để auto-unblock sau khi hết giờ.
    """
    dur = duration_hours if duration_hours is not None else LOCAL_AUTO_BLOCK_DURATION_HOURS
    expires_at = time.time() + dur * 3600
    try:
        if platform.system() == "Linux":
            check = subprocess.run(
                ["iptables", "-C", "INPUT", "-s", ip, "-j", "DROP"],
                capture_output=True, text=True
            )
            if check.returncode == 0:
                logger.info("IP %s already blocked locally", ip)
                _local_blocks[ip] = expires_at  # Refresh expiry
                _save_local_blocks_to_file()
                return True

            result = subprocess.run(
                ["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP",
                 "-m", "comment", "--comment", f"Z-Sentinel: {reason}"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                _local_blocks[ip] = expires_at
                _save_local_blocks_to_file()
                logger.info("Blocked %s locally for %.1fh: %s", ip, dur, reason)
                return True
            else:
                logger.error("Failed to block %s: %s", ip, result.stderr)
                return False

        elif platform.system() == "Windows":
            rule_name = f"Z-Sentinel-Block-{ip}"
            check = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}"],
                capture_output=True, text=True
            )
            if check.returncode == 0:
                logger.info("IP %s already blocked locally (Windows)", ip)
                _local_blocks[ip] = expires_at
                _save_local_blocks_to_file()
                return True

            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "add", "rule",
                 f"name={rule_name}", "dir=in", "action=block", f"remoteip={ip}",
                 f"description=Z-Sentinel Auto Block ({dur:.0f}h): {reason}"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                _local_blocks[ip] = expires_at
                _save_local_blocks_to_file()
                logger.info("Blocked %s locally for %.1fh: %s", ip, dur, reason)
                return True
            else:
                logger.error("Failed to block %s: %s", ip, result.stderr)
                return False
        return False
    except Exception as e:
        logger.error("Error blocking IP locally: %s", e)
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
                _save_local_blocks_to_file()
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
                _save_local_blocks_to_file()
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


def scan_windows_bruteforce() -> Optional[Dict]:
    """
    Phát hiện RDP/Windows logon brute force bằng cách quét Security Event Log (Event ID 4625).
    Chỉ chạy trên Windows.
    """
    if platform.system() != "Windows":
        return None
    try:
        # Lấy 30 log Audit Failure gần nhất dưới dạng XML
        result = subprocess.run(
            ["wevtutil", "qe", "Security", "/q:*[System[(EventID=4625)]]", "/c:30", "/f:xml", "/rd:true"],
            capture_output=True, text=True, timeout=5, shell=True
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        # wevtutil trả về các XML block nối tiếp nhau nhưng không bọc trong một root element chung.
        # Chúng ta sẽ bao bọc chúng bằng <Events>...</Events> để parse.
        xml_data = f"<Events>{result.stdout}</Events>"
        
        # Remove namespace definitions to make parsing simpler
        xml_data = re.sub(r'xmlns="[^"]+"', '', xml_data)
        
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_data)
        
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=60)
        new_failures: Dict[str, int] = defaultdict(int)
        
        for event in root.findall("Event"):
            # Lấy timestamp
            time_created = event.find(".//TimeCreated")
            if time_created is None:
                continue
            sys_time = time_created.attrib.get("SystemTime")
            if not sys_time:
                continue
            
            try:
                # Cắt bớt phần microsecond nếu quá dài để datetime.fromisoformat đọc được
                clean_time = re.sub(r'\.\d+Z$', 'Z', sys_time)
                # Thay Z thành +00:00
                if clean_time.endswith('Z'):
                    clean_time = clean_time[:-1] + "+00:00"
                event_time = datetime.fromisoformat(clean_time)
            except Exception:
                continue
                
            # Chỉ xét các sự kiện trong vòng 60 giây qua
            if event_time < window_start:
                continue
                
            # Tìm IP Address và Username
            ip = None
            for data in event.findall(".//Data"):
                name = data.attrib.get("Name")
                if name == "IpAddress":
                    ip = data.text
                    break
            
            # Bỏ qua các địa chỉ local loopback hoặc rỗng
            if ip and ip not in ("-", "127.0.0.1", "::1"):
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
                logger.warning("Windows logon failure spike detected from %s: %d attempts/60s", ip, count)
                return {
                    "event_type": "windows_logon_brute_force",
                    "source_ip": ip,
                    "count": count,
                    "severity": "high" if count < 20 else "critical",
                    "message": f"Windows logon brute force: {count} failed attempts from {ip} in 60s",
                    "log_source": "Security Event Log (4625)",
                }
    except Exception as e:
        logger.debug("Error scanning Windows logon logs: %s", e)
        
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


def _parse_access_log_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse dòng access log và trả về IP, method, path, status nếu có."""
    match = re.search(r'^(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+[^\s]+\s+[^\s]+\s+"(?P<method>GET|POST|PUT|DELETE|HEAD)\s+(?P<path>[^\s]+)\s+HTTP/\d\.\d"\s+(?P<status>\d{3})', line)
    if not match:
        return None
    return {
        "ip": match.group("ip"),
        "method": match.group("method"),
        "path": match.group("path"),
        "status": int(match.group("status")),
    }


def scan_web_attacks(log_path: str) -> Optional[Dict]:
    """
    Phát hiện tấn công web từ nginx/apache access.log.
    Phát hiện: DVWA brute force, SQL injection, path traversal, DDoS.
    """
    new_lines = _read_new_lines(log_path)
    if not new_lines:
        return None

    sqli_pattern = re.compile(r"(union.*select|select.*from|drop.*table|insert.*into|'.*or.*'|1=1|--\s)", re.IGNORECASE)
    traversal_pattern = re.compile(r"\.\./|\.\.\\|%2e%2e|etc/passwd|etc/shadow", re.IGNORECASE)
    dvwa_login_path = re.compile(r"/dvwa/.*(login\.php|vulnerabilities/brute/|login\.php|brute)", re.IGNORECASE)

    sqli_ips: Dict[str, int] = defaultdict(int)
    traversal_ips: Dict[str, int] = defaultdict(int)
    error_ips: Dict[str, int] = defaultdict(int)
    dvwa_fail_ips: Dict[str, int] = defaultdict(int)
    dvwa_request_ips: Dict[str, int] = defaultdict(int)

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=DVWA_LOGIN_FAIL_WINDOW_SECONDS)

    for line in new_lines:
        parsed = _parse_access_log_line(line)
        if not parsed:
            continue

        ip = parsed["ip"]
        path = parsed["path"]
        status = parsed["status"]

        if sqli_pattern.search(line):
            sqli_ips[ip] += 1
        if traversal_pattern.search(line):
            traversal_ips[ip] += 1

        if status >= 400 and status < 600:
            error_ips[ip] += 1

        if dvwa_login_path.search(path):
            dvwa_request_ips[ip] += 1
            if status in (401, 403):
                _web_fail_tracker[ip].append(now)
                dvwa_fail_ips[ip] += 1

    # Dọn dẹp các IP DVWA cũ ngoài cửa sổ thời gian
    for ip in list(_web_fail_tracker.keys()):
        _web_fail_tracker[ip] = [t for t in _web_fail_tracker[ip] if t >= window_start]
        if not _web_fail_tracker[ip]:
            del _web_fail_tracker[ip]

    for ip, timestamps in _web_fail_tracker.items():
        count = len(timestamps)
        if count >= DVWA_LOGIN_FAIL_THRESHOLD:
            return {
                "event_type": "web_brute_force",
                "source_ip": ip,
                "count": count,
                "severity": "high" if count < 20 else "critical",
                "message": f"DVWA login brute force detected from {ip}: {count} failed login attempts in {DVWA_LOGIN_FAIL_WINDOW_SECONDS}s",
                "log_source": log_path,
                "attack_type": "dvwa_login_brute_force",
            }

    # Nếu có nhiều request đến endpoint DVWA brute force payload trong thời gian ngắn
    for ip, count in dvwa_request_ips.items():
        if count >= DVWA_LOGIN_FAIL_THRESHOLD * 2:
            return {
                "event_type": "web_brute_force",
                "source_ip": ip,
                "count": count,
                "severity": "medium",
                "message": f"High DVWA request rate from {ip}: {count} DVWA-related requests",
                "log_source": log_path,
                "attack_type": "dvwa_request_flood",
            }

    for ip, count in sqli_ips.items():
        if count >= WEB_ATTACK_SQLI_THRESHOLD:
            return {
                "event_type": "sql_injection",
                "source_ip": ip,
                "count": count,
                "severity": "critical" if count >= 10 else "high",
                "message": f"SQL injection attempts from {ip}: {count} requests in access log",
                "log_source": log_path,
                "attack_type": "sql_injection",
            }

    for ip, count in traversal_ips.items():
        if count >= WEB_ATTACK_TRAVERSAL_THRESHOLD:
            return {
                "event_type": "path_traversal",
                "source_ip": ip,
                "count": count,
                "severity": "high",
                "message": f"Path traversal attempts from {ip}: {count} requests",
                "log_source": log_path,
                "attack_type": "path_traversal",
            }

    for ip, count in error_ips.items():
        if count >= WEB_ATTACK_HTTP_FLOOD_THRESHOLD:
            return {
                "event_type": "http_flood",
                "source_ip": ip,
                "count": count,
                "severity": "medium",
                "message": f"HTTP flood from {ip}: {count} error responses",
                "log_source": log_path,
                "attack_type": "http_flood",
            }

    return None


def scan_network_anomaly() -> Optional[Dict]:
    """Phát hiện lượng kết nối SYN bất thường."""
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
    ★ Tự động phản ứng LOCAL khi phát hiện tấn công nghiêm trọng.
    """
    events = []

    # 1. SSH brute force từ auth.log (Linux)
    if platform.system() == "Linux" and os.path.exists(LOG_PATH):
        ev = scan_ssh_bruteforce(LOG_PATH)
        if ev:
            events.append(ev)
            src_ip = ev.get("source_ip")
            severity = ev.get("severity", "low")
            if src_ip and severity in ("high", "critical"):
                logger.warning("[LOCAL RESPONSE] Auto-blocking %s (SSH brute force)", src_ip)
                success = block_ip_local(src_ip, reason=f"Local auto-block: {ev['message']}")
                ev["local_blocked"] = success
                ev["local_action"] = "blocked" if success else "block_failed"

    # 1b. Windows Logon brute force từ Security Event Log (Windows)
    if platform.system() == "Windows":
        ev = scan_windows_bruteforce()
        if ev:
            events.append(ev)
            src_ip = ev.get("source_ip")
            severity = ev.get("severity", "low")
            if src_ip and severity in ("high", "critical"):
                logger.warning("[LOCAL RESPONSE] Auto-blocking %s (Windows logon brute force)", src_ip)
                success = block_ip_local(src_ip, reason=f"Local auto-block: {ev['message']}")
                ev["local_blocked"] = success
                ev["local_action"] = "blocked" if success else "block_failed"

    # 2. Web server attacks từ access log web
    for web_log in WEB_LOG_PATHS:
        if os.path.exists(web_log):
            ev = scan_web_attacks(web_log)
            if ev:
                events.append(ev)
                if ev.get("attack_type") in ("sql_injection", "path_traversal", "dvwa_login_brute_force", "dvwa_request_flood"):
                    src_ip = ev.get("source_ip")
                    if src_ip:
                        logger.warning("[LOCAL RESPONSE] Auto-blocking %s (web attack: %s)", src_ip, ev.get("attack_type"))
                        block_ip_local(src_ip, reason=f"Web attack: {ev.get('attack_type')}", duration_hours=0.5)
                        ev["local_blocked"] = True

    # 3. Resource spike
    ev = scan_cpu_spike(cpu, ram)
    if ev:
        events.append(ev)

    # 4. Network anomaly
    ev = scan_network_anomaly()
    if ev:
        events.append(ev)
        if ev.get("event_type") == "syn_flood_inbound" and ev.get("severity") == "high":
            logger.warning("[LOCAL RESPONSE] SYN flood detected (%d connections).", ev.get("count", 0))
            ev["local_action"] = "rate_limit_recommended"

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
    duration_hours = command.get("duration_hours", LOCAL_AUTO_BLOCK_DURATION_HOURS)

    if action == "block":
        return block_ip_local(ip, reason, duration_hours=float(duration_hours))
    elif action == "unblock":
        _local_blocks.pop(ip, None)  # Xóa khỏi tracking
        return unblock_ip_local(ip)
    else:
        logger.warning("Unknown command action: %s", action)
        return False


def auto_unblock_check() -> int:
    """
    Kiểm tra và tự động unblock các IP đã hết thời hạn.
    Gọi định kỳ trong run_agent loop.
    Returns: số IP đã được unblock.
    """
    now = time.time()
    expired = [ip for ip, exp in list(_local_blocks.items()) if now >= exp]
    unblocked = 0
    for ip in expired:
        logger.info("Auto-unblocking expired block: %s", ip)
        if unblock_ip_local(ip):
            del _local_blocks[ip]
            unblocked += 1
        else:
            # Nếu unblock fail → thử lần sau
            logger.warning("Auto-unblock failed for %s, will retry", ip)
    if unblocked:
        _save_local_blocks_to_file()
        logger.info("Auto-unblocked %d expired IPs", unblocked)
    return unblocked


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


# ── Auto-Register Function ─────────────────────────────────────────────────────

async def auto_register_server(client: httpx.AsyncClient) -> int:
    """
    Tự động đăng ký server mới trong database nếu SERVER_ID=0.
    Trả về ID của server đã tạo.
    """
    global SERVER_ID
    
    hostname = platform.node()
    os_type = platform.system()
    
    # Lấy IP address local
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "unknown"
    
    server_data = {
        "name": hostname,
        "ip_address": local_ip,
        "os": os_type,
        "description": f"Auto-registered agent on {hostname}"
    }
    
    try:
        logger.info("Auto-registering new server: %s (IP: %s)", hostname, local_ip)
        register_url = API_URL.rstrip("/") + "/"
        resp = await client.post(
            register_url,
            json=server_data,
            headers={"X-API-Key": API_KEY},
            timeout=10.0
        )
        resp.raise_for_status()
        result = resp.json()
        
        # API có thể trả về {id: 1} hoặc {server_id: 1}
        new_id = result.get("id") or result.get("server_id")
        if new_id:
            SERVER_ID = new_id
            logger.info("✓ Server registered successfully! Assigned ID: %d", SERVER_ID)
            return SERVER_ID
        else:
            logger.error("Failed to get server ID from response: %s", result)
            return 0
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error during auto-registration: %s", e.response.text[:200])
        return 0
    except Exception as e:
        logger.error("Error during auto-registration: %s", e)
        return 0


# ── Main Agent Loop ───────────────────────────────────────────────────────────

async def run_agent() -> None:
    global _last_batch_send, _last_command_fetch, _events_queue, SERVER_ID
    logger.info("=" * 55)
    logger.info("Z-SENTINEL AGENT v2 STARTING")
    logger.info("Server ID     : %s", SERVER_ID if not AUTO_REGISTER else "auto-registering...")
    logger.info("Metrics URL   : %s/%s/status", API_URL, SERVER_ID if not AUTO_REGISTER else "<pending>")
    logger.info("Logs URL      : %s/%s/logs", API_URL, SERVER_ID if not AUTO_REGISTER else "<pending>")
    logger.info("Commands URL : %s/%s/commands", API_URL, SERVER_ID if not AUTO_REGISTER else "<pending>")
    logger.info("Metric interval: %ss | Log interval: %ss", INTERVAL, LOG_INTERVAL)
    logger.info("=" * 55)

    # Nạp danh sách chặn cũ từ ổ đĩa nếu có
    _load_local_blocks_from_file()

    if not SSL_VERIFY:
        logger.warning("SSL verification DISABLED — only use in private LAN")

    last_log_scan = 0.0

    async with httpx.AsyncClient(verify=SSL_VERIFY, timeout=5.0) as client:
        # Auto-register nếu SERVER_ID=0
        if AUTO_REGISTER:
            registered_id = await auto_register_server(client)
            if registered_id == 0:
                logger.error("Failed to auto-register server. Exiting.")
                return
            logger.info("Updated Server ID to: %d", SERVER_ID)
        
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

            # ── 5. Auto-unblock IPs hết hạn (mỗi 60 giây) ────────────────────
            if int(time.monotonic()) % 60 == 0:
                try:
                    auto_unblock_check()
                except Exception as e:
                    logger.debug("Auto-unblock check error: %s", e)

            # ── 5. Sleep đến lần gửi tiếp theo ─────────────────────────────
            elapsed = time.monotonic() - loop_start
            sleep_time = max(0, INTERVAL - elapsed)
            await asyncio.sleep(sleep_time)


if __name__ == "__main__":
    asyncio.run(run_agent())
