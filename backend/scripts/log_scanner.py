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
        self._running = False
        
        self.alert_manager = alert_manager
        self.log_file_path = settings.auth_log_path
        self.brute_force_threshold = settings.ssh_brute_force_threshold
        self.brute_force_window = timedelta(seconds=settings.ssh_brute_force_window_seconds)
        self.scan_interval = settings.log_scan_interval_seconds
        
        # Dictionary lưu trữ thời gian các lần đăng nhập thất bại của từng IP
        # Key: IP Address (str), Value: deque of datetime objects
        self.failed_attempts: Dict[str, Deque[datetime]] = {}
        
        self.file_handle: Optional[object] = None
        self.last_position: int = 0
        
        self.local_ip = self._get_local_ip()
        
        logger.info(f"LogScanner initialized for {self.log_file_path}")
        logger.info(f"SSH Brute Force detection: {self.brute_force_threshold} attempts in {self.brute_force_window.total_seconds()}s")
        
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
        self._running = True
        try:
            self.file_handle = open(self.log_file_path, 'r', encoding='utf-8', errors='ignore')
            self.file_handle.seek(0, os.SEEK_END) # Bắt đầu đọc từ cuối file
            self.last_position = self.file_handle.tell()
            logger.info(f"LogScanner started, tailing {self.log_file_path} from position {self.last_position}")
        except Exception as e:
            logger.error(f"Failed to open log file {self.log_file_path}: {e}")
            self._running = False
            return

        while self._running:
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
                    time.sleep(self.scan_interval)
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
        self._running = False

    def _process_log_line(self, line: str):
        """Xử lý từng dòng log để phát hiện SSH Brute Force."""
        match = self.SSH_FAILED_LOGIN_REGEX.search(line)
        if match:
            username = match.group(1)
            ip_address = match.group(2)
            current_time = datetime.utcnow()
            
            if ip_address not in self.failed_attempts:
                self.failed_attempts[ip_address] = deque()
            
            self.failed_attempts[ip_address].append(current_time)
            
            # Xóa các lần thử cũ nằm ngoài cửa sổ thời gian
            while self.failed_attempts[ip_address] and \
                  self.failed_attempts[ip_address][0] < current_time - self.brute_force_window:
                self.failed_attempts[ip_address].popleft()
            
            # Kiểm tra nếu vượt ngưỡng
            if len(self.failed_attempts[ip_address]) >= self.brute_force_threshold:
                logger.warning(f"SSH Brute Force detected from {ip_address} (user: {username})")
                
                # Tạo alert và gửi đến AlertManager
                prediction = {'attack_type': 'SSH Brute Force', 'confidence': 1.0, 'severity': 'high'}
                flow_info = {
                    'src_ip': ip_address,
                    'dst_ip': self.local_ip,
                    'src_port': 22, # Giả định port 22 cho SSH
                    'dst_port': 22,
                    'protocol': 'tcp'
                }
                self.alert_manager.generate_alert(prediction, flow_info)
                
                # Xóa lịch sử để tránh tạo quá nhiều alert cho cùng một sự kiện
                self.failed_attempts[ip_address].clear()