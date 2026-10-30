"""Redis-backed caching and rate limiting.

Query cache invalidation uses a *generation* counter: every cache key embeds the
current generation and every write bumps it. Old entries simply age out by TTL,
so a write costs one INCR instead of a SCAN over all cached queries.
"""

import contextlib
import hashlib
import json
import logging
import math
import time
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.services import metrics

logger = logging.getLogger(__name__)

QUERY_GENERATION_KEY = "lms:query:gen"
QUERY_KEY_PREFIX = "lms:query:"
HEALTH_DB_KEY = "lms:health:db"
RATE_LIMIT_KEY = "lms:ratelimit:{service}:{window}"


async def bump_query_generation(redis: Redis) -> None:
    try:
        await redis.incr(QUERY_GENERATION_KEY)
    except RedisError as exc:
        logger.warning("Could not invalidate query cache: %s", exc)


async def _generation(redis: Redis) -> str:
    return await redis.get(QUERY_GENERATION_KEY) or "0"


async def cache_key(redis: Redis, namespace: str, params: dict[str, Any]) -> str | None:
    """Deterministic key for `params` within the current generation. None if Redis is down."""
    try:
        generation = await _generation(redis)
    except RedisError:
        return None
    raw = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(f"{generation}|{raw}".encode()).hexdigest()
    return f"{QUERY_KEY_PREFIX}{namespace}:{digest}"


async def get_cached(redis: Redis, key: str | None) -> Any | None:
    if key is None:
        return None
    try:
        raw = await redis.get(key)
    except RedisError as exc:
        logger.warning("Cache read failed: %s", exc)
        return None
    await metrics.incr(redis, metrics.CACHE_HITS if raw is not None else metrics.CACHE_MISSES)
    return json.loads(raw) if raw is not None else None


async def set_cached(redis: Redis, key: str | None, value: Any, ttl: int) -> None:
    if key is None:
        return
    try:
        await redis.set(key, json.dumps(value, default=str), ex=ttl)
    except RedisError as exc:
        logger.warning("Cache write failed: %s", exc)


async def get_cached_health(redis: Redis) -> dict | None:
    try:
        raw = await redis.get(HEALTH_DB_KEY)
        return json.loads(raw) if raw else None
    except RedisError:
        return None


async def set_cached_health(redis: Redis, value: dict) -> None:
    with contextlib.suppress(RedisError):
        await redis.set(
            HEALTH_DB_KEY, json.dumps(value), ex=get_settings().health_cache_ttl_seconds
        )


async def consume_rate_limit(redis: Redis, counts: dict[str, int]) -> tuple[str, int] | None:
    """Add `counts` (entries per service) to the current one-minute window.

    Returns (service, retry_after_seconds) for the first service over the limit,
    or None when every service is within its budget. Fails open if Redis is down.
    """
    limit = get_settings().rate_limit_max
    now = time.time()
    window = math.floor(now / 60)
    try:
        async with redis.pipeline(transaction=True) as pipe:
            for service, amount in counts.items():
                key = RATE_LIMIT_KEY.format(service=service, window=window)
                pipe.incrby(key, amount)
                pipe.expire(key, 120)
            results = await pipe.execute()
    except RedisError as exc:
        logger.warning("Rate limit check skipped (Redis unavailable): %s", exc)
        return None
    for (service, _), used in zip(counts.items(), results[::2], strict=True):
        if used > limit:
            retry_after = max(1, 60 - int(now % 60))
            logger.warning("Rate limit exceeded for %s: %d/%d", service, used, limit)
            return service, retry_after
    return None
