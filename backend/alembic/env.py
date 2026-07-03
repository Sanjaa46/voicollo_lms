import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.models import Base  # noqa: F401 — triggers all model registrations
from app.models.service import Service  # noqa: F401
from app.models.application_log import ApplicationLog  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Alembic Config object — provides access to alembic.ini values.
config = context.config

# Configure Python logging from alembic.ini [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the SQLAlchemy metadata for autogenerate comparisons.
target_metadata = Base.metadata

database_url = os.environ.get("ROOT_DATABASE_URL")
# database_url = f"mysql+aiomysql://root:{os.environ.get('MARIADB_ROOT_PASSWORD')}@{os.environ.get('DB_HOST', 'localhost')}:3306/lms"
if not database_url:
    raise RuntimeError(
        "ROOT_DATABASE_URL environment variable is not set. "
        "Cannot run Alembic migrations without a database connection."
    )
config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Generates SQL scripts without connecting to the database.
    Useful for reviewing migration SQL before applying, or for DBAs
    who want to apply changes manually in controlled environments.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # LMS-DB-003 §1: version table name matches documented schema_migrations.
        version_table="schema_migrations",
        # Include schemas to ensure all tables are considered.
        include_schemas=False,
        # Compare server defaults so column default changes are detected.
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    Execute migrations against a live connection.
    Called by run_migrations_online() after acquiring an async connection.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table="schema_migrations",
        compare_server_default=True,
        # Render AS NULL for nullable columns explicitly — cleaner diffs.
        render_as_batch=False,
        # Include all column types in comparison for accurate autogenerate.
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Async entry point for online migrations.
    Creates a temporary async engine (separate from the app's engine pool),
    acquires a connection, runs migrations synchronously via run_sync(),
    then disposes the engine.

    LMS-SDD-002 §4: "async SQLAlchemy engine"
    LMS-DB-003 §5: "Run alembic upgrade head in the lms-migrate container
    on every deployment."
    """
    # Use NullPool for migration runs — migrations are one-shot operations
    # and should not maintain a connection pool.
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode (default for `alembic upgrade head`).
    Bridges the sync Alembic runner into the async SQLAlchemy world.
    """
    asyncio.run(run_async_migrations())


# -----------------------------------------------------------------------------
# Entry point — Alembic calls this module; mode is determined by context.
# -----------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
