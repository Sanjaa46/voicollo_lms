"""Shared async Redis client.

Redis is a performance and coordination layer (cache, rate limits, sessions,
locks). Read paths must survive Redis outages; callers catch `RedisError`.
"""

import logging
import time
from collections.abc import AsyncIterator

import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client: Redis | None = None


def init_redis() -> None:
    global _client
    _client = aioredis.from_url(
        get_settings().redis_dsn,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        health_check_interval=30,
    )
    logger.info("Redis client initialised.")


def set_redis_client(client: Redis) -> None:
    """Install a pre-built client (used by the test suite)."""
    global _client
    _client = client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_redis_client() -> Redis:
    if _client is None:
        raise RuntimeError("Redis not initialised. Call init_redis() at startup.")
    return _client


def redis_ready() -> bool:
    return _client is not None


async def get_redis() -> AsyncIterator[Redis]:
    """FastAPI dependency."""
    yield get_redis_client()


async def ping_redis() -> dict:
    if _client is None:
        return {"status": "error", "latency_ms": None, "detail": "client not initialised"}
    start = time.monotonic()
    try:
        await _client.ping()
        return {"status": "ok", "latency_ms": round((time.monotonic() - start) * 1000, 2)}
    except (RedisError, OSError) as exc:
        logger.error("Redis health check failed: %s", exc)
        return {
            "status": "error",
            "latency_ms": round((time.monotonic() - start) * 1000, 2),
            "detail": str(exc),
        }


async def scan_delete(client: Redis, pattern: str) -> int:
    """Delete keys matching `pattern` with SCAN (never KEYS). Best effort."""
    deleted = 0
    try:
        async for key in client.scan_iter(match=pattern, count=200):
            deleted += await client.delete(key)
    except RedisError as exc:
        logger.warning("SCAN delete failed for %s: %s", pattern, exc)
    return deleted
