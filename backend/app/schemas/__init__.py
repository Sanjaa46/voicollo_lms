# =============================================================================
# filename: app/schemas/__init__.py
# purpose:  Re-exports all Pydantic v2 request/response schemas.
#           Import from here rather than individual modules to keep
#           consumer imports stable if schemas are reorganised.
# implements: LMS-SDD-002 §3.1 (app/schemas/)
# =============================================================================

from app.schemas.log_schemas import (
    AppLogRequest,
    AppLogResponse,
    AuditLogRequest,
    AuditLogResponse,
    BatchAppLogRequest,
    BatchAppLogResponse,
    BatchAppLogResult,
    LogQueryParams,
    UnifiedLogEntry,
    PaginatedLogsResponse,
)
from app.schemas.admin_schemas import (
    HealthResponse,
    MetricsResponse,
    ExportQueryParams,
)
from app.schemas.error_schemas import ErrorResponse

__all__ = [
    # Log ingestion
    "AppLogRequest",
    "AppLogResponse",
    "AuditLogRequest",
    "AuditLogResponse",
    "BatchAppLogRequest",
    "BatchAppLogResponse",
    "BatchAppLogResult",
    # Log querying
    "LogQueryParams",
    "UnifiedLogEntry",
    "PaginatedLogsResponse",
    # Admin
    "HealthResponse",
    "MetricsResponse",
    "ExportQueryParams",
    # Error
    "ErrorResponse",
]
