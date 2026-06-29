"""
Simulate Attack — Giả lập tấn công để demo IDS
================================================
Script này KHÔNG gửi gói tin thật qua mạng.
Nó inject trực tiếp features tấn công vào pipeline ML → tạo alert thật.

Cách dùng:
    python backend/scripts/simulate_attack.py
    python backend/scripts/simulate_attack.py --type DDoS --count 3
    python backend/scripts/simulate_attack.py --type PortScan
    python backend/scripts/simulate_attack.py --type BruteForce --src-ip 1.2.3.4

Các loại tấn công hỗ trợ:
    DDoS        — Tấn công từ chối dịch vụ phân tán
    PortScan    — Quét cổng
    BruteForce  — Dò mật khẩu
    Botnet      — Hoạt động botnet
    Abnormal    — Lưu lượng bất thường
    all         — Thực hiện tất cả loại trên

Yêu cầu:
    Backend đang chạy tại http://localhost:8000
"""

import argparse
import sys
import time
import random
import json
import httpx

# ── Cấu hình ──────────────────────────────────────────────────────────────────
BASE_URL   = "http://localhost:8000"
DEMO_START = f"{BASE_URL}/api/demo/start"
DEMO_STOP  = f"{BASE_URL}/api/demo/stop"
DEMO_STATUS= f"{BASE_URL}/api/demo/status"

# ── Feature profiles cho từng loại tấn công ──────────────────────────────────
# Các giá trị này match với patterns mà model đã học từ CICIDS2017
ATTACK_PROFILES = {
    "DDoS": {
        "desc": "DDoS — Tấn công từ chối dịch vụ (lưu lượng cực cao, SYN flood)",
        "features": {
            "flow_duration": 0.5,
            "total_fwd_packets": 1200,
            "total_bwd_packets": 5,
            "total_fwd_bytes": 72000,
            "total_bwd_bytes": 300,
            "avg_packet_size": 60.0,
            "packet_rate": 2400.0,
            "byte_rate": 144000.0,
            "syn_count": 1150,
            "fin_count": 0,
            "rst_count": 2,
            "psh_count": 0,
            "ack_count": 50,
            "unique_dst_ports": 1,
            "inter_arrival_time_mean": 0.0004,
            "fwd_packet_rate": 2390.0,
            "bwd_packet_rate": 10.0,
            "fwd_byte_rate": 143800.0,
            "bwd_byte_rate": 200.0,
            "packet_length_mean": 60.0,
        }
    },
    "PortScan": {
        "desc": "PortScan — Quét cổng (nhiều cổng đích khác nhau, SYN không có ACK)",
        "features": {
            "flow_duration": 30.0,
            "total_fwd_packets": 500,
            "total_bwd_packets": 0,
            "total_fwd_bytes": 30000,
            "total_bwd_bytes": 0,
            "avg_packet_size": 60.0,
            "packet_rate": 16.67,
            "byte_rate": 1000.0,
            "syn_count": 500,
            "fin_count": 0,
            "rst_count": 0,
            "psh_count": 0,
            "ack_count": 0,
            "unique_dst_ports": 500,
            "inter_arrival_time_mean": 0.06,
            "fwd_packet_rate": 16.67,
            "bwd_packet_rate": 0.0,
            "fwd_byte_rate": 1000.0,
            "bwd_byte_rate": 0.0,
            "packet_length_mean": 60.0,
        }
    },
    "BruteForce": {
        "desc": "BruteForce — Dò mật khẩu SSH/FTP (nhiều request nhỏ liên tiếp đến cùng port)",
        "features": {
            "flow_duration": 60.0,
            "total_fwd_packets": 300,
            "total_bwd_packets": 280,
            "total_fwd_bytes": 18000,
            "total_bwd_bytes": 16800,
            "avg_packet_size": 60.0,
            "packet_rate": 9.67,
            "byte_rate": 580.0,
            "syn_count": 300,
            "fin_count": 280,
            "rst_count": 20,
            "psh_count": 280,
            "ack_count": 580,
            "unique_dst_ports": 1,
            "inter_arrival_time_mean": 0.2,
            "fwd_packet_rate": 5.0,
            "bwd_packet_rate": 4.67,
            "fwd_byte_rate": 300.0,
            "bwd_byte_rate": 280.0,
            "packet_length_mean": 60.0,
        }
    },
    "Botnet": {
        "desc": "Botnet — Kết nối C&C định kỳ (beacon traffic pattern)",
        "features": {
            "flow_duration": 120.0,
            "total_fwd_packets": 20,
            "total_bwd_packets": 18,
            "total_fwd_bytes": 2400,
            "total_bwd_bytes": 2160,
            "avg_packet_size": 120.0,
            "packet_rate": 0.32,
            "byte_rate": 38.0,
            "syn_count": 20,
            "fin_count": 18,
            "rst_count": 2,
            "psh_count": 18,
            "ack_count": 38,
            "unique_dst_ports": 2,
            "inter_arrival_time_mean": 6.0,
            "fwd_packet_rate": 0.17,
            "bwd_packet_rate": 0.15,
            "fwd_byte_rate": 20.0,
            "bwd_byte_rate": 18.0,
            "packet_length_mean": 120.0,
        }
    },
    "Abnormal": {
        "desc": "Abnormal — Lưu lượng bất thường (pattern không bình thường)",
        "features": {
            "flow_duration": 10.0,
            "total_fwd_packets": 400,
            "total_bwd_packets": 2,
            "total_fwd_bytes": 800000,
            "total_bwd_bytes": 200,
            "avg_packet_size": 1750.0,
            "packet_rate": 40.2,
            "byte_rate": 80020.0,
            "syn_count": 1,
            "fin_count": 1,
            "rst_count": 0,
            "psh_count": 400,
            "ack_count": 402,
            "unique_dst_ports": 1,
            "inter_arrival_time_mean": 0.025,
            "fwd_packet_rate": 40.0,
            "bwd_packet_rate": 0.2,
            "fwd_byte_rate": 80000.0,
            "bwd_byte_rate": 20.0,
            "packet_length_mean": 1750.0,
        }
    },
}


def print_header():
    print("\n" + "="*60)
    print("  Z-SENTINEL IDS — Attack Simulator")
    print("  Giả lập tấn công để kiểm tra hệ thống phát hiện")
    print("="*60 + "\n")


def check_backend():
    """Kiểm tra backend có đang chạy không."""
    try:
        resp = httpx.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Backend: {data.get('status', 'unknown')} (v{data.get('version', '?')})")
            return True
    except Exception as e:
        print(f"❌ Backend không khả dụng tại {BASE_URL}")
        print(f"   Lỗi: {e}")
        print(f"\n   ➜ Hãy chạy backend trước:")
        print(f"   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload\n")
        return False


def enable_demo_mode():
    """Bật chế độ demo nếu chưa bật."""
    try:
        resp = httpx.post(
            f"{BASE_URL}/api/demo/config",
            json={"enabled": True},
            timeout=5
        )
        if resp.status_code == 200:
            print("✅ Demo mode: enabled")
            return True
    except Exception as e:
        print(f"❌ Không thể bật demo mode: {e}")
        return False


def simulate_via_demo_api(attack_types: list, count: int, delay: float, src_ip: str):
    """
    Phương pháp 1: Dùng /api/demo/start với filter theo class.
    Đây là cách an toàn và chắc chắn nhất.
    """
    classes_param = ",".join(attack_types)
    print(f"\n🚀 Đang khởi động demo replay...")
    print(f"   Loại tấn công : {classes_param}")
    print(f"   Số rounds     : {count}")
    print(f"   Delay         : {delay}s giữa mỗi flow\n")

    try:
        resp = httpx.post(
            DEMO_START,
            params={
                "classes": classes_param,
                "rounds": count,
                "delay_sec": delay,
                "unique_src": True,
                "shuffle": False,
            },
            timeout=10
        )

        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Demo started!")
            print(f"   Samples/round : {data.get('samples_per_round', '?')}")
            print(f"   Total samples : {data.get('samples_per_round', 0) * count}")
        elif resp.status_code == 403:
            print(f"❌ Demo mode chưa được bật")
            print(f"   ➜ Bật ENABLE_DEMO_REPLAY=true trong file .env")
            return False
        else:
            print(f"❌ Lỗi {resp.status_code}: {resp.text[:200]}")
            return False

    except Exception as e:
        print(f"❌ Không thể kết nối: {e}")
        return False

    # Theo dõi tiến trình
    print(f"\n📊 Đang theo dõi tiến trình (Ctrl+C để dừng)...\n")
    last_broadcast = 0
    start_time = time.time()

    try:
        while True:
            time.sleep(2)
            try:
                status_resp = httpx.get(DEMO_STATUS, timeout=5)
                if status_resp.status_code == 200:
                    s = status_resp.json()
                    elapsed = int(time.time() - start_time)
                    replayed   = s.get("replayed", 0)
                    detected   = s.get("detected_attacks", 0)
                    broadcast  = s.get("alerts_broadcast", 0)
                    suppressed = s.get("suppressed", 0)
                    running    = s.get("running", False)

                    # Hiện alert mới
                    if broadcast > last_broadcast:
                        new_alerts = broadcast - last_broadcast
                        print(f"  🔴 +{new_alerts} alert(s) broadcast! "
                              f"(total: {broadcast}) [{elapsed}s]")
                        last_broadcast = broadcast
                    else:
                        print(f"  ⏳ Đang chạy... replayed={replayed} "
                              f"detected={detected} broadcast={broadcast} "
                              f"suppressed={suppressed} [{elapsed}s]")

                    if not running:
                        print(f"\n{'='*50}")
                        print(f"✅ Demo hoàn thành!")
                        print(f"   Tổng flows   : {replayed}")
                        print(f"   Phát hiện    : {detected}")
                        print(f"   Alerts sent  : {broadcast}")
                        print(f"   Bị lọc       : {suppressed}")
                        print(f"\n➜ Kiểm tra Dashboard: http://localhost:3000/alerts")
                        break

            except Exception:
                pass

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Bị ngắt — dừng demo...")
        try:
            httpx.post(DEMO_STOP, timeout=5)
            print("✅ Demo đã dừng")
        except Exception:
            pass

    return True


def quick_inject(attack_type: str, src_ip: str):
    """
    Phương pháp 2: Inject trực tiếp 1 prediction vào AlertManager.
    Dùng cho demo nhanh 1 alert duy nhất.
    """
    profile = ATTACK_PROFILES.get(attack_type)
    if not profile:
        print(f"❌ Loại tấn công không hợp lệ: {attack_type}")
        return False

    print(f"\n⚡ Quick inject: {attack_type}")
    print(f"   {profile['desc']}")

    # Gọi /api/xai/explain để verify features hợp lệ + lấy prediction
    try:
        resp = httpx.post(
            f"{BASE_URL}/api/xai/explain",
            json={
                "model_name": "ensemble",
                "features": profile["features"]
            },
            timeout=15
        )

        if resp.status_code == 200:
            data = resp.json().get("data", {})
            predicted = data.get("predicted_label", "?")
            confidence = data.get("confidence", 0)
            print(f"   Model prediction: {predicted} ({confidence:.1%})")

            if predicted == "Normal":
                print(f"   ⚠️  Model phân loại là Normal — features chưa match")
                print(f"      ➜ Thử dùng --mode demo để dùng dataset thật")
            else:
                print(f"   ✅ Phát hiện đúng: {predicted}")
        else:
            print(f"   XAI endpoint: {resp.status_code}")

    except Exception as e:
        print(f"   ❌ Lỗi XAI: {e}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Z-Sentinel Attack Simulator — Giả lập tấn công để demo IDS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng:
  python simulate_attack.py                          # Demo tất cả loại, 1 round
  python simulate_attack.py --type DDoS              # Chỉ DDoS
  python simulate_attack.py --type PortScan --count 2  # PortScan, 2 rounds
  python simulate_attack.py --type BruteForce --delay 0.2  # Nhanh hơn
  python simulate_attack.py --type all               # Tất cả loại
  python simulate_attack.py --mode quick --type DDoS # Quick check model
        """
    )
    parser.add_argument(
        "--type", default="all",
        choices=["DDoS", "PortScan", "BruteForce", "Botnet", "Abnormal", "all"],
        help="Loại tấn công cần giả lập (default: all)"
    )
    parser.add_argument(
        "--count", type=int, default=1,
        help="Số rounds lặp lại (default: 1)"
    )
    parser.add_argument(
        "--delay", type=float, default=0.5,
        help="Thời gian chờ giữa các flows (giây, default: 0.5)"
    )
    parser.add_argument(
        "--src-ip", default="",
        help="IP nguồn tấn công (default: tự động tạo)"
    )
    parser.add_argument(
        "--mode", choices=["demo", "quick"], default="demo",
        help="demo: dùng dataset CICIDS2017 | quick: inject 1 alert ngay (default: demo)"
    )
    parser.add_argument(
        "--url", default="http://localhost:8000",
        help="URL của backend (default: http://localhost:8000)"
    )

    args = parser.parse_args()

    global BASE_URL, DEMO_START, DEMO_STOP, DEMO_STATUS
    BASE_URL    = args.url.rstrip("/")
    DEMO_START  = f"{BASE_URL}/api/demo/start"
    DEMO_STOP   = f"{BASE_URL}/api/demo/stop"
    DEMO_STATUS = f"{BASE_URL}/api/demo/status"

    print_header()

    # 1. Kiểm tra backend
    if not check_backend():
        sys.exit(1)

    # 2. Bật demo mode
    if args.mode == "demo":
        if not enable_demo_mode():
            sys.exit(1)

    # 3. Xác định loại tấn công
    if args.type == "all":
        attack_types = list(ATTACK_PROFILES.keys())
    else:
        attack_types = [args.type]

    print(f"\n📋 Loại tấn công sẽ giả lập: {', '.join(attack_types)}")
    for t in attack_types:
        if t in ATTACK_PROFILES:
            print(f"   • {ATTACK_PROFILES[t]['desc']}")

    print(f"\n💡 Tip: Mở http://localhost:3000 → tab Cảnh báo để xem real-time alerts\n")
    time.sleep(1)

    # 4. Thực hiện
    if args.mode == "quick":
        for attack_type in attack_types:
            quick_inject(attack_type, args.src_ip)
            if len(attack_types) > 1:
                time.sleep(0.5)
    else:
        simulate_via_demo_api(attack_types, args.count, args.delay, args.src_ip)


if __name__ == "__main__":
    main()
