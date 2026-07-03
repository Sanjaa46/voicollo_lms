# =============================================================================
# purpose:  Admin / observability endpoints. Auth = valid access token.
# =============================================================================

import logging
import time
from typing import Annotated
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import ping_database
from app.core.dependencies import CurrentUser, DBSession, RedisClient
from app.core.redis_client import ping_redis
from app.schemas.admin_schemas import (
    DependencyStatus, ExportFormat, HealthResponse, MetricsResponse
)
from app.schemas.log_schemas import LogType, LogLevel, SortOrder, LogQueryParams
from app.schemas.error_schemas import ErrorResponse
from app.services import log_service
from app.services.cache_service import get_cached_health, set_cached_health
from app.services.metrics_service import get_metrics

logger = logging.getLogger(__name__)
_PROCESS_START_TIME = time.monotonic()

router = APIRouter(tags=["Administration"])


@router.get("/health", status_code=200, response_model=HealthResponse,
    responses={503: {"model": HealthResponse}})
async def health_check(response: Response, redis: RedisClient) -> HealthResponse:
    settings = get_settings()

    cached_db = await get_cached_health(redis)
    if cached_db:
        db_status = DependencyStatus(**cached_db)
    else:
        raw = await ping_database()
        db_status = DependencyStatus(status=raw["status"], latency_ms=raw.get("latency_ms"), detail=raw.get("detail"))
        await set_cached_health(redis, raw)

    raw_redis = await ping_redis()
    cache_status = DependencyStatus(status=raw_redis["status"], latency_ms=raw_redis.get("latency_ms"), detail=raw_redis.get("detail"))

    healthy = db_status.status == "ok" and cache_status.status == "ok"
    if not healthy:
        response.status_code = 503

    return HealthResponse(
        status="healthy" if healthy else "degraded",
        database=db_status, cache=cache_status,
        version=settings.app_version,
        uptime_seconds=round(time.monotonic() - _PROCESS_START_TIME, 2),
    )


@router.get("/metrics", status_code=200, response_model=MetricsResponse,
    responses={401: {"model": ErrorResponse}})
async def get_system_metrics(redis: RedisClient, _: CurrentUser) -> MetricsResponse:
    return await get_metrics(redis)


@router.get("/logs/export", responses={401: {"model": ErrorResponse}})
async def export_logs(
    db: DBSession,
    _: CurrentUser,
    log_type:       LogType            = Query(default=LogType.BOTH),
    level:          list[LogLevel]|None= Query(default=None),
    source_service: str|None           = Query(default=None),
    start_time:     str|None           = Query(default=None),
    end_time:       str|None           = Query(default=None),
    actor_id:       str|None           = Query(default=None),
    trace_id:       str|None           = Query(default=None),
    sort:           SortOrder          = Query(default=SortOrder.DESC),
    page:           int                = Query(default=1, ge=1),
    page_size:      int                = Query(default=500, ge=1, le=10000),
    format:         ExportFormat       = Query(default=ExportFormat.JSON),
) -> Response:
    from fastapi import HTTPException

    def _parse_dt(s):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(422, f"Invalid datetime: {s}")

    params = LogQueryParams(
        log_type=log_type, level=level, source_service=source_service,
        start_time=_parse_dt(start_time) if start_time else None,
        end_time=_parse_dt(end_time) if end_time else None,
        actor_id=actor_id, trace_id=trace_id, sort=sort,
        page=page, page_size=min(page_size, 10000),
    )

    content, content_type = await log_service.export_logs(db=db, params=params, export_format=format.value)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ext = "json" if format == ExportFormat.JSON else "csv"

    return Response(
        content=content, media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="lms_export_{ts}.{ext}"'},
    )
