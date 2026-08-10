"""
NetStat SYN-Flood Worker
========================
Phát hiện SYN Flood bằng cách đọc trạng thái TCP trực tiếp từ Windows
thông qua `netstat` — hoàn toàn độc lập với Npcap/Scapy.

Nguyên lý:
- Mỗi gói SYN từ attacker → Windows phản hồi SYN-ACK và tạo kết nối TCP
  ở trạng thái SYN_RECEIVED (half-open connection)
- Nếu attacker không gửi ACK (SYN Flood), kết nối ở lại trạng thái
  SYN_RECEIVED và tích lũy theo thời gian
- Worker đọc bảng TCP định kỳ, đếm SYN_RECEIVED theo IP nguồn
- Nếu 1 IP có quá nhiều half-open connections → Trigger alert + auto-block
"""

import asyncio
import logging
import subprocess
import re
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# Ngưỡng: nếu 1 IP có >= N kết nối SYN_RECEIVED → SYN flood
SYN_FLOOD_THRESHOLD = 20   # số half-open connections
MONITOR_INTERVAL_SEC = 2   # kiểm tra mỗi 2 giây
MONITOR_PORT = None        # None = giám sát tất cả port; hoặc set = 8000


def _get_syn_received_connections() -> dict[str, int]:
    """
    Chạy `netstat -n -p TCP` và đếm số kết nối SYN_RECEIVED theo IP nguồn.
    
    Returns:
        Dict {remote_ip: count_of_syn_received}
    """
    counts: dict[str, int] = defaultdict(int)
    try:
        result = subprocess.run(
            ["netstat", "-n", "-p", "TCP"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            # Dòng netstat có dạng:
            # TCP  192.168.1.150:8000  192.168.1.xxx:12345  SYN_RECEIVED
            if "SYN_RECEIVED" not in line:
                continue
            parts = line.split()
            # parts[0] = "TCP", parts[1] = local_addr, parts[2] = remote_addr, parts[3] = state
            if len(parts) < 4:
                continue

            local_addr = parts[1]   # e.g. "192.168.1.150:8000"
            remote_addr = parts[2]  # e.g. "192.168.1.102:54321"

            # Lọc theo port nếu MONITOR_PORT được set
            if MONITOR_PORT is not None:
                if not local_addr.endswith(f":{MONITOR_PORT}"):
                    continue

            # Trích IP nguồn (remote)
            m = re.match(r"^([\d.]+):\d+$", remote_addr)
            if m:
                remote_ip = m.group(1)
                counts[remote_ip] += 1

    except subprocess.TimeoutExpired:
        logger.warning("[SYN WORKER] netstat timeout")
    except FileNotFoundError:
        logger.warning("[SYN WORKER] netstat not found (non-Windows?)")
    except Exception as e:
        logger.warning("[SYN WORKER] Error running netstat: %s", e)

    return dict(counts)


async def netstat_syn_flood_task(
    interval_seconds: float = MONITOR_INTERVAL_SEC,
    threshold: int = SYN_FLOOD_THRESHOLD,
    alert_manager=None,
) -> None:
    """
    Async background task: giám sát SYN_RECEIVED mỗi `interval_seconds` giây.
    Tự lấy alert_manager từ singleton nếu không được truyền vào.
    """
    from backend.alert_engine.alert_manager import get_alert_manager

    if alert_manager is None:
        alert_manager = get_alert_manager()

    # Tracking: ip -> số lần phát hiện liên tiếp vượt ngưỡng (chống spam)
    triggered: dict[str, float] = {}  # ip -> last trigger time
    RETRIGGER_COOLDOWN = 30  # giây trước khi trigger lại cho cùng 1 IP

    logger.info(
        "[SYN WORKER] Started — checking every %.1fs, threshold=%d SYN_RECEIVED",
        interval_seconds,
        threshold,
    )

    while True:
        try:
            await asyncio.sleep(interval_seconds)

            counts = await asyncio.get_event_loop().run_in_executor(
                None, _get_syn_received_connections
            )

            for remote_ip, count in counts.items():
                if count < threshold:
                    continue

                # Kiểm tra cooldown chống spam
                import time
                now = time.monotonic()
                last_trigger = triggered.get(remote_ip, 0)
                if now - last_trigger < RETRIGGER_COOLDOWN:
                    logger.debug(
                        "[SYN WORKER] %s: %d SYN_RECEIVED (in cooldown, skip)",
                        remote_ip, count,
                    )
                    continue

                triggered[remote_ip] = now
                logger.warning(
                    "[SYN FLOOD via netstat] %s has %d SYN_RECEIVED connections — triggering alert+block",
                    remote_ip, count,
                )

                # Tạo synthetic prediction + flow info
                synthetic_prediction = {
                    'attack_type': 'syn_flood_inbound',
                    'confidence': 0.97,
                    'severity': 'high',
                    'all_probabilities': {'syn_flood_inbound': 0.97, 'Normal': 0.03},
                    'features': {'syn_received_count': count},
                    'model_name': 'netstat_syn_flood_detector',
                    'model_version': '1.0',
                }
                synthetic_flow = {
                    'src_ip': remote_ip,
                    'dst_ip': None,
                    'src_port': None,
                    'dst_port': MONITOR_PORT,
                    'protocol': 'tcp',
                    'flow_key': f"{remote_ip}:*-server:{MONITOR_PORT or 'any'}-tcp",
                }

                try:
                    alert = alert_manager.generate_alert(
                        synthetic_prediction, synthetic_flow
                    )
                    if alert:
                        logger.warning(
                            "[SYN WORKER] Alert generated for %s: %s",
                            remote_ip, alert.get('alert_id'),
                        )
                except Exception as ae:
                    logger.error("[SYN WORKER] Error generating alert: %s", ae)

        except asyncio.CancelledError:
            logger.info("[SYN WORKER] Stopped.")
            break
        except Exception as e:
            logger.error("[SYN WORKER] Unexpected error: %s", e)
            await asyncio.sleep(interval_seconds)
