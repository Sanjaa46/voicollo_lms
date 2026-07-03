# =============================================================================
# purpose:  Pydantic v2 schemas for admin endpoints:
#             - GET /health  (LMS-API-004 §2.7)
#             - GET /metrics (LMS-API-004 §2.8)
#             - GET /logs/export (LMS-API-004 §2.6)
# implements: LMS-API-004 §2.6 (Export endpoint params)
#             LMS-API-004 §2.7 (Health check response fields)
#             LMS-API-004 §2.8 (Metrics response fields)
#             LMS-BRD-001 FR-16, FR-17, FR-18
# =============================================================================

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.log_schemas import LogType, LogLevel, SortOrder


# ===========================================================================
# Health Check — GET /health
# LMS-API-004 §2.7
# ===========================================================================

class DependencyStatus(BaseModel):
    """
    Status of a single infrastructure dependency (database or cache).
    LMS-API-004 §2.7: "database: ok or error + latency_ms"
    """

    status: str = Field(
        ...,
        description="'ok' or 'error'",
        examples=["ok", "error"],
    )
    latency_ms: float | None = Field(
        default=None,
        description="Round-trip latency in milliseconds. None if status is error.",
    )
    detail: str | None = Field(
        default=None,
        description="Error detail when status is 'error'. Omitted when ok.",
    )


class HealthResponse(BaseModel):
    """
    Response body for GET /api/v1/health.
    LMS-API-004 §2.7 response fields — all fields match exactly.

    HTTP 200 when status='healthy'.
    HTTP 503 when status='degraded' (any dependency is down).
    LMS-API-004 §2.7: "Returns HTTP 200 if healthy, 503 if any dependency is down."
    """

    status: str = Field(
        ...,
        description="'healthy' or 'degraded'",
        examples=["healthy", "degraded"],
    )
    database: DependencyStatus = Field(
        ...,
        description="MariaDB connectivity status and latency",
    )
    cache: DependencyStatus = Field(
        ...,
        description="Redis connectivity status and latency",
    )
    version: str = Field(
        ...,
        description="Application version string",
        examples=["1.0.0"],
    )
    uptime_seconds: float = Field(
        ...,
        description="Process uptime in seconds",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "database": {"status": "ok", "latency_ms": 2.1},
                "cache": {"status": "ok", "latency_ms": 0.4},
                "version": "1.0.0",
                "uptime_seconds": 86412.3,
            }
        }
    }


# ===========================================================================
# Metrics — GET /metrics
# LMS-API-004 §2.8
# ===========================================================================

class MetricsResponse(BaseModel):
    """
    Response body for GET /api/v1/metrics.
    LMS-API-004 §2.8 fields — Prometheus-compatible or JSON metrics.

    Fields per LMS-API-004 §2.8:
      ingestion_total       — counter
      query_total           — counter
      cache_hit_ratio       — gauge
      error_total           — counter by error_code
      retention_last_run    — timestamp
      retention_deleted_count — gauge
    LMS-BRD-001 FR-18: "SHOULD expose ingestion rate, query count,
    cache hit ratio, and error count."
    """

    ingestion_total: int = Field(
        ...,
        description="Total number of log entries ingested since last restart",
    )
    query_total: int = Field(
        ...,
        description="Total number of query requests served since last restart",
    )
    cache_hit_ratio: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Cache hit ratio (0.0–1.0). "
            "LMS-CACHE-005 §9: target > 0.40 during normal operation."
        ),
    )
    cache_hits: int = Field(
        ...,
        description="Total cache hits since last restart",
    )
    cache_misses: int = Field(
        ...,
        description="Total cache misses since last restart",
    )
    error_total: dict[str, int] = Field(
        default_factory=dict,
        description="Error event counts keyed by error_code",
    )
    retention_last_run: datetime | None = Field(
        default=None,
        description="Timestamp of the last successful retention job run (UTC)",
    )
    retention_deleted_count: int = Field(
        default=0,
        description="Number of log entries deleted in the most recent retention run",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "ingestion_total": 8423,
                "query_total": 314,
                "cache_hit_ratio": 0.68,
                "cache_hits": 213,
                "cache_misses": 101,
                "error_total": {
                    "VALIDATION_ERROR": 12,
                    "AUTH_TOKEN_INVALID": 3,
                },
                "retention_last_run": "2025-06-11T18:00:00.000Z",
                "retention_deleted_count": 1204,
            }
        }
    }


# ===========================================================================
# Export — GET /logs/export
# LMS-API-004 §2.6
# ===========================================================================

class ExportFormat(str, Enum):
    """LMS-API-004 §2.6: format=json|csv"""
    JSON = "json"
    CSV = "csv"


class ExportQueryParams(BaseModel):
    """
    Query parameters for GET /api/v1/logs/export.
    LMS-API-004 §2.6: "Same as GET /logs, plus: format=json|csv"

    Inherits all filter fields from LogQueryParams and adds format.
    Max 10,000 rows per export.
    [GAP-02]: Pagination reuses page/page_size from GET /logs.
    TODO: Evaluate if a cursor-based export or streaming endpoint is needed
          for exports larger than 10,000 rows. LMS-API-004 §2.6 is silent
          on multi-page export mechanics beyond "paginate for more".
    """

    # Inherited from LogQueryParams — duplicated here to keep schemas
    # self-contained and avoid complex inheritance chains in Pydantic v2.
    log_type: LogType = Field(default=LogType.BOTH)
    level: list[LogLevel] | None = Field(default=None)
    source_service: str | None = Field(default=None, max_length=64)
    start_time: datetime | None = Field(default=None)
    end_time: datetime | None = Field(default=None)
    actor_id: str | None = Field(default=None, max_length=128)
    trace_id: str | None = Field(default=None, max_length=64)
    sort: SortOrder = Field(default=SortOrder.DESC)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(
        default=500,
        ge=1,
        le=10000,
        description=(
            "Max rows per export request. "
            "LMS-API-004 §2.6: 'Max rows: 10,000 per export request.'"
        ),
    )

    # Export-specific field.
    format: ExportFormat = Field(
        default=ExportFormat.JSON,
        description="Export file format: json | csv",
    )

    def to_filter_dict(self) -> dict[str, Any]:
        """Returns filter fields as a dict for log_service.export_logs()."""
        return {
            "log_type": self.log_type,
            "level": self.level,
            "source_service": self.source_service,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "actor_id": self.actor_id,
            "trace_id": self.trace_id,
            "sort": self.sort,
            "page": self.page,
            "page_size": self.page_size,
        }
