# =============================================================================
# purpose:  Log query endpoints. Auth = valid access token, no roles.
# =============================================================================

import logging
from typing import Annotated
from fastapi import APIRouter, Path, Query, Response

from app.core.dependencies import CurrentUser, DBSession, RedisClient
from app.schemas.log_schemas import (
    AppLogEntry, AuditLogEntry, LogQueryParams,
    LogType, LogLevel, SortOrder, PaginatedLogsResponse,
)
from app.schemas.error_schemas import ErrorResponse
from app.services import log_service
from app.services.cache_service import build_query_cache_key, get_cached_query, set_cached_query

from app.jobs.retention import run_retention_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/logs", tags=["Log Query"])


@router.get("", status_code=200, response_model=PaginatedLogsResponse,
    responses={401: {"model": ErrorResponse}})
async def query_logs(
    response: Response,
    db: DBSession, redis: RedisClient,
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
    page_size:      int                = Query(default=50, ge=1, le=500),
) -> PaginatedLogsResponse:
    from datetime import datetime
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
        page=page, page_size=page_size,
    )
    logger.info(level)

    cache_key = build_query_cache_key(params.to_cache_key_dict())
    cached, headers = await get_cached_query(redis, cache_key)
    for k, v in headers.items():
        response.headers[k] = v

    if cached is not None:
        return PaginatedLogsResponse(**cached)

    result = await log_service.query_logs(db=db, redis=redis, params=params)
    await set_cached_query(redis, cache_key, result.model_dump(mode="json"))
    return result


@router.get("/{log_type}/{log_id}", status_code=200,
    response_model=AppLogEntry|AuditLogEntry,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
async def get_single_log(
    log_type: Annotated[str, Path(pattern="^(app|audit)$")],
    log_id:   Annotated[int, Path(ge=1)],
    db: DBSession,
    _: CurrentUser,
) -> AppLogEntry | AuditLogEntry:
    # Single user = always admin, always can see audit entries.
    return await log_service.get_single_log(
        db=db, log_type=log_type, log_id=log_id, is_admin=True
    )
