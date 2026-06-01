"""
Locust Load Tests for Z-Sentinel IDS Backend API
==================================================
Tests các endpoints chính dưới tải đồng thời.

Usage:
    # Headless mode (CLI only, recommended cho thesis benchmark)
    locust -f backend/loadtests/locustfile.py --host=http://localhost:8000 \
           --headless -u 50 -r 5 -t 60s --csv=backend/reports/locust

    # Web UI mode
    locust -f backend/loadtests/locustfile.py --host=http://localhost:8000
    # Mở: http://localhost:8089

Output files (with --csv=backend/reports/locust):
    - locust_stats.csv
    - locust_failures.csv
    - locust_stats_history.csv
    - locust_exceptions.csv
"""

from locust import HttpUser, task, between, events
from locust.runners import MasterRunner
import random
import os

# API key cho các endpoints cần auth
API_KEY = os.environ.get("LOAD_TEST_API_KEY", "supersecretkey")

# Sample features cho XAI explain (20 features đúng contract)
SAMPLE_FEATURES_NORMAL = {
    "flow_duration": 1.5, "total_fwd_packets": 50, "total_bwd_packets": 30,
    "total_fwd_bytes": 5000, "total_bwd_bytes": 3000, "avg_packet_size": 100.0,
    "packet_rate": 50.0, "byte_rate": 5000.0, "syn_count": 1, "fin_count": 1,
    "rst_count": 0, "psh_count": 5, "ack_count": 70, "unique_dst_ports": 1,
    "inter_arrival_time_mean": 0.02, "fwd_packet_rate": 30.0,
    "bwd_packet_rate": 20.0, "fwd_byte_rate": 3000.0,
    "bwd_byte_rate": 2000.0, "packet_length_mean": 100.0,
}

SAMPLE_FEATURES_DDOS = {
    "flow_duration": 1.5, "total_fwd_packets": 500, "total_bwd_packets": 10,
    "total_fwd_bytes": 50000, "total_bwd_bytes": 1000, "avg_packet_size": 100.0,
    "packet_rate": 1200.0, "byte_rate": 98000.0, "syn_count": 450, "fin_count": 2,
    "rst_count": 5, "psh_count": 10, "ack_count": 50, "unique_dst_ports": 1,
    "inter_arrival_time_mean": 0.001, "fwd_packet_rate": 1100.0,
    "bwd_packet_rate": 100.0, "fwd_byte_rate": 90000.0,
    "bwd_byte_rate": 8000.0, "packet_length_mean": 100.0,
}


class ReadOnlyUser(HttpUser):
    """
    Simulates một dashboard user — chỉ làm read operations.
    Đây là use case phổ biến nhất trong production.
    """
    wait_time = between(0.5, 2.0)
    weight = 5  # 5 read users cho mỗi 1 admin user

    def on_start(self):
        self.client.headers.update({"Content-Type": "application/json"})

    @task(10)
    def get_health(self):
        """Lightweight health check — most frequent."""
        self.client.get("/health", name="GET /health")

    @task(5)
    def get_health_detailed(self):
        """Detailed health với DB connectivity check."""
        self.client.get("/health/detailed", name="GET /health/detailed")

    @task(8)
    def get_alerts(self):
        """List alerts — main dashboard load."""
        self.client.get("/api/alerts/?limit=20", name="GET /api/alerts/")

    @task(4)
    def get_traffic_stats(self):
        """Traffic stats cho Overview page."""
        self.client.get("/api/traffic/stats", name="GET /api/traffic/stats")

    @task(3)
    def get_active_flows(self):
        """Active flows cho Network page."""
        self.client.get("/api/traffic/flows?limit=50", name="GET /api/traffic/flows")

    @task(3)
    def get_top_talkers(self):
        """Top talkers cho Traffic page."""
        self.client.get("/api/traffic/top-talkers?limit=10", name="GET /api/traffic/top-talkers")

    @task(2)
    def get_alert_engine_stats(self):
        """Alert engine stats."""
        self.client.get("/api/stats/alert-engine", name="GET /api/stats/alert-engine")

    @task(2)
    def get_system_stats(self):
        """System stats."""
        self.client.get("/api/stats/system", name="GET /api/stats/system")

    @task(1)
    def get_training_report(self):
        """Training report cho AI Insights page."""
        self.client.get("/api/stats/training-report", name="GET /api/stats/training-report")

    @task(2)
    def get_metrics(self):
        """Prometheus metrics endpoint."""
        self.client.get("/metrics", name="GET /metrics")


class XAIUser(HttpUser):
    """
    Simulates user requesting SHAP explanations.
    Heavier than read ops — model inference + SHAP computation.
    """
    wait_time = between(2, 5)
    weight = 1

    def on_start(self):
        self.client.headers.update({"Content-Type": "application/json"})

    @task(3)
    def explain_normal(self):
        """SHAP explanation cho normal traffic."""
        self.client.post(
            "/api/xai/explain",
            json={"model_name": "ensemble", "features": SAMPLE_FEATURES_NORMAL},
            name="POST /api/xai/explain (normal)",
        )

    @task(2)
    def explain_attack(self):
        """SHAP explanation cho attack traffic."""
        self.client.post(
            "/api/xai/explain",
            json={"model_name": "ensemble", "features": SAMPLE_FEATURES_DDOS},
            name="POST /api/xai/explain (attack)",
        )


class WhitelistUser(HttpUser):
    """
    Simulates admin operations với API key auth.
    """
    wait_time = between(3, 8)
    weight = 1

    def on_start(self):
        self.client.headers.update({
            "X-API-Key": API_KEY,
            "Content-Type": "application/json",
        })

    @task(5)
    def list_whitelist(self):
        self.client.get("/api/whitelist/list", name="GET /api/whitelist/list")

    @task(1)
    def add_whitelist(self):
        ip = f"192.168.{random.randint(1,254)}.{random.randint(1,254)}"
        self.client.post(
            "/api/whitelist/add",
            json={"ip_address": ip, "reason": "load test"},
            name="POST /api/whitelist/add",
        )

    @task(2)
    def get_sniffer_status(self):
        self.client.get("/api/sniffer/status", name="GET /api/sniffer/status")


# ── Event hooks ─────────────────────────────────────────────────────────────

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    print("=" * 60)
    print("Z-Sentinel IDS — Locust Load Test")
    print("=" * 60)


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print(f"\n[START] Load test bắt đầu — target: {environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    if isinstance(environment.runner, MasterRunner):
        return

    stats = environment.runner.stats.total
    print("\n" + "=" * 60)
    print("[FINISHED] Load test kết quả")
    print("=" * 60)
    print(f"Total requests        : {stats.num_requests:,}")
    print(f"Failed requests       : {stats.num_failures:,}")
    if stats.num_requests > 0:
        fail_rate = (stats.num_failures / stats.num_requests) * 100
        print(f"Failure rate          : {fail_rate:.2f}%")
    print(f"Avg response time     : {stats.avg_response_time:.2f} ms")
    print(f"Median response time  : {stats.median_response_time} ms")
    print(f"95th percentile       : {stats.get_response_time_percentile(0.95)} ms")
    print(f"99th percentile       : {stats.get_response_time_percentile(0.99)} ms")
    print(f"Requests per second   : {stats.total_rps:.2f}")
    print("=" * 60)
