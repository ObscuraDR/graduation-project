"""
Run Packet Sniffer
Standalone script to run the packet sniffer for testing
"""
import sys
import time
import argparse
import os
import asyncio
import platform
from pathlib import Path

# Add project root to path so `backend.*` imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.capture_engine.packet_sniffer import get_sniffer
from backend.flow_engine.flow_builder import get_flow_builder
from backend.feature_engine.feature_extractor import get_feature_extractor
from backend.detection_engine.model_loader import get_model_loader
from backend.detection_engine.predictor import get_predictor
from backend.alert_engine.alert_manager import get_alert_manager
from backend.scripts.firewall_manager import FirewallManager
from backend.scripts.log_scanner import LogScanner # Thêm import này
from backend.config import settings
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bộ đếm strike để thực hiện rule chặn sau 3 lần bất thường
strike_counter = {}
STRIKE_THRESHOLD = 3
STRIKE_WINDOW = 600  # Reset bộ đếm nếu IP không vi phạm lại trong 10 phút (600s)
TARGET_SERVER_ID = int(os.environ.get("AGENT_SERVER_ID", 1)) # Đồng nhất với agent.py

async def cleanup_strike_counter():
    """Định kỳ xóa các IP không còn hoạt động trong bộ đếm để tiết kiệm RAM"""
    while True:
        await asyncio.sleep(60) # Kiểm tra mỗi phút thay vì đợi 10 phút
        current_time = time.time()
        expired_ips = [
            ip for ip, info in list(strike_counter.items()) # Dùng list() để tránh lỗi RuntimeError khi xóa dictionary
            if current_time - info['last_seen'] > STRIKE_WINDOW
        ]
        for ip in expired_ips:
            del strike_counter[ip]
        if expired_ips:
            logger.info(f"Cleaned up {len(expired_ips)} expired IPs from strike counter")

def check_privileges():
    """Kiểm tra quyền quản trị tối cao."""
    if platform.system() == "Linux":
        if os.getuid() != 0:
            logger.warning("CẢNH BÁO: Cần quyền Root để bắt gói tin (Sniffing).")
            return False
    elif platform.system() == "Windows":
        import ctypes
        if ctypes.windll.shell32.IsUserAnAdmin() == 0:
            logger.warning("CẢNH BÁO: Cần quyền Administrator để bắt gói tin và quản lý Firewall.")
            return False
    return True

async def main_async(): # Đổi tên hàm main thành main_async và thêm async
    parser = argparse.ArgumentParser(description="Run IDS Packet Sniffer")
    parser.add_argument("--interface", type=str, default="Wi-Fi", help="Network interface")
    parser.add_argument("--filter", type=str, default="ip and not port 8000 and not port 3000", help="BPF filter")
    parser.add_argument("--model", type=str, default="ensemble", help="Model to load")
    parser.add_argument("--duration", type=int, default=60, help="Run duration in seconds")
    parser.add_argument("--server-id", type=int, default=TARGET_SERVER_ID, help="Target Server ID")
    args = parser.parse_args()
    
    # Initialize components
    logger.info("Initializing IDS components...")
    
    check_privileges()

    # Load model
    model_loader = get_model_loader()
    if not model_loader.load_from_directory(args.model):
        logger.error(f"Failed to load model: {args.model}")
        logger.info("Please train a model first using: python backend/ml/training.py")
        return
    
    # Initialize predictor
    predictor = get_predictor(model_loader=model_loader)
    
    # Initialize alert manager
    alert_manager = get_alert_manager()
    
    # Initialize LogScanner (FR05)
    log_scanner = None
    if settings.enable_log_scanner:
        log_scanner = LogScanner(alert_manager=alert_manager)
        log_scanner.start()
        logger.info("LogScanner started.")
    # Initialize firewall manager
    firewall = FirewallManager()
    
    # Initialize flow builder
    flow_builder = get_flow_builder()
    
    # Initialize sniffer
    sniffer = get_sniffer(interface=args.interface, filter_expr=args.filter)
    
    loop = asyncio.get_running_loop()
    
    # Chạy tác vụ dọn dẹp bộ nhớ nền
    asyncio.create_task(cleanup_strike_counter())

    # Packet callback
    def packet_callback(packet_info):
        """Process captured packet"""
        # Add to flow builder
        flow = flow_builder.add_packet(packet_info)
        
        # Bổ sung kiểm tra flow.is_demo để tránh phân tích chồng chéo dữ liệu giả lập
        is_demo_packet = packet_info.get('is_demo', False)
        
        # Tối ưu: Chỉ phân tích các flow thật (không phải demo) đã kết thúc hoặc đạt ngưỡng
        if flow and not is_demo_packet and (flow.is_finished or flow.packet_count == 10 or flow.packet_count % 50 == 0):
            try:
                # Predict
                prediction = predictor.predict_flow(flow)
                
                # Generate alert if attack
                if predictor.is_attack(prediction):
                    alert = alert_manager.generate_alert(
                        prediction,
                        {**flow.get_stats(), 'server_id': args.server_id} # Gắn ID máy chủ mục tiêu từ tham số
                    )
                    if alert:
                        logger.warning(f"ALERT: {alert['attack_type']} from {alert['src_ip']} (severity: {alert['severity']})")
                        
                        # Tích hợp chặn IP tự động (FR07)
                        # Mở rộng cho cả mức độ 'medium' để dễ dàng demo với các loại tấn công khác nhau
                        if alert.get('severity') in ['medium', 'high', 'critical']:
                            src_ip = alert['src_ip']
                            current_time = time.time()
                            
                            # Kiểm tra và reset strike nếu quá thời gian window
                            strike_info = strike_counter.get(src_ip, {'count': 0, 'last_seen': 0})
                            if current_time - strike_info['last_seen'] > STRIKE_WINDOW:
                                strike_info['count'] = 1
                            else:
                                strike_info['count'] += 1
                            
                            strike_info['last_seen'] = current_time
                            strike_counter[src_ip] = strike_info
                            
                            logger.info(f"IP {src_ip} vi phạm lần {strike_info['count']}/{STRIKE_THRESHOLD}")

                            if strike_info['count'] >= STRIKE_THRESHOLD:
                                logger.warning(f"IP {src_ip} vượt ngưỡng vi phạm. Tiến hành chặn!")
                                # Đẩy tác vụ chặn vào loop chính của AsyncIO
                                asyncio.run_coroutine_threadsafe(
                                    handle_firewall_block(firewall, alert_manager, src_ip, alert['attack_type'], alert['severity']),
                                    loop
                                )
                                del strike_counter[src_ip] # Xóa khỏi bộ đếm sau khi đã thực hiện chặn
                                
            except Exception as e:
                logger.error(f"Error processing flow: {e}")

    async def handle_firewall_block(fw: FirewallManager, am, ip: str, attack_type: str, severity: str):
        """Xử lý chặn tại OS và lưu vào Database Blacklist"""
        # Lưu vào Database thông qua AlertManager trước
        try:
            # Đảm bảo gọi hàm add_to_blacklist và truyền đủ thông tin
            am.add_to_blacklist(ip_address=ip, reason=f"AI Detected {attack_type} ({severity}) - 3-Strike Rule")
            logger.info(f"Database: IP {ip} added to blacklist table")
        except Exception as e:
            logger.error(f"Failed to add IP to DB blacklist: {e}")

        if await fw.block_ip(ip, f"Auto-blocked: {attack_type}"):
            logger.info(f"Firewall: Blocked {ip} for 1 hour")
            await asyncio.sleep(3600)
            await fw.unblock_ip(ip)
            logger.info(f"Firewall: Unblocked {ip}")
    
    # Set callback
    sniffer.callback = packet_callback
    
    # Start sniffer
    logger.info(f"Starting sniffer on interface {args.interface}")
    sniffer.start()
    
    try:
        # Run for specified duration
        logger.info(f"Running for {args.duration} seconds...")
        await asyncio.sleep(args.duration) # Sử dụng await asyncio.sleep
        
        # Print statistics
        logger.info("\n=== Statistics ===")
        logger.info(f"Sniffer: {sniffer.get_stats()}")
        logger.info(f"Flows: {flow_builder.get_stats()}")
        logger.info(f"Predictor: {predictor.get_stats()}")
        logger.info(f"Alert Manager: {alert_manager.get_stats()}")
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        # Stop sniffer
        sniffer.stop()
        logger.info("Sniffer stopped")
        if log_scanner:
            log_scanner.stop()
            log_scanner.join(timeout=2.0) # Chờ tối đa 2 giây để tránh treo máy


if __name__ == "__main__":
    asyncio.run(main_async()) # Chạy hàm main_async bằng asyncio.run
