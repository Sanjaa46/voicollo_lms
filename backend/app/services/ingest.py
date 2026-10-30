"""Log ingestion (write path)."""

import logging
from collections import Counter

from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import LMSError, RateLimitExceededError
from app.core.time import to_utc_naive
from app.models import ApplicationLog, AuditLog
from app.schemas.logs import (
    AppLogRequest,
    AuditLogRequest,
    BatchAppLogRequest,
    BatchAppLogResponse,
    BatchAppLogResult,
    IngestResponse,
)
from app.services import cache, metrics
from app.services.service_registry import ensure_can_ingest

logger = logging.getLogger(__name__)


async def enforce_rate_limit(redis: Redis, counts: dict[str, int]) -> None:
    exceeded = await cache.consume_rate_limit(redis, counts)
    if exceeded:
        raise RateLimitExceededError(*exceeded)


def _app_row(entry: AppLogRequest) -> ApplicationLog:
    return ApplicationLog(
        source_service=entry.source_service,
        level=entry.level.value,
        message=entry.message,
        environment=entry.environment,
        created_at=to_utc_naive(entry.created_at),
        trace_id=entry.trace_id,
        context_json=entry.context_json,
    )


async def _after_write(redis: Redis, count: int) -> None:
    await cache.bump_query_generation(redis)
    await metrics.incr(redis, metrics.INGESTION_TOTAL, count)


async def write_app_log(db: AsyncSession, redis: Redis, entry: AppLogRequest) -> IngestResponse:
    await enforce_rate_limit(redis, {entry.source_service: 1})
    await ensure_can_ingest(db, redis, entry.source_service)
    row = _app_row(entry)
    db.add(row)
    await db.flush()
    await _after_write(redis, 1)
    return IngestResponse(log_id=row.id, ingested_at=row.ingested_at)


async def write_audit_log(db: AsyncSession, redis: Redis, entry: AuditLogRequest) -> IngestResponse:
    await enforce_rate_limit(redis, {entry.source_service: 1})
    await ensure_can_ingest(db, redis, entry.source_service)
    row = AuditLog(
        source_service=entry.source_service,
        environment=entry.environment,
        actor_id=entry.actor_id,
        actor_type=entry.actor_type.value,
        action=entry.action,
        target_resource=entry.target_resource,
        outcome=entry.outcome.value,
        event_time=to_utc_naive(entry.event_time),
        ip_address=entry.ip_address,
        detail_json=entry.detail_json,
    )
    db.add(row)
    await db.flush()
    await _after_write(redis, 1)
    return IngestResponse(log_id=row.id, ingested_at=row.ingested_at)


def _validation_message(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(p) for p in err['loc']) or 'entry'}: {err['msg']}" for err in exc.errors()
    )


async def write_app_log_batch(
    db: AsyncSession, redis: Redis, batch: BatchAppLogRequest
) -> BatchAppLogResponse:
    """Ingest up to 100 entries. Every entry succeeds or fails on its own."""
    results: dict[int, BatchAppLogResult] = {}
    valid: list[tuple[int, AppLogRequest]] = []

    for index, raw in enumerate(batch.logs):
        try:
            valid.append((index, AppLogRequest.model_validate(raw)))
        except ValidationError as exc:
            results[index] = BatchAppLogResult(
                index=index,
                success=False,
                error_code="VALIDATION_ERROR",
                message=_validation_message(exc),
            )

    if valid:
        await enforce_rate_limit(redis, dict(Counter(e.source_service for _, e in valid)))

    eligible: list[tuple[int, ApplicationLog]] = []
    checked: dict[str, LMSError | None] = {}
    for index, entry in valid:
        if entry.source_service not in checked:
            try:
                await ensure_can_ingest(db, redis, entry.source_service)
                checked[entry.source_service] = None
            except LMSError as exc:
                checked[entry.source_service] = exc
        if error := checked[entry.source_service]:
            results[index] = BatchAppLogResult(
                index=index, success=False, error_code=error.error_code, message=error.message
            )
        else:
            eligible.append((index, _app_row(entry)))

    if eligible:
        await _insert_isolated(db, eligible, results)

    ordered = [results[i] for i in sorted(results)]
    succeeded = sum(r.success for r in ordered)
    if succeeded:
        await _after_write(redis, succeeded)
    return BatchAppLogResponse(
        results=ordered,
        total=len(ordered),
        succeeded=succeeded,
        failed=len(ordered) - succeeded,
    )


async def _insert_isolated(
    db: AsyncSession,
    rows: list[tuple[int, ApplicationLog]],
    results: dict[int, BatchAppLogResult],
) -> None:
    """Insert all rows in one savepoint; on failure, retry row by row to isolate the bad one."""
    try:
        async with db.begin_nested():
            db.add_all([row for _, row in rows])
        for index, row in rows:
            results[index] = BatchAppLogResult(index=index, success=True, log_id=row.id)
        return
    except SQLAlchemyError as exc:
        logger.warning("Bulk insert failed (%s); retrying entries individually", exc)

    for index, row in rows:
        fresh = ApplicationLog(
            **{
                c.key: getattr(row, c.key)
                for c in ApplicationLog.__table__.columns
                if c.key != "id"
            }
        )
        try:
            async with db.begin_nested():
                db.add(fresh)
            results[index] = BatchAppLogResult(index=index, success=True, log_id=fresh.id)
        except SQLAlchemyError as exc:
            logger.error("Batch entry %d failed to insert: %s", index, exc)
            results[index] = BatchAppLogResult(
                index=index,
                success=False,
                error_code="INTERNAL_ERROR",
                message="The entry could not be stored.",
            )
