# =============================================================================
# purpose:  Log ingestion endpoints. Auth = valid access token, no roles.
# =============================================================================

import logging
from fastapi import APIRouter, Response
from redis.asyncio import Redis

from app.core.dependencies import DBSession, RedisClient, ServiceSignature
from app.core.exceptions import RateLimitExceededError
from app.schemas.log_schemas import (
    AppLogRequest, AppLogResponse,
    AuditLogRequest, AuditLogResponse,
    BatchAppLogRequest, BatchAppLogResponse,
)
from app.schemas.error_schemas import ErrorResponse
from app.services import log_service
from app.services.cache_service import check_and_increment_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/logs", tags=["Log Ingestion"])


async def _enforce_rate_limit(redis: Redis, source_service: str) -> None:
    allowed, retry_after = await check_and_increment_rate_limit(redis, source_service)
    if not allowed:
        raise RateLimitExceededError(source_service=source_service, retry_after_seconds=retry_after)


@router.post("/app", status_code=201, response_model=AppLogResponse,
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}})
async def ingest_app_log(
    request: AppLogRequest,
    db: DBSession, redis: RedisClient,
    _: ServiceSignature,
) -> AppLogResponse:
    await _enforce_rate_limit(redis, request.source_service)
    return await log_service.write_app_log(db=db, redis=redis, request=request)


@router.post("/app/batch", status_code=207, response_model=BatchAppLogResponse,
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}})
async def ingest_app_log_batch(
    request: BatchAppLogRequest,
    db: DBSession, redis: RedisClient,
    _: ServiceSignature,
    response: Response = None,
) -> BatchAppLogResponse:
    if request.logs:
        await _enforce_rate_limit(redis, request.logs[0].source_service)
    result = await log_service.write_app_log_batch(db=db, redis=redis, request=request)
    if response is not None:
        response.status_code = 207
    return result


@router.post("/audit", status_code=201, response_model=AuditLogResponse,
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}})
async def ingest_audit_log(
    request: AuditLogRequest,
    db: DBSession, redis: RedisClient,
    _: ServiceSignature,
) -> AuditLogResponse:
    await _enforce_rate_limit(redis, request.source_service)
    return await log_service.write_audit_log(db=db, redis=redis, request=request)


@router.delete("/audit", status_code=405,
    responses={405: {"model": ErrorResponse}})
async def delete_audit_blocked() -> None:
    from app.core.exceptions import AuditLogDeleteForbiddenError
    raise AuditLogDeleteForbiddenError()


@router.delete("/audit/{log_id}", status_code=405,
    responses={405: {"model": ErrorResponse}})
async def delete_audit_by_id_blocked(log_id: int) -> None:
    from app.core.exceptions import AuditLogDeleteForbiddenError
    raise AuditLogDeleteForbiddenError()
