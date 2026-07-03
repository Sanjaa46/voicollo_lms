# =============================================================================
# purpose:  Aggregates metrics data for the GET /metrics endpoint.
#           Sources:
#             - Redis counters (ingestion_total, query_total, cache stats)
#             - Redis retention metadata (last_run, deleted_count)
#           No DB queries are made for metrics — all counters are maintained
#           in Redis by cache_service.py and the retention job.
# implements: LMS-API-004 §2.8 (GET /metrics)
#             LMS-CACHE-005 §9 (Monitoring — cache_hit_ratio gauge)
#             LMS-BRD-001 FR-18 (SHOULD expose ingestion rate, query count,
#                                cache hit ratio, error count)
# =============================================================================

import logging
from datetime import datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.schemas.admin_schemas import MetricsResponse
from app.services.cache_service import get_metrics_counters

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retention job metadata keys — written by app/jobs/retention.py
# These are not in LMS-CACHE-005 key schema (they are metadata, not cache),
# but follow the lms: namespace convention.
# ---------------------------------------------------------------------------
RETENTION_LAST_RUN_KEY = "lms:retention:last_run"
RETENTION_DELETED_COUNT_KEY = "lms:retention:last_deleted_count"


async def get_metrics(redis: Redis) -> MetricsResponse:
    """
    Assembles the full metrics payload for GET /api/v1/metrics.

    All data is sourced from Redis — no DB round-trip.
    On Redis failure, returns zeroed metrics rather than raising 500.
    LMS-CACHE-005 §10: must not crash on Redis failure.

    LMS-API-004 §2.8 fields returned:
      ingestion_total       — total log entries ingested (counter)
      query_total           — total query requests served (counter)
      cache_hit_ratio       — hits / (hits + misses) (gauge, 0.0–1.0)
      error_total           — dict of error_code → count (counter per code)
      retention_last_run    — ISO timestamp of last retention job (or None)
      retention_deleted_count — rows deleted in last retention run (gauge)

    LMS-CACHE-005 §9: "Target cache hit ratio > 40% during normal operation."

    Args:
        redis: Async Redis client.

    Returns:
        MetricsResponse populated with current metric values.
    """
    # Fetch base counters from cache_service.
    counters = await get_metrics_counters(redis)

    # Fetch retention job metadata.
    retention_last_run: datetime | None = None
    retention_deleted_count: int = 0

    try:
        raw_last_run = await redis.get(RETENTION_LAST_RUN_KEY)
        if raw_last_run:
            retention_last_run = datetime.fromisoformat(raw_last_run)

        raw_deleted = await redis.get(RETENTION_DELETED_COUNT_KEY)
        if raw_deleted:
            retention_deleted_count = int(raw_deleted)

    except RedisError as exc:
        logger.warning("Redis error fetching retention metadata for metrics: %s", exc)
    except (ValueError, TypeError) as exc:
        logger.warning("Failed to parse retention metadata: %s", exc)

    return MetricsResponse(
        ingestion_total=counters["ingestion_total"],
        query_total=counters["query_total"],
        cache_hit_ratio=counters["cache_hit_ratio"],
        cache_hits=counters["cache_hits"],
        cache_misses=counters["cache_misses"],
        error_total=counters["error_total"],
        retention_last_run=retention_last_run,
        retention_deleted_count=retention_deleted_count,
    )


async def record_retention_run(
    redis: Redis,
    deleted_app_logs: int,
    deleted_audit_logs: int,
    run_timestamp: datetime,
) -> None:
    """
    Persists retention job execution metadata to Redis.
    Called by the retention job after each successful run.

    These values are read back by get_metrics() for the /metrics endpoint.
    LMS-API-004 §2.8: "retention_last_run (timestamp),
    retention_deleted_count (gauge)."

    Args:
        redis:              Async Redis client.
        deleted_app_logs:   Number of application_logs rows deleted.
        deleted_audit_logs: Number of audit_logs rows deleted.
        run_timestamp:      UTC datetime when the retention job ran.
    """
    total_deleted = deleted_app_logs + deleted_audit_logs

    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.set(RETENTION_LAST_RUN_KEY, run_timestamp.isoformat())
            pipe.set(RETENTION_DELETED_COUNT_KEY, str(total_deleted))
            await pipe.execute()

        logger.debug(
            "Retention run metadata stored: last_run=%s deleted=%d",
            run_timestamp.isoformat(),
            total_deleted,
        )
    except RedisError as exc:
        # Non-fatal — metrics will show stale data but system continues.
        logger.warning(
            "Failed to store retention run metadata in Redis: %s", exc
        )
