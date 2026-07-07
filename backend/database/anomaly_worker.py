"""
Anomaly Detection Worker — học baseline và phát hiện bất thường.

Nguyên lý:
  - Mỗi máy chủ có "hành vi bình thường" (baseline): CPU 20-30%, RAM 40-50%
  - Khi số liệu vượt quá mean + 2*stddev → bất thường
  - Học dần dần từ lịch sử metrics thay vì dùng ngưỡng cứng

Thuật toán: Rolling Z-Score với sliding window 1 giờ
  z = (x - mean) / std
  |z| > 2.5 → anomaly
"""

import asyncio
import logging
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Z-score threshold cho anomaly
ZSCORE_THRESHOLD = 2.5
# Số điểm dữ liệu tối thiểu để tính baseline
MIN_BASELINE_POINTS = 10
# Cửa sổ baseline (giờ)
BASELINE_WINDOW_HOURS = 1

# In-memory rolling baseline per server
# Format: {server_id: {"cpu": [values], "ram": [values], "disk": [values]}}
_baselines: Dict[int, Dict[str, List[float]]] = {}


def _zscore(value: float, data: List[float]) -> float:
    """Tính Z-score của value so với data list."""
    if len(data) < 2:
        return 0.0
    try:
        mean = statistics.mean(data)
        std = statistics.stdev(data)
        if std == 0:
            return 0.0
        return abs(value - mean) / std
    except Exception:
        return 0.0


def update_baseline(server_id: int, cpu: float, ram: float, disk: float) -> None:
    """Cập nhật baseline với giá trị metrics mới."""
    if server_id not in _baselines:
        _baselines[server_id] = {"cpu": [], "ram": [], "disk": [], "timestamps": []}

    baseline = _baselines[server_id]
    now = datetime.now(timezone.utc)

    # Thêm giá trị mới
    baseline["cpu"].append(cpu)
    baseline["ram"].append(ram)
    baseline["disk"].append(disk)
    baseline["timestamps"].append(now)

    # Giới hạn rolling window — chỉ giữ 1 giờ gần nhất
    cutoff = now - timedelta(hours=BASELINE_WINDOW_HOURS)
    valid_indices = [
        i for i, ts in enumerate(baseline["timestamps"])
        if ts >= cutoff
    ]

    if len(valid_indices) < len(baseline["timestamps"]):
        baseline["cpu"]        = [baseline["cpu"][i] for i in valid_indices]
        baseline["ram"]        = [baseline["ram"][i] for i in valid_indices]
        baseline["disk"]       = [baseline["disk"][i] for i in valid_indices]
        baseline["timestamps"] = [baseline["timestamps"][i] for i in valid_indices]


def detect_anomaly(server_id: int, cpu: float, ram: float, disk: float) -> Optional[Dict]:
    """
    Phát hiện bất thường dựa trên Z-score so với baseline.

    Returns:
        Dict với thông tin anomaly nếu phát hiện, None nếu bình thường.
    """
    baseline = _baselines.get(server_id, {})

    cpu_data  = baseline.get("cpu", [])
    ram_data  = baseline.get("ram", [])
    disk_data = baseline.get("disk", [])

    # Chưa đủ dữ liệu để tính baseline
    if len(cpu_data) < MIN_BASELINE_POINTS:
        return None

    anomalies = []

    cpu_z  = _zscore(cpu,  cpu_data)
    ram_z  = _zscore(ram,  ram_data)
    disk_z = _zscore(disk, disk_data)

    if cpu_z > ZSCORE_THRESHOLD:
        mean_cpu = statistics.mean(cpu_data)
        anomalies.append({
            "metric": "cpu",
            "current": cpu,
            "baseline_mean": round(mean_cpu, 1),
            "zscore": round(cpu_z, 2),
            "message": f"CPU anomaly: {cpu:.1f}% (baseline: {mean_cpu:.1f}%, z={cpu_z:.2f})",
        })

    if ram_z > ZSCORE_THRESHOLD:
        mean_ram = statistics.mean(ram_data)
        anomalies.append({
            "metric": "ram",
            "current": ram,
            "baseline_mean": round(mean_ram, 1),
            "zscore": round(ram_z, 2),
            "message": f"RAM anomaly: {ram:.1f}% (baseline: {mean_ram:.1f}%, z={ram_z:.2f})",
        })

    if disk_z > ZSCORE_THRESHOLD:
        mean_disk = statistics.mean(disk_data)
        anomalies.append({
            "metric": "disk",
            "current": disk,
            "baseline_mean": round(mean_disk, 1),
            "zscore": round(disk_z, 2),
            "message": f"Disk anomaly: {disk:.1f}% (baseline: {mean_disk:.1f}%, z={disk_z:.2f})",
        })

    if not anomalies:
        return None

    # Xác định severity theo mức Z-score cao nhất
    max_z = max(a["zscore"] for a in anomalies)
    severity = "critical" if max_z > 4.0 else ("high" if max_z > 3.0 else "medium")

    return {
        "server_id": server_id,
        "anomalies": anomalies,
        "severity": severity,
        "max_zscore": round(max_z, 2),
        "baseline_points": len(cpu_data),
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }


def get_baseline_summary(server_id: int) -> Optional[Dict]:
    """Lấy tóm tắt baseline của một server để debug/monitor."""
    baseline = _baselines.get(server_id)
    if not baseline or len(baseline.get("cpu", [])) < 2:
        return None
    return {
        "server_id": server_id,
        "data_points": len(baseline["cpu"]),
        "window_hours": BASELINE_WINDOW_HOURS,
        "cpu": {
            "mean": round(statistics.mean(baseline["cpu"]), 1),
            "stdev": round(statistics.stdev(baseline["cpu"]), 1) if len(baseline["cpu"]) > 1 else 0,
            "min": round(min(baseline["cpu"]), 1),
            "max": round(max(baseline["cpu"]), 1),
        },
        "ram": {
            "mean": round(statistics.mean(baseline["ram"]), 1),
            "stdev": round(statistics.stdev(baseline["ram"]), 1) if len(baseline["ram"]) > 1 else 0,
        },
        "disk": {
            "mean": round(statistics.mean(baseline["disk"]), 1),
            "stdev": round(statistics.stdev(baseline["disk"]), 1) if len(baseline["disk"]) > 1 else 0,
        },
    }


async def anomaly_detection_task(interval_seconds: int = 30):
    """
    Background task: đọc metrics mới nhất của tất cả servers từ DB,
    cập nhật baseline và phát hiện bất thường.
    """
    logger.info("Anomaly Detection Worker started (interval=%ds, zscore_threshold=%.1f)",
                interval_seconds, ZSCORE_THRESHOLD)

    while True:
        try:
            from backend.database.connection import SessionLocal
            from backend.database.repository import ServerRepository, ServerMetricHistoryRepository
            from backend.database.security_log_store import store_security_log

            db = SessionLocal()
            try:
                servers = ServerRepository.get_all_servers(db)
                for server in servers:
                    if server.status != "online":
                        continue
                    if server.cpu_usage is None or server.ram_usage is None:
                        continue

                    cpu  = float(server.cpu_usage)
                    ram  = float(server.ram_usage)
                    disk = float(server.disk_usage or 0)

                    # Phát hiện trước khi update baseline
                    anomaly = detect_anomaly(server.id, cpu, ram, disk)

                    # Cập nhật baseline
                    update_baseline(server.id, cpu, ram, disk)

                    # Xử lý anomaly nếu có
                    if anomaly:
                        logger.warning(
                            "Anomaly detected on server %s (id=%d): severity=%s, max_z=%.2f",
                            server.name, server.id,
                            anomaly["severity"], anomaly["max_zscore"]
                        )
                        # Lưu vào security_logs
                        for a in anomaly["anomalies"]:
                            store_security_log(
                                server=server.name,
                                event_type=f"{a['metric']}_anomaly",
                                message=a["message"],
                                log_source="anomaly_detector",
                                extra={
                                    "server_id": server.id,
                                    "zscore": a["zscore"],
                                    "severity": anomaly["severity"],
                                    "baseline_mean": a["baseline_mean"],
                                },
                            )

                        # Trigger AlertManager nếu anomaly nghiêm trọng
                        if anomaly["severity"] in ("high", "critical"):
                            try:
                                from backend.alert_engine.alert_manager import get_alert_manager
                                alert_mgr = get_alert_manager()
                                prediction = {
                                    "attack_type": "Abnormal",
                                    "confidence": min(0.95, 0.5 + anomaly["max_zscore"] / 10),
                                    "severity": anomaly["severity"],
                                }
                                flow_info = {
                                    "src_ip": server.ip_address,
                                    "dst_ip": "system",
                                    "server_name": server.name,
                                    "anomaly_details": anomaly,
                                }
                                alert_mgr.generate_alert(prediction, flow_info)
                            except Exception as e:
                                logger.debug("AlertManager anomaly trigger failed: %s", e)

            finally:
                db.close()

        except Exception as e:
            logger.error("Anomaly detection task error: %s", e)

        await asyncio.sleep(interval_seconds)
