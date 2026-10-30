"""Retention purge job.

* app logs:   deleted when created_at  < now - APP_LOG_RETENTION_DAYS
* audit logs: deleted when ingested_at < now - AUDIT_LOG_RETENTION_DAYS
  (ingested_at, not event_time: a producer cannot shorten an audit record's
  lifetime by back-dating it)

Runs under a Redis lock so multiple Uvicorn workers (each with its own
scheduler) never purge concurrently. Deletes in chunks to keep locks short.
"""

import json
import logging
import time
from datetime import timedelta
from typing import Literal

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import retention_session_scope, session_scope
from app.core.exceptions import RetentionAlreadyRunningError
from app.core.redis import get_redis_client
from app.core.time import utcnow
from app.models import ApplicationLog, AuditLog
from app.schemas.system import RetentionRun
from app.services import cache
from app.services.service_registry import SYSTEM_SERVICE_ID

logger = logging.getLogger(__name__)

LOCK_KEY = "lms:lock:retention"
LOCK_TTL_SECONDS = 3600
LAST_RUN_KEY = "lms:retention:last_run"
CHUNK_SIZE = 5000

Trigger = Literal["schedule", "manual"]


async def _delete_older_than(session: AsyncSession, model, column, threshold) -> int:
    """Delete in primary-key chunks so no single statement holds locks for long."""
    deleted = 0
    while True:
        ids = list(
            (
                await session.scalars(select(model.id).where(column < threshold).limit(CHUNK_SIZE))
            ).all()
        )
        if not ids:
            return deleted
        result = await session.execute(
            delete(model).where(model.id.in_(ids)).execution_options(synchronize_session=False)
        )
        await session.commit()
        deleted += result.rowcount or 0
        if len(ids) < CHUNK_SIZE:
            return deleted


async def _write_self_log(run: RetentionRun) -> None:
    async with session_scope() as session:
        session.add(
            ApplicationLog(
                source_service=SYSTEM_SERVICE_ID,
                level="INFO" if run.status == "SUCCESS" else "ERROR",
                message=(
                    f"Retention {run.status.lower()}: deleted {run.deleted_app_logs} app logs "
                    f"and {run.deleted_audit_logs} audit logs in {run.duration_seconds:.2f}s"
                    + (f" — {run.error}" if run.error else "")
                ),
                environment=get_settings().app_env,
                created_at=run.started_at,
                context_json={"job": "retention", **run.model_dump(mode="json")},
            )
        )


async def run_retention(trigger: Trigger = "schedule", redis: Redis | None = None) -> RetentionRun:
    settings = get_settings()
    redis = redis or get_redis_client()
    token = str(time.time_ns())
    try:
        acquired = await redis.set(LOCK_KEY, token, nx=True, ex=LOCK_TTL_SECONDS)
    except RedisError as exc:
        logger.error("Retention skipped: cannot acquire lock (%s)", exc)
        raise
    if not acquired:
        logger.info("Retention already running (%s trigger ignored).", trigger)
        raise RetentionAlreadyRunningError()

    started = utcnow()
    clock = time.monotonic()
    deleted_app = deleted_audit = 0
    error: str | None = None
    try:
        async with retention_session_scope() as session:
            deleted_app = await _delete_older_than(
                session,
                ApplicationLog,
                ApplicationLog.created_at,
                started - timedelta(days=settings.app_log_retention_days),
            )
            deleted_audit = await _delete_older_than(
                session,
                AuditLog,
                AuditLog.ingested_at,
                started - timedelta(days=settings.audit_log_retention_days),
            )
    except Exception as exc:  # the job must never crash the server
        logger.exception("Retention purge failed")
        error = f"{type(exc).__name__}: {exc}"

    run = RetentionRun(
        status="FAILURE" if error else "SUCCESS",
        started_at=started,
        duration_seconds=round(time.monotonic() - clock, 3),
        deleted_app_logs=deleted_app,
        deleted_audit_logs=deleted_audit,
        trigger=trigger,
        error=error,
    )
    try:
        await _write_self_log(run)
    except Exception:
        logger.exception("Could not write retention self-log")
    try:
        await redis.set(LAST_RUN_KEY, run.model_dump_json())
        if deleted_app or deleted_audit:
            await cache.bump_query_generation(redis)
        if await redis.get(LOCK_KEY) == token:
            await redis.delete(LOCK_KEY)
    except RedisError as exc:
        logger.warning("Could not record retention result: %s", exc)

    logger.info(
        "Retention %s: app=%d audit=%d in %.2fs",
        run.status,
        deleted_app,
        deleted_audit,
        run.duration_seconds,
    )
    return run


async def scheduled_retention() -> None:
    try:
        await run_retention("schedule")
    except RetentionAlreadyRunningError:
        pass
    except Exception:
        logger.exception("Scheduled retention could not start")


async def last_run(redis: Redis) -> RetentionRun | None:
    try:
        raw = await redis.get(LAST_RUN_KEY)
        return RetentionRun.model_validate(json.loads(raw)) if raw else None
    except (RedisError, ValueError):
        return None


async def is_running(redis: Redis) -> bool:
    try:
        return bool(await redis.exists(LOCK_KEY))
    except RedisError:
        return False
