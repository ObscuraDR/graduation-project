"""add blacklist geoblock reports

Revision ID: 002_security_tables
Revises: 001_initial_schema
Create Date: 2025-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '002_security_tables'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'blacklist',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ip_address', sa.String(45), nullable=False, unique=True, index=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('country_code', sa.String(5), nullable=True),
        sa.Column('auto_blocked', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
    )
    op.create_table(
        'geo_block_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('country_code', sa.String(5), nullable=False, unique=True, index=True),
        sa.Column('country_name', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_table(
        'security_reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('report_id', sa.String(50), nullable=False, unique=True),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('total_alerts', sa.Integer(), default=0),
        sa.Column('critical_count', sa.Integer(), default=0),
        sa.Column('high_count', sa.Integer(), default=0),
        sa.Column('medium_count', sa.Integer(), default=0),
        sa.Column('low_count', sa.Integer(), default=0),
        sa.Column('top_attackers', sa.JSON(), nullable=True),
        sa.Column('top_attack_types', sa.JSON(), nullable=True),
        sa.Column('auto_blocked_count', sa.Integer(), default=0),
        sa.Column('geo_blocked_count', sa.Integer(), default=0),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('security_reports')
    op.drop_table('geo_block_rules')
    op.drop_table('blacklist')
