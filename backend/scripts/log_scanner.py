import logging
import re
import time
import os
import threading
import socket
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, Deque, Optional

from backend.config import settings
from backend.alert_engine.alert_manager import AlertManager

logger = logging.getLogger(__name__)

class LogScanner(threading.Thread):
    """
    Quét file log hệ thống (ví dụ: auth.log) để phát hiện các hành vi đáng ngờ
    như SSH Brute Force. Chạy trong một luồng riêng biệt.
    """
    
    # Regex để phát hiện đăng nhập SSH thất bại
    # Ví dụ: "Failed password for root from 192.168.1.100 port 54321 ssh2"
    # Hoặc: "Failed password for invalid user guest from 192.168.1.101 port 12345 ssh2"
    SSH_FAILED_LOGIN_REGEX = re.compile(
        r"Failed password for (?:invalid user )?(\S+) from (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) port \d+ ssh2"
    )

    def __init__(self, alert_manager: AlertManager):
        super().__init__()
        self.daemon = True  # Cho phép luồng kết thúc khi chương trình chính kết thúc
        self._stop_event = threading.Event()
        
        self.alert_manager = alert_manager
        self.log_file_path = settings.auth_log_path
        self.brute_force_threshold = settings.ssh_brute_force_threshold
        self.brute_force_window = timedelta(seconds=settings.ssh_brute_force_window_seconds)
        self.scan_interval = settings.log_scan_interval_seconds
        
        # Dictionary lưu trữ thời gian các lần đăng nhập thất bại của từng IP
        # Key: IP Address (str), Value: deque of datetime objects
        self.failed_attempts: Dict[str, Deque[datetime]] = {}
        self.total_failed: Dict[str, int] = {}
        self._window_alerted: set = set()
        self._block_level: Dict[str, str] = {}  # "1h" | "24h"
        self.file_handle: Optional[object] = None
        self.last_position: int = 0
        
        self.local_ip = self._get_local_ip()
        
        logger.info(f"LogScanner initialized for {self.log_file_path}")
        logger.info(
            "SSH rules: %s fails/%ss → warning | %s → block 1h | %s → block 24h",
            self.brute_force_threshold,
            int(self.brute_force_window.total_seconds()),
            settings.ssh_brute_force_block_threshold,
            settings.ssh_brute_force_severe_threshold,
        )
        
        if not self._check_log_file_access():
            logger.error("LogScanner will not function due to file access issues.")
            self._running = False # Ngăn không cho start nếu không có quyền

    def _get_local_ip(self) -> str:
        """Lấy địa chỉ IP cục bộ của máy chủ."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80)) # Kết nối tới một địa chỉ ngoài để lấy IP cục bộ
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1" # Fallback

    def _check_log_file_access(self) -> bool:
        """Kiểm tra quyền đọc file log."""
        if not os.path.exists(self.log_file_path):
            logger.error(f"Log file not found: {self.log_file_path}")
            return False
        if not os.access(self.log_file_path, os.R_OK):
            logger.error(f"Permission denied to read log file: {self.log_file_path}. "
                         "Run with appropriate privileges (e.g., sudo or add user to 'adm' group).")
            return False
        return True

    def run(self):
        """Phương thức chính của luồng, đọc và xử lý log."""
        self._stop_event.clear()
        try:
            self.file_handle = open(self.log_file_path, 'r', encoding='utf-8', errors='ignore')
            self.file_handle.seek(0, os.SEEK_END) # Bắt đầu đọc từ cuối file
            self.last_position = self.file_handle.tell()
            logger.info(f"LogScanner started, tailing {self.log_file_path} from position {self.last_position}")
        except Exception as e:
            logger.error(f"Failed to open log file {self.log_file_path}: {e}")
            return

        while not self._stop_event.is_set():
            try:
                # Kiểm tra xem file có bị rotate không
                current_position = self.file_handle.tell()
                current_inode = os.fstat(self.file_handle.fileno()).st_ino
                
                # Nếu file bị rotate (inode thay đổi hoặc kích thước nhỏ hơn vị trí cuối cùng)
                if os.path.getsize(self.log_file_path) < current_position or \
                   current_inode != os.stat(self.log_file_path).st_ino:
                    logger.info(f"Log file {self.log_file_path} rotated. Reopening and seeking to end.")
                    self.file_handle.close()
                    self.file_handle = open(self.log_file_path, 'r', encoding='utf-8', errors='ignore')
                    self.file_handle.seek(0, os.SEEK_END)
                    self.last_position = self.file_handle.tell()
                    continue

                line = self.file_handle.readline()
                if not line:
                    self._stop_event.wait(self.scan_interval)
                    continue
                
                self._process_log_line(line)
                self.last_position = self.file_handle.tell()

            except Exception as e:
                logger.error(f"Error processing log line: {e}")
            
        if self.file_handle:
            self.file_handle.close()
        logger.info("LogScanner stopped.")

    def stop(self):
        """Dừng luồng LogScanner."""
        self._stop_event.set()

    def _process_log_line(self, line: str):
        """Xử lý từng dòng log để phát hiện SSH Brute Force."""
        match = self.SSH_FAILED_LOGIN_REGEX.search(line)
        if not match:
            return

        username = match.group(1)
        ip_address = match.group(2)
        current_time = datetime.utcnow()

        if ip_address not in self.failed_attempts:
            self.failed_attempts[ip_address] = deque()

        self.failed_attempts[ip_address].append(current_time)
        self.total_failed[ip_address] = self.total_failed.get(ip_address, 0) + 1

        try:
            from backend.api.routes.geoip import lookup_country
            from backend.database.security_log_store import store_security_log
            country = lookup_country(ip_address)
            store_security_log(
                server=self.local_ip,
                source_ip=ip_address,
                country=country,
                event_type="ssh_login_failed",
                message=line.strip()[:500],
                log_source="auth.log",
                raw=line.strip(),
            )
        except Exception:
            pass

        while self.failed_attempts[ip_address] and \
              self.failed_attempts[ip_address][0] < current_time - self.brute_force_window:
            self.failed_attempts[ip_address].popleft()

        window_count = len(self.failed_attempts[ip_address])
        total_count = self.total_failed[ip_address]
        flow_info = {
            'src_ip': ip_address,
            'dst_ip': self.local_ip,
            'src_port': 22,
            'dst_port': 22,
            'protocol': 'tcp',
        }

        # Rule 1: 5 fails in 1 minute → warning alert
        if window_count >= self.brute_force_threshold and ip_address not in self._window_alerted:
            logger.warning(
                "SSH Brute Force warning from %s (user: %s, %s fails in window)",
                ip_address, username, window_count,
            )
            prediction = {
                'attack_type': 'SSH Brute Force',
                'confidence': 0.95,
                'severity': 'medium',
            }
            self.alert_manager.generate_alert(prediction, flow_info)
            self._window_alerted.add(ip_address)

        # Reset window alert flag when window is empty
        if window_count == 0 and ip_address in self._window_alerted:
            self._window_alerted.discard(ip_address)

        # Rule 3: 100 fails → block 24h (checked before rule 2 so severe wins)
        if total_count >= settings.ssh_brute_force_severe_threshold:
            if self._block_level.get(ip_address) != "24h":
                logger.warning(
                    "SSH Brute Force severe block: %s (%s total fails) → 24h",
                    ip_address, total_count,
                )
                self._apply_block(
                    ip_address, username, total_count,
                    duration_seconds=settings.ssh_brute_force_block_24h_seconds,
                    severity='critical',
                    level='24h',
                    flow_info=flow_info,
                )
            return

        # Rule 2: 20 fails → block 1h
        if total_count >= settings.ssh_brute_force_block_threshold:
            if self._block_level.get(ip_address) not in ("1h", "24h"):
                logger.warning(
                    "SSH Brute Force block: %s (%s total fails) → 1h",
                    ip_address, total_count,
                )
                self._apply_block(
                    ip_address, username, total_count,
                    duration_seconds=settings.ssh_brute_force_block_1h_seconds,
                    severity='high',
                    level='1h',
                    flow_info=flow_info,
                )

    def _apply_block(
        self,
        ip_address: str,
        username: str,
        total_count: int,
        duration_seconds: int,
        severity: str,
        level: str,
        flow_info: dict,
    ):
        """Persist blacklist entry and emit a block alert."""
        prediction = {
            'attack_type': 'SSH Brute Force',
            'confidence': 1.0,
            'severity': severity,
        }
        self.alert_manager.generate_alert(prediction, flow_info)

        self.alert_manager._auto_add_to_blacklist(
            ip_address,
            reason=f"SSH brute force: {total_count} failed logins (user: {username})",
            auto_blocked=True,
            duration_seconds=duration_seconds,
        )
        self.alert_manager.add_to_blacklist(ip_address)
        self._block_level[ip_address] = level