"""audit logs, block history, geo allow/watch

Revision ID: 003_audit_geo
Revises: 002_security_tables
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = '003_audit_geo'
down_revision = '002_security_tables'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(50), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('client_ip', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_audit_logs_username', 'audit_logs', ['username'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])

    op.create_table(
        'block_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ip_address', sa.String(45), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('duration_hours', sa.Integer(), nullable=True),
        sa.Column('performed_by', sa.String(50), nullable=True),
        sa.Column('auto_blocked', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_block_history_ip_address', 'block_history', ['ip_address'])
    op.create_index('ix_block_history_created_at', 'block_history', ['created_at'])

    op.create_table(
        'geo_allow_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('country_code', sa.String(5), nullable=False, unique=True),
        sa.Column('country_name', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_geo_allow_rules_country_code', 'geo_allow_rules', ['country_code'])

    op.create_table(
        'geo_watch_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('country_code', sa.String(5), nullable=False, unique=True),
        sa.Column('country_name', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_geo_watch_rules_country_code', 'geo_watch_rules', ['country_code'])


def downgrade():
    op.drop_table('geo_watch_rules')
    op.drop_table('geo_allow_rules')
    op.drop_table('block_history')
    op.drop_table('audit_logs')
