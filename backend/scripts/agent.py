import psutil
import requests
import time
import platform
import logging
import os

# Cấu hình logging cho Agent
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- Cấu hình Agent ---
# Thay đổi SERVER_ID này cho mỗi máy chủ bạn muốn giám sát.
# SERVER_ID phải tương ứng với ID của máy chủ trong database của IDS Backend.
SERVER_ID = os.environ.get("AGENT_SERVER_ID", 1)  # Lấy từ biến môi trường hoặc mặc định là 1

# API Key của IDS Backend (Xác thực Agent)
API_KEY = os.environ.get("AGENT_API_KEY", "changeme-set-API_KEY-in-env")

# Địa chỉ API của IDS Backend
API_URL = os.environ.get("IDS_API_URL", "http://127.0.0.1:8000/api/servers")

# Khoảng thời gian gửi dữ liệu (giây)
INTERVAL = int(os.environ.get("AGENT_INTERVAL_SECONDS", 10))

def get_system_stats():
    """Thu thập các chỉ số hệ thống hiện tại."""
    cpu_usage = psutil.cpu_percent(interval=1) # CPU usage trong 1 giây
    ram_usage = psutil.virtual_memory().percent
    disk_usage = psutil.disk_usage('/').percent # Disk usage của phân vùng gốc
    
    # Trạng thái firewall (đơn giản, cần cải thiện cho thực tế)
    firewall_status = "active" if platform.system() == "Linux" else "enabled"

    return {
        "status": "online", # Luôn gửi online nếu agent đang chạy
        "cpu_usage": cpu_usage,
        "ram_usage": ram_usage,
        "disk_usage": disk_usage,
        "firewall_status": firewall_status
    }

def run_agent():
    logger.info(f"Z-Sentinel Agent started for Server ID: {SERVER_ID}. Reporting to {API_URL}.")
    while True:
        try:
            stats = get_system_stats()
            # Gửi kèm API Key trong Header X-API-Key
            response = requests.post(
                f"{API_URL}/{SERVER_ID}/status", 
                params=stats, 
                headers={"X-API-Key": API_KEY}
            )
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            logger.info(f"[{time.strftime('%H:%M:%S')}] Status updated successfully for Server ID {SERVER_ID}.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending status to IDS Server: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
        
        time.sleep(INTERVAL)

if __name__ == "__main__":
    # Cần cài đặt psutil và requests: pip install psutil requests
    run_agent()