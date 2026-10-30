"""Operational counters stored in Redis (best effort, never raises)."""

import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.redis import get_redis_client, redis_ready
from app.core.time import isoformat_utc, utcnow

logger = logging.getLogger(__name__)

INGESTION_TOTAL = "lms:metrics:ingestion_total"
QUERY_TOTAL = "lms:metrics:query_total"
CACHE_HITS = "lms:metrics:cache_hits"
CACHE_MISSES = "lms:metrics:cache_misses"
ERROR_HASH = "lms:metrics:errors"
SINCE = "lms:metrics:since"


async def incr(redis: Redis, key: str, amount: int = 1) -> None:
    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.incrby(key, amount)
            pipe.set(SINCE, isoformat_utc(utcnow()), nx=True)
            await pipe.execute()
    except RedisError as exc:
        logger.debug("metrics incr failed: %s", exc)


async def record_error(error_code: str) -> None:
    if not redis_ready():
        return
    try:
        await get_redis_client().hincrby(ERROR_HASH, error_code, 1)
    except RedisError as exc:
        logger.debug("error counter failed: %s", exc)


async def read_counters(redis: Redis) -> dict:
    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.get(INGESTION_TOTAL)
            pipe.get(QUERY_TOTAL)
            pipe.get(CACHE_HITS)
            pipe.get(CACHE_MISSES)
            pipe.hgetall(ERROR_HASH)
            pipe.get(SINCE)
            ingest, query, hits, misses, errors, since = await pipe.execute()
    except RedisError as exc:
        logger.warning("Could not read metrics: %s", exc)
        ingest = query = hits = misses = since = None
        errors = {}
    hits_i, misses_i = int(hits or 0), int(misses or 0)
    lookups = hits_i + misses_i
    return {
        "ingestion_total": int(ingest or 0),
        "query_total": int(query or 0),
        "cache_hits": hits_i,
        "cache_misses": misses_i,
        "cache_hit_ratio": round(hits_i / lookups, 4) if lookups else 0.0,
        "error_total": {code: int(count) for code, count in (errors or {}).items()},
        "since": since,
    }
