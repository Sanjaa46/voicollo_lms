"""Log query, detail and export endpoints (user session required)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Response
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.core.dependencies import CurrentUser, DBSession, RedisClient
from app.core.time import utcnow
from app.schemas.common import ErrorResponse
from app.schemas.logs import (
    AppLogEntry,
    AuditLogEntry,
    ExportParams,
    LogQueryParams,
    PaginatedLogsResponse,
)
from app.services import cache, export, log_query, metrics

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get(
    "",
    response_model=PaginatedLogsResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Search logs across both tables with global ordering",
)
async def query_logs(
    params: Annotated[LogQueryParams, Query()],
    response: Response,
    db: DBSession,
    redis: RedisClient,
    _: CurrentUser,
) -> PaginatedLogsResponse:
    await metrics.incr(redis, metrics.QUERY_TOTAL)
    key = await cache.cache_key(redis, "logs", params.model_dump(mode="json"))
    if (cached := await cache.get_cached(redis, key)) is not None:
        response.headers["X-Cache"] = "HIT"
        return PaginatedLogsResponse.model_validate(cached)

    response.headers["X-Cache"] = "MISS"
    result = await log_query.query_logs(db, params, params.page, params.page_size)
    await cache.set_cached(
        redis, key, result.model_dump(mode="json"), get_settings().query_cache_ttl_seconds
    )
    return result


@router.get(
    "/export",
    responses={
        200: {"content": {"application/json": {}, "text/csv": {}}},
        401: {"model": ErrorResponse},
    },
    summary="Download matching logs as JSON or CSV (max 10 000 rows)",
)
async def export_logs(
    params: Annotated[ExportParams, Query()], db: DBSession, _: CurrentUser
) -> StreamingResponse:
    chunks, media_type, total = await export.export_logs(db, params)
    filename = f"lms-logs-{utcnow():%Y%m%d-%H%M%S}.{params.format}"
    return StreamingResponse(
        chunks,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Total-Count": str(total),
        },
    )


@router.get(
    "/{log_type}/{log_id}",
    response_model=AppLogEntry | AuditLogEntry,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_log(
    log_type: Literal["app", "audit"],
    log_id: Annotated[int, Path(ge=1)],
    db: DBSession,
    _: CurrentUser,
) -> AppLogEntry | AuditLogEntry:
    return await log_query.get_log(db, log_type, log_id)
