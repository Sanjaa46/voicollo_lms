# =============================================================================
# purpose:  Async Redis connection pool management.
#           Provides:
#             - init_redis() — creates the connection pool at startup
#             - close_redis() — graceful shutdown
#             - get_redis() — FastAPI dependency yielding a Redis client
#             - ping_redis() — health check helper for GET /health
# implements: LMS-CACHE-005 §2 (Redis Configuration)
#             LMS-CACHE-005 §3 (Key Schema — namespace lms:{category}:{id})
#             LMS-SDD-002 §3.1 (get_redis FastAPI Depends() factory)
#             LMS-SDD-002 §4 (redis-py 5.0+ async)
# =============================================================================

import logging
import time
from typing import AsyncGenerator

import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Module-level singleton
# Initialised by init_redis() at application startup.
# -----------------------------------------------------------------------------
_redis_pool: Redis | None = None


def init_redis() -> None:
    """
    Create the async Redis connection pool from REDIS_URL.
    Called once during application startup (app/main.py lifespan).

    Configuration per LMS-CACHE-005 §2:
      - Redis 7.0+
      - DB 0 (production), DB 1 (test isolation)
      - requirepass set via REDIS_URL
      - bind to container network only (enforced at infrastructure level)
      - maxmemory-policy: allkeys-lru (set in redis.conf, not here)
    """
    global _redis_pool
    settings = get_settings()

    _redis_pool = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,   # Always return str, never bytes — simpler handling.
        max_connections=20,      # Sufficient for single-node at 10k logs/day.
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )
    logger.info("Redis connection pool initialised.")


async def close_redis() -> None:
    """
    Close the Redis connection pool gracefully.
    Called during application shutdown (app/main.py lifespan).
    """
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None
        logger.info("Redis connection pool closed.")


def get_redis_client() -> Redis:
    """
    Returns the raw Redis client singleton.
    Used internally by cache_service and auth modules where a FastAPI
    dependency context is not available (e.g., startup, background jobs).

    Raises RuntimeError if init_redis() has not been called.
    """
    if _redis_pool is None:
        raise RuntimeError("Redis not initialised. Call init_redis() at startup.")
    return _redis_pool


async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    FastAPI dependency that yields the async Redis client.
    Does NOT acquire/release a connection per-request — the pool manages that.

    Usage:
        @router.get("/logs")
        async def query_logs(redis: Redis = Depends(get_redis)):
            ...

    LMS-CACHE-005 §10: "The application must not crash or return 500 on
    Redis failure for read operations." Callers should catch RedisError
    and fall through to the DB layer.
    """
    if _redis_pool is None:
        raise RuntimeError("Redis not initialised. Call init_redis() at startup.")
    yield _redis_pool


async def ping_redis() -> dict:
    """
    Sends a PING command to verify Redis connectivity.
    Returns a status dict with latency, used by GET /health (LMS-API-004 §2.7).

    Returns:
        {"status": "ok", "latency_ms": 0.8}
        {"status": "error", "latency_ms": None, "detail": "..."}
    """
    if _redis_pool is None:
        return {"status": "error", "latency_ms": None, "detail": "Pool not initialised"}

    start = time.monotonic()
    try:
        await _redis_pool.ping()
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {"status": "ok", "latency_ms": latency_ms}
    except RedisError as exc:
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        logger.error("Redis health check failed: %s", exc)
        return {"status": "error", "latency_ms": latency_ms, "detail": str(exc)}
