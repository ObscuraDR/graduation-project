"""initial schema — create all tables

Revision ID: 001_initial
Revises:
Create Date: 2026-05-28

Migration đầu tiên — tạo tất cả tables từ Base.metadata.
Sau lần này, dùng `alembic revision --autogenerate -m "..."` cho các thay đổi schema.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Revision identifiers, used by Alembic
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all initial tables."""
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), server_default="user"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    # traffic_flows
    op.create_table(
        "traffic_flows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("flow_key", sa.String(200), nullable=False),
        sa.Column("src_ip", sa.String(45), nullable=False),
        sa.Column("dst_ip", sa.String(45), nullable=False),
        sa.Column("src_port", sa.Integer(), nullable=True),
        sa.Column("dst_port", sa.Integer(), nullable=True),
        sa.Column("protocol", sa.String(10), nullable=False),
        sa.Column("packet_count", sa.Integer(), server_default="0"),
        sa.Column("byte_count", sa.Integer(), server_default="0"),
        sa.Column("forward_packets", sa.Integer(), server_default="0"),
        sa.Column("backward_packets", sa.Integer(), server_default="0"),
        sa.Column("forward_bytes", sa.Integer(), server_default="0"),
        sa.Column("backward_bytes", sa.Integer(), server_default="0"),
        sa.Column("syn_count", sa.Integer(), server_default="0"),
        sa.Column("fin_count", sa.Integer(), server_default="0"),
        sa.Column("rst_count", sa.Integer(), server_default="0"),
        sa.Column("psh_count", sa.Integer(), server_default="0"),
        sa.Column("ack_count", sa.Integer(), server_default="0"),
        sa.Column("flow_duration", sa.Float(), server_default="0.0"),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("inter_arrival_time_mean", sa.Float(), server_default="0.0"),
        sa.Column("unique_dst_ports", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flow_key"),
    )
    op.create_index("ix_traffic_flows_flow_key", "traffic_flows", ["flow_key"])
    op.create_index("ix_traffic_flows_src_ip", "traffic_flows", ["src_ip"])
    op.create_index("ix_traffic_flows_dst_ip", "traffic_flows", ["dst_ip"])
    op.create_index("ix_traffic_flows_created_at", "traffic_flows", ["created_at"])

    # flow_features
    op.create_table(
        "flow_features",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("flow_id", sa.Integer(), nullable=True),
        sa.Column("flow_duration", sa.Float(), server_default="0.0"),
        sa.Column("total_fwd_packets", sa.Integer(), server_default="0"),
        sa.Column("total_bwd_packets", sa.Integer(), server_default="0"),
        sa.Column("total_fwd_bytes", sa.Integer(), server_default="0"),
        sa.Column("total_bwd_bytes", sa.Integer(), server_default="0"),
        sa.Column("avg_packet_size", sa.Float(), server_default="0.0"),
        sa.Column("packet_rate", sa.Float(), server_default="0.0"),
        sa.Column("byte_rate", sa.Float(), server_default="0.0"),
        sa.Column("syn_count", sa.Integer(), server_default="0"),
        sa.Column("fin_count", sa.Integer(), server_default="0"),
        sa.Column("rst_count", sa.Integer(), server_default="0"),
        sa.Column("psh_count", sa.Integer(), server_default="0"),
        sa.Column("ack_count", sa.Integer(), server_default="0"),
        sa.Column("unique_dst_ports", sa.Integer(), server_default="0"),
        sa.Column("inter_arrival_time_mean", sa.Float(), server_default="0.0"),
        sa.Column("fwd_packet_rate", sa.Float(), server_default="0.0"),
        sa.Column("bwd_packet_rate", sa.Float(), server_default="0.0"),
        sa.Column("fwd_byte_rate", sa.Float(), server_default="0.0"),
        sa.Column("bwd_byte_rate", sa.Float(), server_default="0.0"),
        sa.Column("packet_length_mean", sa.Float(), server_default="0.0"),
        sa.Column("feature_vector", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["flow_id"], ["traffic_flows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_flow_features_created_at", "flow_features", ["created_at"])

    # attack_alerts
    op.create_table(
        "attack_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_id", sa.String(50), nullable=False),
        sa.Column("flow_id", sa.Integer(), nullable=True),
        sa.Column("source_ip", sa.String(45), nullable=False),
        sa.Column("dest_ip", sa.String(45), nullable=False),
        sa.Column("source_port", sa.Integer(), nullable=True),
        sa.Column("dest_port", sa.Integer(), nullable=True),
        sa.Column("protocol", sa.String(10), nullable=True),
        sa.Column("attack_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("confidence", sa.DECIMAL(5, 2), nullable=False),
        sa.Column("correlated", sa.Boolean(), server_default="false"),
        sa.Column("original_severity", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("is_resolved", sa.Boolean(), server_default="false"),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("model_version", sa.String(20), nullable=True),
        sa.Column("all_probabilities", postgresql.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["flow_id"], ["traffic_flows.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_id"),
    )
    op.create_index("ix_attack_alerts_alert_id", "attack_alerts", ["alert_id"])
    op.create_index("ix_attack_alerts_source_ip", "attack_alerts", ["source_ip"])
    op.create_index("ix_attack_alerts_dest_ip", "attack_alerts", ["dest_ip"])
    op.create_index("ix_attack_alerts_attack_type", "attack_alerts", ["attack_type"])
    op.create_index("ix_attack_alerts_timestamp", "attack_alerts", ["timestamp"])

    # attack_history
    op.create_table(
        "attack_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_ip", sa.String(45), nullable=False),
        sa.Column("attack_type", sa.String(50), nullable=False),
        sa.Column("first_seen", sa.DateTime(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("attack_count", sa.Integer(), server_default="1"),
        sa.Column("critical_count", sa.Integer(), server_default="0"),
        sa.Column("high_count", sa.Integer(), server_default="0"),
        sa.Column("medium_count", sa.Integer(), server_default="0"),
        sa.Column("low_count", sa.Integer(), server_default="0"),
        sa.Column("correlation_window_start", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attack_history_source_ip", "attack_history", ["source_ip"])
    op.create_index("ix_attack_history_attack_type", "attack_history", ["attack_type"])

    # models
    op.create_table(
        "models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("algorithm", sa.String(50), nullable=False),
        sa.Column("accuracy", sa.DECIMAL(5, 2), nullable=True),
        sa.Column("precision", sa.DECIMAL(5, 2), nullable=True),
        sa.Column("recall", sa.DECIMAL(5, 2), nullable=True),
        sa.Column("f1_score", sa.DECIMAL(5, 2), nullable=True),
        sa.Column("file_path", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # whitelist
    op.create_table(
        "whitelist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("protocol", sa.String(10), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("added_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_whitelist_ip_address", "whitelist", ["ip_address"])

    # metrics
    op.create_table(
        "metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("model_id", sa.Integer(), nullable=True),
        sa.Column("metric_type", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_metrics_timestamp", "metrics", ["timestamp"])


def downgrade() -> None:
    """Drop all tables (reverse order vì có FK)."""
    op.drop_table("metrics")
    op.drop_table("whitelist")
    op.drop_table("models")
    op.drop_table("attack_history")
    op.drop_table("attack_alerts")
    op.drop_table("flow_features")
    op.drop_table("traffic_flows")
    op.drop_table("users")
