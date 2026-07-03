# =============================================================================
# purpose:  Async SQLAlchemy 2.0 engine and session factory.
#           Provides:
#             - Primary async engine (lms_app user — SELECT/INSERT)
#             - Retention async engine (lms_retention user — DELETE only)
#             - get_db() FastAPI dependency yielding an AsyncSession
#             - get_retention_db() for use by the retention job only
#             - ping_database() for the /health endpoint
# implements: LMS-SDD-002 §3.1 (app/core/dependencies.py get_db)
#             LMS-SDD-002 §4 (SQLAlchemy 2.0+ async)
#             LMS-DB-003 §1 (MariaDB 10.6+, InnoDB, async engine)
#             LMS-DB-003 §4 (DB user privilege matrix — two separate users)
# =============================================================================

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# ORM Base
# All SQLAlchemy models inherit from this.
# -----------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# -----------------------------------------------------------------------------
# Module-level engine singletons
# Engines are created once at startup and reused across all requests.
# They are initialised by init_db() called from the FastAPI lifespan handler.
# -----------------------------------------------------------------------------
_primary_engine: AsyncEngine | None = None
_retention_engine: AsyncEngine | None = None

_primary_session_factory: async_sessionmaker[AsyncSession] | None = None
_retention_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db() -> None:
    """
    Initialise both database engines and session factories.
    Called once during application startup (app/main.py lifespan).

    Uses two separate connection strings:
      - DATABASE_URL       → lms_app user (SELECT, INSERT on all tables)
      - RETENTION_DATABASE_URL → lms_retention user (DELETE on log tables only)

    LMS-DB-003 §4: "Create a dedicated DB user lms_app with minimum required
    privileges. A separate lms_retention user runs the purge job."
    """
    global _primary_engine, _retention_engine
    global _primary_session_factory, _retention_session_factory

    settings = get_settings()

    # Common engine kwargs — pool tuning from config.
    engine_kwargs = {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout,
        "pool_pre_ping": True,   # Verify connections before use; handles dropped connections.
        "pool_recycle": 3600,    # Recycle connections older than 1 hour.
        "echo": False,           # Set True temporarily for SQL debugging; never in production.
    }

    _primary_engine = create_async_engine(
        settings.database_url,
        **engine_kwargs,
    )
    _retention_engine = create_async_engine(
        settings.retention_database_url,
        # Retention job runs once per night; small pool is sufficient.
        pool_size=2,
        max_overflow=2,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )

    _primary_session_factory = async_sessionmaker(
        bind=_primary_engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Prevent lazy-load errors after commit in async context.
        autoflush=False,
        autocommit=False,
    )
    _retention_session_factory = async_sessionmaker(
        bind=_retention_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    logger.info("Database engines initialised (primary + retention).")


async def close_db() -> None:
    """
    Dispose both engine connection pools.
    Called during application shutdown (app/main.py lifespan).
    """
    if _primary_engine:
        await _primary_engine.dispose()
        logger.info("Primary DB engine disposed.")
    if _retention_engine:
        await _retention_engine.dispose()
        logger.info("Retention DB engine disposed.")


# -----------------------------------------------------------------------------
# FastAPI dependency — primary session
# -----------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession for the primary lms_app user.

    Usage:
        @router.post("/logs/app")
        async def ingest_log(db: AsyncSession = Depends(get_db)):
            ...

    The session is automatically committed on success and rolled back on error.
    LMS-SDD-002 §3.1: "get_db FastAPI Depends() factory"
    """
    if _primary_session_factory is None:
        raise RuntimeError("Database not initialised. Call init_db() at startup.")

    async with _primary_session_factory() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error("Database session error, rolled back: %s", exc, exc_info=True)
            raise
        except Exception:
            await session.rollback()
            raise


# -----------------------------------------------------------------------------
# Context manager — retention session (used by retention job, not HTTP layer)
# -----------------------------------------------------------------------------
@asynccontextmanager
async def get_retention_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager yielding an AsyncSession for the lms_retention user.
    Used exclusively by app/jobs/retention.py.

    Example:
        async with get_retention_db() as session:
            await session.execute(delete_stmt)
            await session.commit()
    """
    if _retention_session_factory is None:
        raise RuntimeError("Database not initialised. Call init_db() at startup.")

    async with _retention_session_factory() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error(
                "Retention DB session error, rolled back: %s", exc, exc_info=True
            )
            raise
        except Exception:
            await session.rollback()
            raise


# -----------------------------------------------------------------------------
# Health check helper
# -----------------------------------------------------------------------------
async def ping_database() -> dict:
    """
    Executes a lightweight SELECT 1 against the primary engine to verify
    database connectivity. Returns a dict with status and latency.

    Used by GET /health endpoint (LMS-API-004 §2.7) and the health cache
    key lms:health:db_check (LMS-CACHE-005 §3, TTL 10s).

    Returns:
        {"status": "ok", "latency_ms": 3.2}
        {"status": "error", "latency_ms": None, "detail": "..."}
    """
    if _primary_engine is None:
        return {"status": "error", "latency_ms": None, "detail": "Engine not initialised"}

    start = time.monotonic()
    try:
        async with _primary_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {"status": "ok", "latency_ms": latency_ms}
    except OperationalError as exc:
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        logger.error("Database health check failed: %s", exc)
        return {"status": "error", "latency_ms": latency_ms, "detail": str(exc)}
