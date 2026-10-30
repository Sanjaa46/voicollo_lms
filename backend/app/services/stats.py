"""Dashboard statistics for a rolling time window."""

from datetime import datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.time import utcnow
from app.models import ApplicationLog, AuditLog
from app.models.application_log import LOG_LEVELS
from app.models.audit_log import OUTCOMES
from app.schemas.logs import AppLogEntry
from app.schemas.stats import OverviewResponse, ServiceVolume, TimeBucket
from app.services import cache

_BUCKET_CHOICES = (300, 900, 1800, 3600, 3 * 3600, 6 * 3600, 86400)
_MAX_BUCKETS = 96


def bucket_seconds_for(hours: int) -> int:
    for size in _BUCKET_CHOICES:
        if hours * 3600 / size <= _MAX_BUCKETS:
            return size
    return _BUCKET_CHOICES[-1]


def _epoch(column, dialect: str):
    if dialect == "sqlite":
        return cast(func.strftime("%s", column), Integer)
    return func.unix_timestamp(column)  # session time zone is pinned to UTC


async def overview(db: AsyncSession, redis: Redis, hours: int) -> OverviewResponse:
    key = await cache.cache_key(redis, "stats", {"hours": hours, "minute": utcnow().minute})
    if cached := await cache.get_cached(redis, key):
        return OverviewResponse.model_validate(cached)

    result = await _compute(db, hours)
    await cache.set_cached(
        redis, key, result.model_dump(mode="json"), get_settings().stats_cache_ttl_seconds
    )
    return result


async def _compute(db: AsyncSession, hours: int) -> OverviewResponse:
    dialect = db.get_bind().dialect.name
    now = utcnow()
    bucket = bucket_seconds_for(hours)
    since = now - timedelta(hours=hours)
    epoch_since = int((since - datetime(1970, 1, 1)).total_seconds())
    first_bucket = epoch_since // bucket

    levels = dict.fromkeys(LOG_LEVELS, 0)
    for level, count in await db.execute(
        select(ApplicationLog.level, func.count())
        .where(ApplicationLog.created_at >= since)
        .group_by(ApplicationLog.level)
    ):
        levels[level] = count

    outcomes = dict.fromkeys(OUTCOMES, 0)
    for outcome, count in await db.execute(
        select(AuditLog.outcome, func.count())
        .where(AuditLog.event_time >= since)
        .group_by(AuditLog.outcome)
    ):
        outcomes[outcome] = count

    buckets: dict[int, TimeBucket] = {}
    span = (int((now - since).total_seconds()) // bucket) + 1
    for i in range(span):
        index = first_bucket + i
        buckets[index] = TimeBucket(start=datetime(1970, 1, 1) + timedelta(seconds=index * bucket))

    app_bucket = (_epoch(ApplicationLog.created_at, dialect) // bucket).label("b")
    for b, level, count in await db.execute(
        select(app_bucket, ApplicationLog.level, func.count())
        .where(ApplicationLog.created_at >= since, ApplicationLog.created_at <= now)
        .group_by(app_bucket, ApplicationLog.level)
    ):
        if (target := buckets.get(int(b))) is not None:
            setattr(target, level.lower(), getattr(target, level.lower()) + count)

    audit_bucket = (_epoch(AuditLog.event_time, dialect) // bucket).label("b")
    for b, count in await db.execute(
        select(audit_bucket, func.count())
        .where(AuditLog.event_time >= since, AuditLog.event_time <= now)
        .group_by(audit_bucket)
    ):
        if (target := buckets.get(int(b))) is not None:
            target.audit += count

    services: dict[str, ServiceVolume] = {}
    is_error = ApplicationLog.level.in_(("ERROR", "FATAL"))
    for sid, total, errors in await db.execute(
        select(
            ApplicationLog.source_service,
            func.count(),
            func.sum(cast(is_error, Integer)),
        )
        .where(ApplicationLog.created_at >= since)
        .group_by(ApplicationLog.source_service)
    ):
        services[sid] = ServiceVolume(
            source_service=sid, app_logs=total, errors=int(errors or 0), audit_logs=0
        )
    for sid, total in await db.execute(
        select(AuditLog.source_service, func.count())
        .where(AuditLog.event_time >= since)
        .group_by(AuditLog.source_service)
    ):
        services.setdefault(
            sid, ServiceVolume(source_service=sid, app_logs=0, errors=0, audit_logs=0)
        ).audit_logs = total
    top = sorted(services.values(), key=lambda s: s.app_logs + s.audit_logs, reverse=True)[:8]

    recent = await db.scalars(
        select(ApplicationLog)
        .where(ApplicationLog.level.in_(("ERROR", "FATAL")), ApplicationLog.created_at >= since)
        .order_by(ApplicationLog.created_at.desc(), ApplicationLog.id.desc())
        .limit(8)
    )

    app_window = sum(levels.values())
    return OverviewResponse(
        window_hours=hours,
        bucket_seconds=bucket,
        generated_at=now,
        totals={
            "app_logs": app_window,
            "audit_logs": sum(outcomes.values()),
            "errors": levels["ERROR"] + levels["FATAL"],
            "active_services": len(services),
            "app_logs_all_time": await db.scalar(select(func.count()).select_from(ApplicationLog))
            or 0,
            "audit_logs_all_time": await db.scalar(select(func.count()).select_from(AuditLog)) or 0,
        },
        levels=levels,
        outcomes=outcomes,
        error_rate=round((levels["ERROR"] + levels["FATAL"]) / app_window, 4) if app_window else 0,
        timeline=[buckets[k] for k in sorted(buckets)],
        top_services=top,
        recent_errors=[AppLogEntry.model_validate(r) for r in recent],
    )
