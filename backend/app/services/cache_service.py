# =============================================================================
# purpose:  Redis caching operations for the LMS.
#           Implements all key patterns, TTLs, invalidation strategies,
#           and response header values defined in LMS-CACHE-005.
#
#           Key responsibilities:
#             - Query result caching (lms:query:{sha256}, TTL 60s)
#             - Query cache invalidation (SCAN-based, never KEYS)
#             - Health check result caching (lms:health:db_check, TTL 10s)
#             - Rate limit counter management (lms:ratelimit:{svc}:{window})
#             - Response header population (X-Cache, X-Cache-Key, X-Cache-TTL)
#             - Cache hit/miss counter tracking for GET /metrics
#
# implements: LMS-CACHE-005 §3  (Key Schema)
#             LMS-CACHE-005 §4  (Cache Key Generation — SHA-256)
#             LMS-CACHE-005 §5  (Cache Invalidation Strategy)
#             LMS-CACHE-005 §7  (Rate Limiting Implementation)
#             LMS-CACHE-005 §8  (Response Headers)
#             LMS-CACHE-005 §9  (Monitoring — hit/miss counters)
#             LMS-CACHE-005 §10 (Testing — Redis failure resilience)
#             LMS-SDD-002 §3.3  (Ingestion Flow — invalidate on write)
#             LMS-SDD-002 §3.4  (Query Flow — cache get/set)
#             LMS-BRD-001 FR-10 (60-second repeat query caching)
# =============================================================================

import hashlib
import json
import logging
import math
import time
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis key prefixes — LMS-CACHE-005 §3
# All keys use the namespace: lms:{category}:{identifier}
# ---------------------------------------------------------------------------
KEY_PREFIX_QUERY = "lms:query:"
KEY_PREFIX_RATELIMIT = "lms:ratelimit:"
KEY_PREFIX_HEALTH = "lms:health:"

# Full key constants for single-instance keys.
HEALTH_DB_CHECK_KEY = "lms:health:db_check"

# Internal counters for metrics (stored in Redis as simple integers).
# These are NOT in the CACHE-005 spec but are required by LMS-API-004 §2.8
# (GET /metrics: cache_hit_ratio gauge). They use the lms: namespace.
METRICS_CACHE_HITS_KEY = "lms:metrics:cache_hits"
METRICS_CACHE_MISSES_KEY = "lms:metrics:cache_misses"
METRICS_INGESTION_TOTAL_KEY = "lms:metrics:ingestion_total"
METRICS_QUERY_TOTAL_KEY = "lms:metrics:query_total"
METRICS_ERROR_TOTAL_KEY = "lms:metrics:error_total"


# ===========================================================================
# Section 4: Cache Key Generation
# LMS-CACHE-005 §4 — deterministic SHA-256 key from query parameters
# ===========================================================================

def build_query_cache_key(params: dict[str, Any]) -> str:
    """
    Generates a deterministic SHA-256 cache key for a query result.

    Algorithm (LMS-CACHE-005 §4):
      1. Collect all query parameters as a dict (including page, page_size, sort).
      2. Sort dict keys alphabetically.
      3. Serialize to compact JSON (no whitespace).
      4. Compute SHA-256 hex digest.
      5. Return lms:query:{hex_digest}

    The SHA-256 approach:
      - Is collision-resistant for all practical parameter combinations.
      - Avoids key length issues with long parameter lists.
      - Is safe from injection via parameter value manipulation.
      - Produces identical output regardless of insertion order.

    Args:
        params: Dict of query parameters. May contain None values
                (they are included as JSON null to keep keys deterministic).

    Returns:
        Redis key string: "lms:query:{64-char-hex}"

    Example (LMS-CACHE-005 §4):
        build_query_cache_key({
            "log_type": "app", "level": "ERROR",
            "source_service": "xyp-backend", "page": 1, "page_size": 50
        })
        → "lms:query:a3f9...c72b"
    """
    # Step 1 & 2: Sort keys alphabetically for determinism.
    sorted_params = dict(sorted(params.items()))

    # Step 3: Compact JSON — no whitespace, sorted keys are already applied.
    serialised = json.dumps(sorted_params, separators=(",", ":"), sort_keys=False)

    # Step 4: SHA-256 hex digest.
    digest = hashlib.sha256(serialised.encode("utf-8")).hexdigest()

    # Step 5: Full cache key.
    return f"{KEY_PREFIX_QUERY}{digest}"


def get_cache_key_prefix(digest: str) -> str:
    """
    Returns the first 16 characters of the SHA-256 digest.
    Used for X-Cache-Key response header (LMS-CACHE-005 §8).
    """
    return digest[:16]


# ===========================================================================
# Section 4 + 3.4: Query cache get / set
# ===========================================================================

async def get_cached_query(
    redis: Redis,
    cache_key: str,
) -> tuple[Any | None, dict]:
    """
    Attempts to retrieve a cached query result from Redis.

    Args:
        redis:     Async Redis client.
        cache_key: Full cache key (from build_query_cache_key).

    Returns:
        Tuple of (result, headers) where:
          - result is the deserialized cached value, or None on miss/error.
          - headers is a dict of X-Cache-* headers to attach to the response.
            LMS-CACHE-005 §8: X-Cache, X-Cache-Key, X-Cache-TTL.

    Note:
        LMS-CACHE-005 §10: Must not crash or return 500 on Redis failure.
        On RedisError, returns (None, miss_headers) — caller falls through to DB.
    """
    # Extract the short key for the header (first 16 chars of digest).
    short_key = cache_key.removeprefix(KEY_PREFIX_QUERY)[:16]

    miss_headers = {
        "X-Cache": "MISS",
        "X-Cache-Key": short_key,
        "X-Cache-TTL": "0",
    }

    try:
        # Fetch value and remaining TTL in a pipeline (single round-trip).
        async with redis.pipeline(transaction=False) as pipe:
            pipe.get(cache_key)
            pipe.ttl(cache_key)
            raw_value, ttl = await pipe.execute()

        if raw_value is None:
            # Cache miss — increment miss counter for metrics.
            await _increment_counter(redis, METRICS_CACHE_MISSES_KEY)
            return None, miss_headers

        # Cache hit.
        result = json.loads(raw_value)
        remaining_ttl = max(ttl, 0)  # TTL returns -2 if key absent, -1 if no expiry.

        hit_headers = {
            "X-Cache": "HIT",
            "X-Cache-Key": short_key,
            "X-Cache-TTL": str(remaining_ttl),
        }

        # Increment hit counter for metrics.
        await _increment_counter(redis, METRICS_CACHE_HITS_KEY)

        logger.debug("Cache HIT for key %s (TTL=%ds)", cache_key, remaining_ttl)
        return result, hit_headers

    except RedisError as exc:
        # LMS-CACHE-005 §10: Redis failure must not cause 500 on reads.
        logger.warning(
            "Redis error on cache GET for key %s — falling through to DB: %s",
            cache_key,
            exc,
        )
        return None, miss_headers


async def set_cached_query(
    redis: Redis,
    cache_key: str,
    value: Any,
) -> None:
    """
    Stores a query result in Redis with the configured TTL.

    Args:
        redis:     Async Redis client.
        cache_key: Full cache key (from build_query_cache_key).
        value:     JSON-serialisable query result.

    Note:
        Failures are logged but non-fatal — the response is already being
        sent to the client. LMS-CACHE-005 §10.
    """
    settings = get_settings()
    try:
        serialised = json.dumps(value, default=str)  # default=str handles datetime.
        await redis.set(
            cache_key,
            serialised,
            ex=settings.query_cache_ttl_seconds,
        )
        logger.debug(
            "Cache SET for key %s (TTL=%ds)",
            cache_key,
            settings.query_cache_ttl_seconds,
        )
    except RedisError as exc:
        logger.warning("Redis error on cache SET for key %s: %s", cache_key, exc)
    except (TypeError, ValueError) as exc:
        logger.error(
            "Failed to serialise query result for cache key %s: %s", cache_key, exc
        )


# ===========================================================================
# Section 5: Cache Invalidation
# LMS-CACHE-005 §5 — four invalidation triggers
# ===========================================================================

async def invalidate_app_log_query_cache(
    redis: Redis,
    source_service: str,
) -> None:
    """
    Active cache invalidation triggered when a new application log is ingested.

    LMS-CACHE-005 §5:
      "New log ingested (app) → Active delete — All lms:query:* keys for
      that source_service."

    Implementation note from LMS-CACHE-005 §5:
      "Use SCAN pattern: lms:query:* and filter in-app, OR tag keys with
      service prefix."

    We use the SCAN approach — SHA-256 keys cannot be filtered by service name
    after hashing. We scan ALL lms:query:* keys and delete them all when any
    app log is ingested. This is correct because any cached query result
    may include logs from this service (e.g. log_type=both, no service filter).

    LMS-CACHE-005 WARNING: "Never use the Redis KEYS pattern command in
    production — it blocks the server. Use SCAN with COUNT 100."

    [CONFLICT-02 resolved]: Audit log ingestion does NOT call this function —
    audit query cache uses TTL-expiry only (LMS-CACHE-005 §5).

    Args:
        redis:          Async Redis client.
        source_service: The service that ingested the log (for logging context).
    """
    deleted_count = await _scan_and_delete(redis, f"{KEY_PREFIX_QUERY}*")
    logger.debug(
        "App log ingestion by '%s': invalidated %d query cache key(s).",
        source_service,
        deleted_count,
    )


async def invalidate_all_query_cache(redis: Redis) -> None:
    """
    Flushes ALL lms:query:* keys from Redis.

    Called by the retention job after purging expired log entries.
    LMS-CACHE-005 §5: "Retention job completes → Active flush — Flush all
    lms:query:* keys. Stale counts are worse post-purge."

    Also safe to call from admin operations that modify log data.
    """
    deleted_count = await _scan_and_delete(redis, f"{KEY_PREFIX_QUERY}*")
    logger.info(
        "Full query cache flush completed: %d key(s) deleted.", deleted_count
    )


async def _scan_and_delete(redis: Redis, pattern: str) -> int:
    """
    Iterates through all keys matching `pattern` using SCAN and deletes them.

    LMS-CACHE-005 WARNING: Uses SCAN with COUNT 100, never KEYS.
    SCAN is non-blocking; it returns a cursor that must be followed until
    it returns 0 (indicating the full keyspace has been scanned).

    Args:
        redis:   Async Redis client.
        pattern: Glob-style key pattern, e.g. "lms:query:*"

    Returns:
        Total number of keys deleted.
    """
    deleted_count = 0
    cursor = 0

    try:
        while True:
            # SCAN returns (next_cursor, [keys]).
            # COUNT 100 is a hint — Redis may return more or fewer per batch.
            cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)

            if keys:
                # DELETE all matched keys in a single call (pipeline efficiency).
                await redis.delete(*keys)
                deleted_count += len(keys)

            # SCAN returns cursor=0 when the full keyspace has been iterated.
            if cursor == 0:
                break

    except RedisError as exc:
        logger.warning(
            "Redis SCAN/DELETE error during cache invalidation (pattern=%s): %s",
            pattern,
            exc,
        )

    return deleted_count


# ===========================================================================
# Health check cache
# LMS-CACHE-005 §3: lms:health:db_check  TTL: 10s
# ===========================================================================

async def get_cached_health(redis: Redis) -> dict | None:
    """
    Returns the cached DB health check result, or None on miss/error.
    TTL: 10 seconds (LMS-CACHE-005 §3).
    Reduces DB polling on the /health endpoint.
    """
    try:
        raw = await redis.get(HEALTH_DB_CHECK_KEY)
        if raw:
            return json.loads(raw)
    except RedisError as exc:
        logger.debug("Redis error on health cache GET: %s", exc)
    return None


async def set_cached_health(redis: Redis, health_data: dict) -> None:
    """
    Caches the DB health check result for 10 seconds.
    LMS-CACHE-005 §3: lms:health:db_check  TTL: 10s
    """
    settings = get_settings()
    try:
        await redis.set(
            HEALTH_DB_CHECK_KEY,
            json.dumps(health_data),
            ex=settings.health_cache_ttl_seconds,
        )
    except RedisError as exc:
        logger.debug("Redis error on health cache SET: %s", exc)


# ===========================================================================
# Section 7: Rate Limiting
# LMS-CACHE-005 §7 — INCR + EXPIRE pattern per service per 60s window
# ===========================================================================

async def check_and_increment_rate_limit(
    redis: Redis,
    source_service: str,
) -> tuple[bool, int]:
    """
    Checks and increments the ingestion rate limit counter for a service.

    Uses the Redis INCR + EXPIRE pattern (LMS-CACHE-005 §7):
      Key: lms:ratelimit:{source_service}:{unix_minute}
      - INCR the key. If result == 1, set EXPIRE 60 (first request in window).
      - If result > RATE_LIMIT_MAX → reject with 429.

    Rate limits are per source_service, not per IP.
    LMS-CACHE-005 §7: "Services are authenticated, so IP-based limiting
    adds no value here."

    Args:
        redis:          Async Redis client.
        source_service: Authenticated service identifier.

    Returns:
        Tuple of (allowed: bool, retry_after_seconds: int).
          - allowed=True  → request is within rate limit.
          - allowed=False → rate limit exceeded; retry_after_seconds tells
                            the client when to retry.

    Note:
        On RedisError, rate limiting is bypassed (fail-open) to avoid
        blocking ingestion when Redis is temporarily unavailable.
        The error is logged as WARNING for observability.
    """
    settings = get_settings()

    # Window key: floor(current time / 60) gives the current 60s bucket.
    unix_minute = math.floor(time.time() / 60)
    rate_key = f"{KEY_PREFIX_RATELIMIT}{source_service}:{unix_minute}"

    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(rate_key)
            # EXPIRE is only applied on first INCR (result==1) but we set it
            # every time as a safety net (idempotent if already set).
            pipe.expire(rate_key, 60)
            results = await pipe.execute()

        current_count = results[0]

        if current_count > settings.rate_limit_max:
            # Calculate seconds until the next 60s window starts.
            seconds_elapsed_in_window = int(time.time() % 60)
            retry_after = 60 - seconds_elapsed_in_window
            logger.warning(
                "Rate limit exceeded for service '%s': %d/%d requests in current window.",
                source_service,
                current_count,
                settings.rate_limit_max,
            )
            return False, retry_after

        return True, 0

    except RedisError as exc:
        # Fail-open: don't block ingestion on Redis unavailability.
        # LMS-CACHE-005 §10: application must not crash on Redis failure.
        logger.warning(
            "Redis error during rate limit check for service '%s' — "
            "allowing request through (fail-open): %s",
            source_service,
            exc,
        )
        return True, 0


# ===========================================================================
# Section 9: Metrics counters
# LMS-API-004 §2.8, LMS-CACHE-005 §9
# ===========================================================================

async def _increment_counter(redis: Redis, key: str, amount: int = 1) -> None:
    """
    Increments a Redis metrics counter. Non-fatal on error.
    """
    try:
        await redis.incr(key) if amount == 1 else await redis.incrby(key, amount)
    except RedisError:
        pass  # Metrics counters are best-effort — never block on failure.


async def increment_ingestion_counter(redis: Redis) -> None:
    """Increment the total ingestion events counter (LMS-API-004 §2.8)."""
    await _increment_counter(redis, METRICS_INGESTION_TOTAL_KEY)


async def increment_query_counter(redis: Redis) -> None:
    """Increment the total query events counter (LMS-API-004 §2.8)."""
    await _increment_counter(redis, METRICS_QUERY_TOTAL_KEY)


async def increment_error_counter(redis: Redis, error_code: str) -> None:
    """
    Increment the error counter for a specific error code.
    LMS-API-004 §2.8: "error_total (counter by error_code)"
    """
    key = f"lms:metrics:error:{error_code}"
    await _increment_counter(redis, key)


async def get_metrics_counters(redis: Redis) -> dict[str, Any]:
    """
    Retrieves all metrics counters from Redis for the GET /metrics endpoint.

    LMS-API-004 §2.8 metrics:
      - ingestion_total (counter)
      - query_total (counter)
      - cache_hit_ratio (gauge) — computed from hits / (hits + misses)
      - error_total (counter by error_code)

    LMS-CACHE-005 §9: "Monitor INFO stats keyspace_hits and keyspace_misses.
    Target cache hit ratio > 40%."

    Returns:
        Dict of metric name → value. All values default to 0 on Redis error.
    """
    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.get(METRICS_INGESTION_TOTAL_KEY)
            pipe.get(METRICS_QUERY_TOTAL_KEY)
            pipe.get(METRICS_CACHE_HITS_KEY)
            pipe.get(METRICS_CACHE_MISSES_KEY)
            results = await pipe.execute()

        ingestion_total = int(results[0] or 0)
        query_total = int(results[1] or 0)
        cache_hits = int(results[2] or 0)
        cache_misses = int(results[3] or 0)

        total_cache_ops = cache_hits + cache_misses
        cache_hit_ratio = (
            round(cache_hits / total_cache_ops, 4) if total_cache_ops > 0 else 0.0
        )

        # Scan for per-error-code counters.
        error_counts: dict[str, int] = {}
        error_cursor = 0
        while True:
            error_cursor, error_keys = await redis.scan(
                cursor=error_cursor, match="lms:metrics:error:*", count=50
            )
            for key in error_keys:
                error_code = key.removeprefix("lms:metrics:error:")
                val = await redis.get(key)
                error_counts[error_code] = int(val or 0)
            if error_cursor == 0:
                break

        return {
            "ingestion_total": ingestion_total,
            "query_total": query_total,
            "cache_hit_ratio": cache_hit_ratio,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "error_total": error_counts,
        }

    except RedisError as exc:
        logger.warning("Redis error fetching metrics counters: %s", exc)
        return {
            "ingestion_total": 0,
            "query_total": 0,
            "cache_hit_ratio": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
            "error_total": {},
        }
