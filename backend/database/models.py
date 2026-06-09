"""
Database Models
SQLAlchemy ORM models for PostgreSQL database
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, DECIMAL, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class User(Base):
    """User model for authentication"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TrafficFlow(Base):
    """Traffic flow model for storing network flow data"""
    __tablename__ = "traffic_flows"
    
    id = Column(Integer, primary_key=True, index=True)
    flow_key = Column(String(200), unique=True, nullable=False, index=True)
    src_ip = Column(String(45), nullable=False, index=True)
    dst_ip = Column(String(45), nullable=False, index=True)
    src_port = Column(Integer, nullable=True)
    dst_port = Column(Integer, nullable=True)
    protocol = Column(String(10), nullable=False)
    
    # Flow statistics
    packet_count = Column(Integer, default=0)
    byte_count = Column(Integer, default=0)
    forward_packets = Column(Integer, default=0)
    backward_packets = Column(Integer, default=0)
    forward_bytes = Column(Integer, default=0)
    backward_bytes = Column(Integer, default=0)
    
    # TCP flags
    syn_count = Column(Integer, default=0)
    fin_count = Column(Integer, default=0)
    rst_count = Column(Integer, default=0)
    psh_count = Column(Integer, default=0)
    ack_count = Column(Integer, default=0)
    
    # Timing
    flow_duration = Column(Float, default=0.0)
    start_time = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    inter_arrival_time_mean = Column(Float, default=0.0)
    
    # Unique ports
    unique_dst_ports = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class FlowFeature(Base):
    """Flow feature model for storing extracted ML features"""
    __tablename__ = "flow_features"
    
    id = Column(Integer, primary_key=True, index=True)
    flow_id = Column(Integer, ForeignKey("traffic_flows.id"), nullable=True)
    
    # All 21 features
    flow_duration = Column(Float, default=0.0)
    total_fwd_packets = Column(Integer, default=0)
    total_bwd_packets = Column(Integer, default=0)
    total_fwd_bytes = Column(Integer, default=0)
    total_bwd_bytes = Column(Integer, default=0)
    avg_packet_size = Column(Float, default=0.0)
    packet_rate = Column(Float, default=0.0)
    byte_rate = Column(Float, default=0.0)
    syn_count = Column(Integer, default=0)
    fin_count = Column(Integer, default=0)
    rst_count = Column(Integer, default=0)
    psh_count = Column(Integer, default=0)
    ack_count = Column(Integer, default=0)
    unique_dst_ports = Column(Integer, default=0)
    inter_arrival_time_mean = Column(Float, default=0.0)
    fwd_packet_rate = Column(Float, default=0.0)
    bwd_packet_rate = Column(Float, default=0.0)
    fwd_byte_rate = Column(Float, default=0.0)
    bwd_byte_rate = Column(Float, default=0.0)
    packet_length_mean = Column(Float, default=0.0)
    
    # Store raw feature vector as JSON for reference
    feature_vector = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AttackAlert(Base):
    """Attack alert model for storing detected attacks"""
    __tablename__ = "attack_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String(50), unique=True, nullable=False, index=True)
    flow_id = Column(Integer, ForeignKey("traffic_flows.id"), nullable=True)
    
    source_ip = Column(String(45), nullable=False, index=True)
    dest_ip = Column(String(45), nullable=False, index=True)
    source_port = Column(Integer, nullable=True)
    dest_port = Column(Integer, nullable=True)
    protocol = Column(String(10), nullable=True)
    
    attack_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False)  # critical, high, medium, low
    confidence = Column(DECIMAL(5, 2), nullable=False)
    
    # Correlation info
    correlated = Column(Boolean, default=False)
    original_severity = Column(String(20), nullable=True)
    
    # Status
    status = Column(String(20), default="active")  # active, resolved, ignored
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Model information
    model_name = Column(String(100), nullable=True)
    model_version = Column(String(20), nullable=True)
    
    # Store prediction probabilities
    all_probabilities = Column(JSON, nullable=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


# Cấu trúc đề xuất cho backend/database/models.py
class Blacklist(Base):
    __tablename__ = "blacklist"
    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String, unique=True, index=True, nullable=False)
    reason = Column(String)
    blocked_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # Null nghĩa là chặn vĩnh viễn
    is_active = Column(Boolean, default=True)
    auto_blocked = Column(Boolean, default=True)


class Server(Base):
    """Model cho các máy chủ được quản lý bởi IDS."""
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    ip_address = Column(String(45), unique=True, nullable=False, index=True)
    os = Column(String(50), nullable=True)  # e.g., "Linux", "Windows"
    description = Column(Text, nullable=True)
    status = Column(String(20), default="offline")  # online, offline, warning
    cpu_usage = Column(Float, nullable=True)  # %
    ram_usage = Column(Float, nullable=True)  # %
    disk_usage = Column(Float, nullable=True) # %
    firewall_status = Column(String(50), nullable=True) # e.g., "active", "inactive"
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class ServerMetricHistory(Base):
    """Model lưu trữ lịch sử các chỉ số của máy chủ."""
    __tablename__ = "server_metric_history"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    cpu_usage = Column(Float, nullable=False)
    ram_usage = Column(Float, nullable=False)
    disk_usage = Column(Float, nullable=False)
    firewall_status = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False)

class SystemSetting(Base):
    """Bảng lưu trữ cấu hình hệ thống động (Notifications, GeoIP, v.v.)"""
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AttackHistory(Base):
    """Attack history model for tracking attack patterns over time"""
    __tablename__ = "attack_history"
    
    id = Column(Integer, primary_key=True, index=True)
    source_ip = Column(String(45), nullable=False, index=True)
    attack_type = Column(String(50), nullable=False, index=True)
    
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    attack_count = Column(Integer, default=1)
    
    # Severity distribution
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    
    # Correlation window
    correlation_window_start = Column(DateTime, nullable=True)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Model(Base):
    """Model metadata for tracking trained ML models"""
    __tablename__ = "models"
    
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False)
    algorithm = Column(String(50), nullable=False)
    accuracy = Column(DECIMAL(5, 2), nullable=True)
    precision = Column(DECIMAL(5, 2), nullable=True)
    recall = Column(DECIMAL(5, 2), nullable=True)
    f1_score = Column(DECIMAL(5, 2), nullable=True)
    file_path = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Whitelist(Base):
    """Whitelist for safe IPs/ports"""
    __tablename__ = "whitelist"
    
    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), nullable=False, index=True)
    port = Column(Integer, nullable=True)
    protocol = Column(String(10), nullable=True)
    reason = Column(Text, nullable=True)
    added_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Blacklist(Base):
    """Blacklist for blocked IPs"""
    __tablename__ = "blacklist"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), nullable=False, unique=True, index=True)
    reason = Column(Text, nullable=True)
    country_code = Column(String(5), nullable=True)   # e.g. "CN", "RU"
    auto_blocked = Column(Boolean, default=False)      # True = blocked by AlertManager
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)       # None = permanent


class GeoBlockRule(Base):
    """Geo-blocking rules by country code"""
    __tablename__ = "geo_block_rules"

    id = Column(Integer, primary_key=True, index=True)
    country_code = Column(String(5), nullable=False, unique=True, index=True)
    country_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SecurityReport(Base):
    """Periodic security reports"""
    __tablename__ = "security_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String(50), unique=True, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    total_alerts = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    top_attackers = Column(JSON, nullable=True)        # [{ip, count, attack_type}]
    top_attack_types = Column(JSON, nullable=True)     # [{type, count}]
    auto_blocked_count = Column(Integer, default=0)
    geo_blocked_count = Column(Integer, default=0)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Metric(Base):
    """Model performance metrics over time"""
    __tablename__ = "metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    model_id = Column(Integer, nullable=True)
    metric_type = Column(String(50), nullable=True)  # accuracy, precision, recall, f1, fpr
