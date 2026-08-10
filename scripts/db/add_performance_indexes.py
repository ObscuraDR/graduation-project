"""add performance indexes

Revision ID: add_perf_idx_001
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Index cho việc tìm kiếm và sắp xếp theo thời gian
    op.create_index('ix_alerts_created_at', 'alerts', ['created_at'])
    op.create_index('ix_flow_logs_timestamp', 'flow_logs', ['timestamp'])
    # Index cho việc truy vấn theo IP nguồn (thường dùng trong Firewall/Alerts)
    op.create_index('ix_alerts_src_ip', 'alerts', ['src_ip'])

def downgrade():
    op.drop_index('ix_alerts_created_at')
    op.drop_index('ix_flow_logs_timestamp')
    op.drop_index('ix_alerts_src_ip')