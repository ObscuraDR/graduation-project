"""
Attack Simulation Script
=========================
Sinh attack traffic giả để test IDS detection.

Usage:
    python backend/scripts/attack_simulation.py --type ddos --target 127.0.0.1
    python backend/scripts/attack_simulation.py --type portscan --target 127.0.0.1
    python backend/scripts/attack_simulation.py --type bruteforce --target 127.0.0.1

Lưu ý:
- Cần scapy đã cài (đã có trong requirements.txt)
- Trên Windows cần Npcap
- Trên Linux cần root privileges (sudo) để send raw packets
- Mặc định gửi đến 127.0.0.1 (loopback) — an toàn cho test local

CẢNH BÁO: KHÔNG dùng script này tấn công systems mà bạn không sở hữu.
"""

import argparse
import logging
import random
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def simulate_ddos(target: str, port: int = 80, count: int = 1000, rate: int = 500):
    """SYN flood DDoS simulation — gửi nhiều SYN packets liên tục."""
    try:
        from scapy.all import IP, TCP, send, RandShort
    except ImportError:
        logger.error("Scapy is required. Install with: pip install scapy")
        return

    logger.info(f"Starting DDoS simulation: {count} SYN packets to {target}:{port} at {rate} pps")
    interval = 1.0 / rate if rate > 0 else 0.001
    sent = 0

    try:
        for i in range(count):
            # Random source IP để mô phỏng botnet
            src_ip = f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
            packet = IP(src=src_ip, dst=target) / TCP(
                sport=RandShort(), dport=port, flags="S"
            )
            send(packet, verbose=0)
            sent += 1
            if sent % 100 == 0:
                logger.info(f"Sent {sent}/{count} packets")
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info(f"Interrupted. Sent {sent}/{count} packets")
    except PermissionError:
        logger.error("Permission denied. Run with sudo (Linux) or as Administrator (Windows)")
    except Exception as e:
        logger.error(f"Error: {e}")

    logger.info(f"DDoS simulation complete. Sent {sent} SYN packets")


def simulate_portscan(target: str, port_range: tuple = (1, 1000)):
    """Port scan simulation — quét nhiều ports trên target."""
    try:
        from scapy.all import IP, TCP, sr1, RandShort
    except ImportError:
        logger.error("Scapy is required")
        return

    start, end = port_range
    logger.info(f"Starting port scan: {target} ports {start}-{end}")
    scanned = 0

    try:
        for port in range(start, end + 1):
            packet = IP(dst=target) / TCP(sport=RandShort(), dport=port, flags="S")
            sr1(packet, timeout=0.1, verbose=0)
            scanned += 1
            if scanned % 50 == 0:
                logger.info(f"Scanned {scanned} ports...")
    except KeyboardInterrupt:
        logger.info(f"Interrupted. Scanned {scanned} ports")
    except PermissionError:
        logger.error("Permission denied. Run with sudo or Administrator")
    except Exception as e:
        logger.error(f"Error: {e}")

    logger.info(f"Port scan complete. Scanned {scanned} ports")


def simulate_bruteforce(target: str, port: int = 22, count: int = 100):
    """Brute force simulation — gửi nhiều TCP connections liên tục đến port (SSH/HTTP/FTP)."""
    try:
        from scapy.all import IP, TCP, send, RandShort
    except ImportError:
        logger.error("Scapy is required")
        return

    logger.info(f"Starting brute force simulation: {count} connections to {target}:{port}")
    sent = 0

    try:
        for i in range(count):
            # Mỗi connection: SYN → SYN-ACK (giả lập) → ACK + data
            sport = random.randint(40000, 60000)
            # SYN
            send(IP(dst=target) / TCP(sport=sport, dport=port, flags="S"), verbose=0)
            time.sleep(0.05)
            # PSH-ACK với "credentials"
            send(
                IP(dst=target) / TCP(sport=sport, dport=port, flags="PA")
                / f"USER admin\r\nPASS pwd{i}\r\n".encode(),
                verbose=0,
            )
            sent += 1
            if sent % 10 == 0:
                logger.info(f"Sent {sent}/{count} brute force attempts")
            time.sleep(0.2)
    except KeyboardInterrupt:
        logger.info(f"Interrupted. Sent {sent}/{count} attempts")
    except PermissionError:
        logger.error("Permission denied. Run with sudo or Administrator")
    except Exception as e:
        logger.error(f"Error: {e}")

    logger.info(f"Brute force simulation complete. Sent {sent} attempts")


def simulate_normal(target: str, port: int = 80, count: int = 50):
    """Normal traffic simulation — flow TCP bình thường (HTTP-like)."""
    try:
        from scapy.all import IP, TCP, send
    except ImportError:
        logger.error("Scapy is required")
        return

    logger.info(f"Generating {count} normal HTTP-like flows to {target}:{port}")
    sent = 0

    try:
        for i in range(count):
            sport = random.randint(40000, 60000)
            # 3-way handshake
            send(IP(dst=target) / TCP(sport=sport, dport=port, flags="S"), verbose=0)
            time.sleep(0.01)
            send(IP(dst=target) / TCP(sport=sport, dport=port, flags="A"), verbose=0)
            # GET request
            send(
                IP(dst=target) / TCP(sport=sport, dport=port, flags="PA")
                / b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n",
                verbose=0,
            )
            time.sleep(0.05)
            # FIN
            send(IP(dst=target) / TCP(sport=sport, dport=port, flags="FA"), verbose=0)
            sent += 1
            if sent % 10 == 0:
                logger.info(f"Sent {sent}/{count} normal flows")
            time.sleep(random.uniform(0.1, 0.5))
    except KeyboardInterrupt:
        logger.info(f"Interrupted. Sent {sent}/{count} flows")
    except Exception as e:
        logger.error(f"Error: {e}")

    logger.info(f"Normal traffic complete. Sent {sent} flows")


def main():
    parser = argparse.ArgumentParser(
        description="IDS Attack Simulation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python backend/scripts/attack_simulation.py --type ddos --target 127.0.0.1
    python backend/scripts/attack_simulation.py --type portscan --target 127.0.0.1
    python backend/scripts/attack_simulation.py --type bruteforce --target 127.0.0.1 --port 22
    python backend/scripts/attack_simulation.py --type normal --target 127.0.0.1
""",
    )
    parser.add_argument(
        "--type",
        choices=["ddos", "portscan", "bruteforce", "normal", "all"],
        required=True,
        help="Type of attack to simulate",
    )
    parser.add_argument(
        "--target", default="127.0.0.1", help="Target IP (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=80, help="Target port (default: 80)"
    )
    parser.add_argument(
        "--count", type=int, default=500, help="Number of packets/attempts (default: 500)"
    )
    parser.add_argument(
        "--rate", type=int, default=500, help="DDoS rate in packets per second (default: 500)"
    )
    args = parser.parse_args()

    if args.type == "ddos":
        simulate_ddos(args.target, args.port, args.count, args.rate)
    elif args.type == "portscan":
        simulate_portscan(args.target)
    elif args.type == "bruteforce":
        simulate_bruteforce(args.target, args.port, args.count)
    elif args.type == "normal":
        simulate_normal(args.target, args.port, args.count)
    elif args.type == "all":
        logger.info("Running all attack simulations sequentially...")
        simulate_normal(args.target, args.port, 30)
        time.sleep(2)
        simulate_portscan(args.target, (1, 200))
        time.sleep(2)
        simulate_bruteforce(args.target, 22, 30)
        time.sleep(2)
        simulate_ddos(args.target, args.port, 200, 100)


if __name__ == "__main__":
    main()
