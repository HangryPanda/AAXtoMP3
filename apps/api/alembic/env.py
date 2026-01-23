"""Alembic environment configuration with async support."""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

# Import all models to ensure they are registered with SQLModel.metadata
from db.models import (  # noqa: F401
    Book,
    Job,
    SettingsModel,
    Person,
    BookAuthor,
    BookNarrator,
    Series,
    BookSeries,
    Chapter,
    BookAsset,
    BookTechnical,
    PlaybackProgress,
    BookScanState,
    LocalItem,
)

# Alembic Config object
config = context.config

# Configure logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate support
target_metadata = SQLModel.metadata

# Get database URL from environment or config
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    config.get_main_option("sqlalchemy.url"),
)

# Convert asyncpg URL to postgresql URL for sync operations if needed
if DATABASE_URL and DATABASE_URL.startswith("postgresql+asyncpg://"):
    SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
else:
    SYNC_DATABASE_URL = DATABASE_URL


def get_url() -> str:
    """Get the database URL for migrations."""
    url = DATABASE_URL
    if not url:
        raise ValueError("DATABASE_URL environment variable is not set")
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
