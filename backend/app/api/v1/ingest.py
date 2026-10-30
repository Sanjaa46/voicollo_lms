"""Producer endpoints. Authenticated by HMAC signature, not by user session."""

from fastapi import APIRouter

from app.core.dependencies import DBSession, RedisClient, ServiceSignature
from app.core.exceptions import AuditLogImmutableError
from app.schemas.common import ErrorResponse
from app.schemas.logs import (
    AppLogRequest,
    AuditLogRequest,
    BatchAppLogRequest,
    BatchAppLogResponse,
    IngestResponse,
)
from app.services import ingest

router = APIRouter(prefix="/logs", tags=["Ingestion"])

_ERRORS = {
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired signature"},
    403: {"model": ErrorResponse, "description": "source_service is disabled"},
    409: {"model": ErrorResponse, "description": "Replayed request"},
    422: {"model": ErrorResponse, "description": "Invalid payload or unknown source_service"},
    429: {"model": ErrorResponse, "description": "Rate limit exceeded (see Retry-After)"},
}


@router.post("/app", status_code=201, response_model=IngestResponse, responses=_ERRORS)
async def ingest_app_log(
    body: AppLogRequest, db: DBSession, redis: RedisClient, _: ServiceSignature
) -> IngestResponse:
    return await ingest.write_app_log(db, redis, body)


@router.post(
    "/app/batch",
    status_code=207,
    response_model=BatchAppLogResponse,
    responses=_ERRORS,
    summary="Ingest up to 100 app logs; each entry succeeds or fails independently",
)
async def ingest_app_log_batch(
    body: BatchAppLogRequest, db: DBSession, redis: RedisClient, _: ServiceSignature
) -> BatchAppLogResponse:
    return await ingest.write_app_log_batch(db, redis, body)


@router.post("/audit", status_code=201, response_model=IngestResponse, responses=_ERRORS)
async def ingest_audit_log(
    body: AuditLogRequest, db: DBSession, redis: RedisClient, _: ServiceSignature
) -> IngestResponse:
    return await ingest.write_audit_log(db, redis, body)


@router.delete("/audit", status_code=405, include_in_schema=False)
@router.delete("/audit/{log_id}", status_code=405, include_in_schema=False)
async def delete_audit_blocked() -> None:
    raise AuditLogImmutableError()
