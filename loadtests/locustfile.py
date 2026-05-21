"""
Locust Load Tests for IDS Backend API
Tests API endpoints under concurrent load
"""

from locust import HttpUser, task, between, events
from locust.runners import MasterRunner
import json
import random


class IDSUser(HttpUser):
    """Simulates a user interacting with the IDS API"""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Called when a user starts"""
        # Set API key header
        self.client.headers.update({
            "X-API-Key": "changeme-set-API_KEY-in-env",
            "Content-Type": "application/json"
        })
    
    @task(3)
    def get_health(self):
        """Test health check endpoint (lightweight)"""
        self.client.get("/health")
    
    @task(2)
    def get_alerts(self):
        """Test getting alerts"""
        self.client.get("/api/alerts?limit=10")
    
    @task(2)
    def get_whitelist(self):
        """Test getting whitelist"""
        self.client.get("/api/whitelist/list")
    
    @task(1)
    def get_stats(self):
        """Test getting statistics"""
        self.client.get("/api/stats/system")
    
    @task(1)
    def get_metrics(self):
        """Test Prometheus metrics endpoint"""
        self.client.get("/metrics")
    
    @task(1)
    def make_prediction(self):
        """Test making a prediction (heavier operation)"""
        # Sample features for prediction
        features = {
            "flow_duration": random.uniform(0, 100),
            "total_fwd_packets": random.randint(1, 1000),
            "total_bwd_packets": random.randint(1, 1000),
            "total_fwd_bytes": random.randint(100, 100000),
            "total_bwd_bytes": random.randint(100, 100000),
            "avg_packet_size": random.uniform(50, 1500),
            "packet_rate": random.uniform(0, 10000),
            "byte_rate": random.uniform(0, 10000000),
            "syn_count": random.randint(0, 100),
            "fin_count": random.randint(0, 10),
            "rst_count": random.randint(0, 10),
            "psh_count": random.randint(0, 100),
            "ack_count": random.randint(0, 1000),
            "unique_dst_ports": random.randint(1, 100),
            "inter_arrival_time_mean": random.uniform(0, 1),
            "fwd_packet_rate": random.uniform(0, 5000),
            "bwd_packet_rate": random.uniform(0, 5000),
            "fwd_byte_rate": random.uniform(0, 5000000),
            "bwd_byte_rate": random.uniform(0, 5000000),
            "packet_length_mean": random.uniform(50, 1500)
        }
        self.client.post("/api/predictions", json=features)


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Called when Locust starts"""
    print("Locust load tests initialized for IDS Backend")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the test starts"""
    print("Load test starting...")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the test stops"""
    print("Load test stopped")
    if not isinstance(environment.runner, MasterRunner):
        print(f"Total requests: {environment.runner.stats.total.num_requests}")
        print(f"Failures: {environment.runner.stats.total.num_failures}")
        print(f"Median response time: {environment.runner.stats.total.median_response_time}ms")
        print(f"95th percentile: {environment.runner.stats.total.get_response_time_percentile(0.95)}ms")
