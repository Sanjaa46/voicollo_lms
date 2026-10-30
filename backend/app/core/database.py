"""Async SQLAlchemy engines and sessions.

Two engines with different DB users (least privilege):
  * primary   — `lms_app`: SELECT/INSERT on logs, SELECT/INSERT/UPDATE on services.
  * retention — `lms_retention`: DELETE on log tables, used only by the purge job.

Every MySQL/MariaDB connection is pinned to UTC so `CURRENT_TIMESTAMP` defaults
and `UNIX_TIMESTAMP()` agree with the naive-UTC values the application writes.
"""

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


_primary_engine: AsyncEngine | None = None
_retention_engine: AsyncEngine | None = None
_primary_sessions: async_sessionmaker[AsyncSession] | None = None
_retention_sessions: async_sessionmaker[AsyncSession] | None = None


def engine_kwargs(url: str, *, pool_size: int, max_overflow: int, pool_timeout: int) -> dict:
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("mysql"):
        kwargs.update(
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=3600,
            connect_args={"init_command": "SET time_zone = '+00:00'"},
        )
    return kwargs


def init_db() -> None:
    global _primary_engine, _retention_engine, _primary_sessions, _retention_sessions
    settings = get_settings()

    _primary_engine = create_async_engine(
        settings.app_db_url,
        **engine_kwargs(
            settings.app_db_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
        ),
    )
    _retention_engine = create_async_engine(
        settings.retention_db_url,
        **engine_kwargs(
            settings.retention_db_url,
            pool_size=1,
            max_overflow=1,
            pool_timeout=settings.db_pool_timeout,
        ),
    )
    _primary_sessions = async_sessionmaker(_primary_engine, expire_on_commit=False, autoflush=False)
    _retention_sessions = async_sessionmaker(
        _retention_engine, expire_on_commit=False, autoflush=False
    )
    logger.info("Database engines initialised.")


def set_engines(primary: AsyncEngine, retention: AsyncEngine | None = None) -> None:
    """Install pre-built engines (used by the test suite)."""
    global _primary_engine, _retention_engine, _primary_sessions, _retention_sessions
    _primary_engine = primary
    _retention_engine = retention or primary
    _primary_sessions = async_sessionmaker(primary, expire_on_commit=False, autoflush=False)
    _retention_sessions = async_sessionmaker(
        _retention_engine, expire_on_commit=False, autoflush=False
    )


async def close_db() -> None:
    global _primary_engine, _retention_engine
    for engine in {_primary_engine, _retention_engine} - {None}:
        await engine.dispose()
    _primary_engine = _retention_engine = None


@asynccontextmanager
async def _scope(factory: async_sessionmaker[AsyncSession] | None) -> AsyncIterator[AsyncSession]:
    if factory is None:
        raise RuntimeError("Database not initialised. Call init_db() at startup.")
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


def session_scope() -> Any:
    """Transactional primary session for code outside the request cycle."""
    return _scope(_primary_sessions)


def retention_session_scope() -> Any:
    return _scope(_retention_sessions)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one transaction per request, committed on success."""
    async with _scope(_primary_sessions) as session:
        yield session


async def ping_database() -> dict:
    if _primary_engine is None:
        return {"status": "error", "latency_ms": None, "detail": "engine not initialised"}
    start = time.monotonic()
    try:
        async with _primary_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "latency_ms": round((time.monotonic() - start) * 1000, 2)}
    except (SQLAlchemyError, OSError) as exc:
        logger.error("Database health check failed: %s", exc)
        return {
            "status": "error",
            "latency_ms": round((time.monotonic() - start) * 1000, 2),
            "detail": str(exc),
        }
