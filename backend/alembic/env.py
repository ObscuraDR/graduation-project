"""
Alembic Environment Configuration
==================================
Cấu hình Alembic để dùng cùng engine và models của Z-Sentinel IDS.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool

from alembic import context

# Thêm project root vào sys.path để import backend modules
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_settings
from backend.database.connection import engine
from backend.database.models import Base

# Alembic Config object
config = context.config

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata cho autogenerate
target_metadata = Base.metadata


def get_url() -> str:
    """Lấy database URL từ settings (override sqlalchemy.url trong alembic.ini)."""
    s = get_settings()
    return (
        f"postgresql://{s.postgres_user}:{s.postgres_password}"
        f"@{s.postgres_host}:{s.postgres_port}/{s.postgres_db}"
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (không cần DB connection)."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # Detect column type changes
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (cần DB connection)."""
    # Dùng engine từ backend.database.connection (đã có pool config)
    connectable = engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
