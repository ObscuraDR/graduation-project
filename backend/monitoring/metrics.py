"""
Prometheus Metrics for IDS Backend
Exposes metrics for monitoring system health and performance
"""

from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from typing import Dict
import time

# Request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

# Alert metrics
alerts_total = Counter(
    'alerts_total',
    'Total alerts generated',
    ['attack_type', 'severity']
)

alerts_by_confidence = Histogram(
    'alerts_by_confidence',
    'Alert confidence distribution',
    ['attack_type']
)

# Pipeline metrics
packets_captured_total = Counter(
    'packets_captured_total',
    'Total packets captured'
)

flows_processed_total = Counter(
    'flows_processed_total',
    'Total flows processed'
)

predictions_total = Counter(
    'predictions_total',
    'Total predictions made',
    ['predicted_class']
)

pipeline_processing_duration_seconds = Histogram(
    'pipeline_processing_duration_seconds',
    'Pipeline processing duration in seconds'
)

# Database metrics
db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation', 'table']
)

db_connections_active = Gauge(
    'db_connections_active',
    'Active database connections',
    ['database']
)

# Model metrics
model_prediction_duration_seconds = Histogram(
    'model_prediction_duration_seconds',
    'Model prediction duration in seconds',
    ['model_name']
)

model_accuracy = Gauge(
    'model_accuracy',
    'Model accuracy',
    ['model_name', 'version']
)

# System metrics
system_info = Info(
    'system_info',
    'System information'
)

# WebSocket metrics
websocket_connections_active = Gauge(
    'websocket_connections_active',
    'Active WebSocket connections'
)

websocket_messages_total = Counter(
    'websocket_messages_total',
    'Total WebSocket messages sent',
    ['message_type']
)

# Email metrics
emails_sent_total = Counter(
    'emails_sent_total',
    'Total emails sent',
    ['status']
)

email_send_duration_seconds = Histogram(
    'email_send_duration_seconds',
    'Email send duration in seconds'
)


def init_metrics():
    """Initialize system info metrics"""
    system_info.info({
        'service': 'IDS Backend',
        'version': '1.0.0',
        'environment': 'production'
    })


def track_request(method: str, endpoint: str, status: int, duration: float):
    """Track HTTP request metrics"""
    http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
    http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)


def track_alert(attack_type: str, severity: str, confidence: float):
    """Track alert metrics"""
    alerts_total.labels(attack_type=attack_type, severity=severity).inc()
    alerts_by_confidence.labels(attack_type=attack_type).observe(confidence)


def track_prediction(predicted_class: str, duration: float, model_name: str = 'ensemble'):
    """Track prediction metrics"""
    predictions_total.labels(predicted_class=predicted_class).inc()
    model_prediction_duration_seconds.labels(model_name=model_name).observe(duration)


def track_db_query(operation: str, table: str, duration: float):
    """Track database query metrics"""
    db_query_duration_seconds.labels(operation=operation, table=table).observe(duration)


def metrics_endpoint():
    """FastAPI endpoint for Prometheus metrics"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
