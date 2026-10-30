"""Health, version, metrics, retention and dashboard statistics."""

import time
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.core.config import get_settings
from app.core.database import ping_database
from app.core.dependencies import CurrentUser, DBSession, RedisClient
from app.core.redis import ping_redis
from app.jobs import retention
from app.jobs.scheduler import next_retention_run
from app.schemas.common import ErrorResponse
from app.schemas.stats import OverviewResponse
from app.schemas.system import (
    DependencyStatus,
    HealthResponse,
    MetricsResponse,
    RetentionPolicy,
    RetentionRun,
    RetentionStatus,
    SystemStatus,
    VersionResponse,
)
from app.services import cache, metrics, stats

router = APIRouter(tags=["System"])
_STARTED = time.monotonic()
_AUTH = {401: {"model": ErrorResponse}}


async def _health(redis, include_detail: bool) -> HealthResponse:
    settings = get_settings()
    db_raw = await cache.get_cached_health(redis)
    if db_raw is None:
        db_raw = await ping_database()
        await cache.set_cached_health(redis, db_raw)
    redis_raw = await ping_redis()

    def dep(raw: dict) -> DependencyStatus:
        return DependencyStatus(
            status=raw["status"],
            latency_ms=raw.get("latency_ms"),
            detail=raw.get("detail") if include_detail else None,
        )

    database, cache_status = dep(db_raw), dep(redis_raw)
    healthy = database.status == "ok" and cache_status.status == "ok"
    return HealthResponse(
        status="healthy" if healthy else "degraded",
        version=settings.app_version,
        uptime_seconds=round(time.monotonic() - _STARTED, 1),
        database=database,
        cache=cache_status,
    )


def _version() -> VersionResponse:
    s = get_settings()
    return VersionResponse(
        version=s.app_version, git_sha=s.git_sha, build_date=s.build_date, environment=s.app_env
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
    summary="Liveness/readiness probe (public; error details hidden in production)",
)
async def health(response: Response, redis: RedisClient) -> HealthResponse:
    result = await _health(redis, include_detail=not get_settings().is_production)
    if result.status != "healthy":
        response.status_code = 503
    return result


@router.get("/version", response_model=VersionResponse, summary="Build information (public)")
async def version() -> VersionResponse:
    return _version()


@router.get("/metrics", response_model=MetricsResponse, responses=_AUTH)
async def get_metrics(redis: RedisClient, _: CurrentUser) -> MetricsResponse:
    return MetricsResponse.model_validate(await metrics.read_counters(redis))


async def _retention_status(redis) -> RetentionStatus:
    s = get_settings()
    return RetentionStatus(
        policy=RetentionPolicy(
            enabled=s.retention_enabled,
            app_log_retention_days=s.app_log_retention_days,
            audit_log_retention_days=s.audit_log_retention_days,
            schedule=f"{s.retention_job_hour:02d}:{s.retention_job_minute:02d}",
            timezone=s.scheduler_timezone,
            next_run_at=next_retention_run(),
        ),
        last_run=await retention.last_run(redis),
        running=await retention.is_running(redis),
    )


@router.get("/system/status", response_model=SystemStatus, responses=_AUTH)
async def system_status(redis: RedisClient, _: CurrentUser) -> SystemStatus:
    s = get_settings()
    return SystemStatus(
        health=await _health(redis, include_detail=True),
        version=_version(),
        metrics=MetricsResponse.model_validate(await metrics.read_counters(redis)),
        retention=await _retention_status(redis),
        rate_limit_per_minute=s.rate_limit_max,
        signature_tolerance_seconds=s.signature_tolerance_seconds,
    )


@router.get("/retention", response_model=RetentionStatus, responses=_AUTH)
async def retention_status(redis: RedisClient, _: CurrentUser) -> RetentionStatus:
    return await _retention_status(redis)


@router.post(
    "/retention/run",
    response_model=RetentionRun,
    responses={**_AUTH, 409: {"model": ErrorResponse}},
    summary="Run the retention purge now",
)
async def run_retention_now(redis: RedisClient, _: CurrentUser) -> RetentionRun:
    return await retention.run_retention("manual", redis)


@router.get("/stats/overview", response_model=OverviewResponse, responses=_AUTH)
async def stats_overview(
    db: DBSession,
    redis: RedisClient,
    _: CurrentUser,
    hours: Annotated[int, Query(ge=1, le=24 * 30)] = 24,
) -> OverviewResponse:
    return await stats.overview(db, redis, hours)
