# =============================================================================
# purpose:  Pydantic v2 schemas for all log ingestion, query, and single-entry
#           endpoints. Field names, types, enums, and constraints match
#           LMS-API-004 and LMS-DB-003 exactly — no invented fields.
# implements: LMS-API-004 §2.1 (POST /logs/app — AppLog request/response)
#             LMS-API-004 §2.2 (POST /logs/app/batch — batch request/response)
#             LMS-API-004 §2.3 (POST /logs/audit — AuditLog request)
#             LMS-API-004 §2.4 (GET /logs — query parameters)
#             LMS-API-004 §2.5 (GET /logs/{log_type}/{id} — single entry)
#             LMS-API-004 §1   (Pagination envelope)
#             LMS-DB-003 §3.2  (application_logs column types)
#             LMS-DB-003 §3.3  (audit_logs column types)
#             LMS-BRD-001 FR-02, FR-03, FR-04, FR-07, FR-08, FR-09
# =============================================================================

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from app.shared.utils.datetime import to_ulaanbaatar

from pydantic import BaseModel, Field, field_validator, model_validator, field_serializer


# ---------------------------------------------------------------------------
# Enums — values must match DB ENUM definitions exactly (LMS-DB-003 §3.2, §3.3)
# ---------------------------------------------------------------------------

class LogLevel(str, Enum):
    """LMS-DB-003 §3.2: ENUM('DEBUG','INFO','WARN','ERROR','FATAL')"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


class ActorType(str, Enum):
    """LMS-DB-003 §3.3: ENUM('USER','SERVICE','SYSTEM')"""
    USER = "USER"
    SERVICE = "SERVICE"
    SYSTEM = "SYSTEM"


class Outcome(str, Enum):
    """LMS-DB-003 §3.3: ENUM('SUCCESS','FAILURE','PARTIAL')"""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    PARTIAL = "PARTIAL"


class LogType(str, Enum):
    """LMS-API-004 §2.4: log_type query parameter"""
    APP = "app"
    AUDIT = "audit"
    BOTH = "both"


class SortOrder(str, Enum):
    """LMS-API-004 §2.4: sort query parameter"""
    ASC = "asc"
    DESC = "desc"


# ===========================================================================
# Application Log Schemas
# LMS-API-004 §2.1
# ===========================================================================

class AppLogRequest(BaseModel):
    """
    Request body for POST /api/v1/logs/app.
    All field names and types match LMS-API-004 §2.1 exactly.
    """
    @field_serializer("created_at", when_used="always")
    def serialize_datetime(self, dt: datetime | None) -> str | None:
        if dt is None:
            return None
        return to_ulaanbaatar(dt).isoformat()

    source_service: str = Field(
        ...,
        max_length=64,
        description="Must match a registered services.id",
        examples=["example-service"],
    )
    level: LogLevel = Field(
        ...,
        description="Log severity level: DEBUG | INFO | WARN | ERROR | FATAL",
    )
    message: str = Field(
        ...,
        max_length=65000,
        description="Log message body. Max 65,000 characters (LMS-API-004 §2.1).",
        min_length=1,
    )
    environment: str = Field(
        ...,
        max_length=32,
        description="Deployment environment, e.g. 'production', 'staging'",
        examples=["production"],
    )
    created_at: datetime = Field(
        ...,
        description="Event timestamp (UTC, ISO 8601). LMS-API-004 §2.1.",
    )
    trace_id: str | None = Field(
        default=None,
        max_length=64,
        description="Distributed trace correlation ID (optional)",
    )
    context_json: dict[str, Any] | None = Field(
        default=None,
        description="Arbitrary key-value metadata (optional)",
    )

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank or whitespace-only")
        return value

    model_config = {
        "json_schema_extra": {
            "example": {
                "source_service": "example-service",
                "level": "ERROR",
                "message": "Unhandled exception in payment processor",
                "environment": "production",
                "created_at": "2025-06-11T06:30:00.000Z",
                "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
                "context_json": {"request_id": "abc-123", "user_id": 42},
            }
        }
    }


class AppLogResponse(BaseModel):
    """
    Response body for POST /api/v1/logs/app (HTTP 201).
    LMS-API-004 §2.1 response fields.
    """
    @field_serializer("ingested_at", when_used="always")
    def serialize_datetime(self, dt: datetime | None) -> str | None:
        if dt is None:
            return None
        return to_ulaanbaatar(dt).isoformat()

    log_id: int = Field(..., description="Assigned log ID (auto-increment PK)")
    ingested_at: datetime = Field(
        ..., description="Server ingestion timestamp (UTC)"
    )

    model_config = {"from_attributes": True}


# ===========================================================================
# Batch Application Log Schemas
# LMS-API-004 §2.2
# ===========================================================================

class BatchAppLogRequest(BaseModel):
    """
    Request body for POST /api/v1/logs/app/batch.
    LMS-API-004 §2.2: "Maximum 100 entries per batch."
    """

    logs: list[AppLogRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of application log entries. Max 100 per batch.",
    )

    @field_validator("logs")
    @classmethod
    def logs_not_empty(cls, value: list) -> list:
        if len(value) == 0:
            raise ValueError("logs array must contain at least one entry")
        return value


class BatchAppLogResult(BaseModel):
    """
    Per-entry result within a batch ingest response.
    LMS-API-004 §2.2: "Returns array of results with per-entry success/failure."
    """

    index: int = Field(..., description="Zero-based index of this entry in the batch")
    success: bool = Field(..., description="Whether this entry was ingested successfully")
    log_id: int | None = Field(
        default=None,
        description="Assigned log ID on success; null on failure",
    )
    error_code: str | None = Field(
        default=None,
        description="Error code on failure; null on success",
    )
    message: str | None = Field(
        default=None,
        description="Error detail on failure; null on success",
    )


class BatchAppLogResponse(BaseModel):
    """
    Response body for POST /api/v1/logs/app/batch (HTTP 207 Multi-Status).
    LMS-API-004 §2.2: "Partial success is allowed (207)."
    """

    results: list[BatchAppLogResult] = Field(
        ..., description="Per-entry ingestion results"
    )
    total: int = Field(..., description="Total entries submitted")
    succeeded: int = Field(..., description="Number of successfully ingested entries")
    failed: int = Field(..., description="Number of failed entries")


# ===========================================================================
# Audit Log Schemas
# LMS-API-004 §2.3
# ===========================================================================

class AuditLogRequest(BaseModel):
    """
    Request body for POST /api/v1/logs/audit.
    Includes all AppLog base fields plus audit-specific required fields.
    LMS-API-004 §2.3: "Additional fields beyond AppLog."
    LMS-BRD-001 FR-03: actor_id, actor_type, action, target_resource, outcome MUST.
    """

    @field_serializer("event_time", when_used="always")
    def serialize_datetime(self, dt: datetime | None) -> str | None:
        if dt is None:
            return None
        return to_ulaanbaatar(dt).isoformat()

    # Base fields shared with AppLog (LMS-API-004 §2.3 inherits from AppLog).
    source_service: str = Field(
        ...,
        max_length=64,
        description="Service that generated the event",
    )
    environment: str = Field(
        ...,
        max_length=32,
        description="Deployment environment",
        examples=["production"],
    )

    # Audit-specific required fields (LMS-API-004 §2.3).
    actor_id: str = Field(
        ...,
        max_length=128,
        description="DAN SSO user ID or service account ID performing the action",
    )
    actor_type: ActorType = Field(
        ...,
        description="Type of actor: USER | SERVICE | SYSTEM",
    )
    action: str = Field(
        ...,
        max_length=128,
        description=(
            "Verb-noun format action descriptor. "
            "Examples: USER_LOGIN, RECORD_DELETE, RECORD_UPDATE"
        ),
        examples=["USER_LOGIN", "RECORD_DELETE"],
    )
    target_resource: str = Field(
        ...,
        max_length=256,
        description="Resource path or identifier affected by the action",
        examples=["/api/users/42", "document:8831"],
    )
    outcome: Outcome = Field(
        ...,
        description="Result of the action: SUCCESS | FAILURE | PARTIAL",
    )
    event_time: datetime = Field(
        ...,
        description="When the action occurred (UTC, ISO 8601). LMS-API-004 §2.3.",
    )

    # Optional audit fields.
    ip_address: str | None = Field(
        default=None,
        max_length=45,
        description="Client IP address (IPv4 or IPv6). VARCHAR(45) per LMS-DB-003 §3.3.",
    )
    detail_json: dict[str, Any] | None = Field(
        default=None,
        description="Old/new values, diff, or additional context (optional)",
    )

    @field_validator("action")
    @classmethod
    def action_format(cls, value: str) -> str:
        """
        Enforce VERB_NOUN format for action strings.
        LMS-API-004 §2.3: "Verb-noun format: USER_LOGIN, RECORD_DELETE"
        """
        stripped = value.strip()
        if not stripped:
            raise ValueError("action must not be blank")
        if " " in stripped:
            raise ValueError(
                "action must use VERB_NOUN format with underscores, not spaces. "
                "Example: USER_LOGIN, not 'user login'"
            )
        return stripped.upper()

    model_config = {
        "json_schema_extra": {
            "example": {
                "source_service": "example-service",
                "environment": "production",
                "actor_id": "user-12345",
                "actor_type": "USER",
                "action": "RECORD_DELETE",
                "target_resource": "/api/v1/records/8831",
                "outcome": "SUCCESS",
                "event_time": "2025-06-11T06:30:00.000Z",
                "ip_address": "192.168.1.100",
                "detail_json": {
                    "record_id": 8831,
                    "deleted_by": "user-12345",
                },
            }
        }
    }


class AuditLogResponse(BaseModel):
    """
    Response body for POST /api/v1/logs/audit (HTTP 201).
    Same shape as AppLogResponse per LMS-API-004 §2.3 (no distinct response spec).
    """

    @field_serializer("ingested_at", when_used="always")
    def serialize_datetime(self, dt: datetime | None) -> str | None:
        if dt is None:
            return None
        return to_ulaanbaatar(dt).isoformat()

    log_id: int = Field(..., description="Assigned audit log ID")
    ingested_at: datetime = Field(
        ..., description="Server ingestion timestamp (UTC)"
    )

    model_config = {"from_attributes": True}


# ===========================================================================
# Query Schemas
# LMS-API-004 §2.4 — GET /logs
# ===========================================================================

class LogQueryParams(BaseModel):
    """
    Query parameters for GET /api/v1/logs.
    All parameter names, types, defaults, and constraints match
    LMS-API-004 §2.4 exactly.

    Used as a Pydantic model (not FastAPI Query() directly) so that
    the cache key builder receives a clean dict with consistent defaults.
    """

    log_type: LogType = Field(
        default=LogType.BOTH,
        description="Filter by log type: app | audit | both",
    )
    level: list[LogLevel] | None = Field(
        default=None,
        description=(
            "Filter by severity level(s). Comma-separated in URL: level=ERROR,FATAL. "
        ),
    )
    source_service: str | None = Field(
        default=None,
        max_length=64,
        description="Exact match on source_service",
    )
    start_time: datetime | None = Field(
        default=None,
        description="Inclusive lower time bound (ISO 8601 UTC)",
    )
    end_time: datetime | None = Field(
        default=None,
        description="Inclusive upper time bound. Defaults to now (LMS-API-004 §2.4).",
    )
    actor_id: str | None = Field(
        default=None,
        max_length=128,
        description="Filter by actor ID. Audit logs only (LMS-API-004 §2.4).",
    )
    trace_id: str | None = Field(
        default=None,
        max_length=64,
        description="Filter by trace ID. App logs only (LMS-API-004 §2.4).",
    )
    sort: SortOrder = Field(
        default=SortOrder.DESC,
        description="Sort order by timestamp: asc | desc",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed). LMS-API-004 §2.4.",
    )
    page_size: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Results per page. Max 500. LMS-API-004 §2.4 + BRD FR-08.",
    )

    @model_validator(mode="after")
    def validate_time_range(self) -> "LogQueryParams":
        """Ensure start_time is before end_time when both are provided."""
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be before end_time")
        return self

    def to_cache_key_dict(self) -> dict[str, Any]:
        """
        Converts params to a dict suitable for build_query_cache_key().
        Serialises datetime to ISO string and enum to value for JSON stability.
        None values are included as null (deterministic).
        """
        return {
            "log_type": self.log_type.value,
            "level": (
                sorted([lv.value for lv in self.level]) if self.level else None
            ),
            "source_service": self.source_service,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "actor_id": self.actor_id,
            "trace_id": self.trace_id,
            "sort": self.sort.value,
            "page": self.page,
            "page_size": self.page_size,
        }


# ===========================================================================
# Unified Log Response
# LMS-API-004 §2.4 — log_type=both returns mixed results
# [AMBIGUITY-04]: Discriminated union with log_type field on each record.
# ===========================================================================

class AppLogEntry(BaseModel):
    """
    Single application log entry as returned in query results.
    All field names match application_logs columns (LMS-DB-003 §3.2).
    """
    @field_serializer("created_at", "ingested_at", when_used="always")
    def serialize_datetime(self, dt: datetime | None) -> str | None:
        if dt is None:
            return None
        return to_ulaanbaatar(dt).isoformat()

    log_type: Literal["app"] = "app"
    id: int
    source_service: str
    level: LogLevel
    message: str
    environment: str
    context_json: dict[str, Any] | None = None
    trace_id: str | None = None
    created_at: datetime
    ingested_at: datetime

    model_config = {"from_attributes": True}


class AuditLogEntry(BaseModel):
    """
    Single audit log entry as returned in query results.
    All field names match audit_logs columns (LMS-DB-003 §3.3).
    """

    @field_serializer("event_time", "ingested_at", when_used="always")
    def serialize_datetime(self, dt: datetime | None) -> str | None:
        if dt is None:
            return None
        return to_ulaanbaatar(dt).isoformat()

    log_type: Literal["audit"] = "audit"
    id: int
    source_service: str
    actor_id: str
    actor_type: ActorType
    action: str
    target_resource: str
    outcome: Outcome
    ip_address: str | None = None
    detail_json: dict[str, Any] | None = None
    event_time: datetime
    ingested_at: datetime

    model_config = {"from_attributes": True}


# [AMBIGUITY-04]: Discriminated union — the log_type field on each entry
# allows clients to determine the schema of each record in a mixed result set.
# TODO: Document this unified response format in LMS-API-004 (gap in spec).
UnifiedLogEntry = AppLogEntry | AuditLogEntry


class PaginatedLogsResponse(BaseModel):
    """
    Paginated response envelope for GET /api/v1/logs.
    LMS-API-004 §1: "All list endpoints return: { data, total, page,
    page_size, has_next }"
    """

    data: list[UnifiedLogEntry] = Field(
        ..., description="Log entries for this page"
    )
    total: int = Field(
        ..., description="Total number of matching log entries across all pages"
    )
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of entries per page")
    has_next: bool = Field(
        ..., description="Whether there are more pages after this one"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "data": [
                    {
                        "log_type": "app",
                        "id": 1001,
                        "source_service": "example-service",
                        "level": "ERROR",
                        "message": "Database connection timeout",
                        "environment": "production",
                        "context_json": None,
                        "trace_id": None,
                        "created_at": "2025-06-11T06:30:00.000Z",
                        "ingested_at": "2025-06-11T06:30:00.123Z",
                    }
                ],
                "total": 2847,
                "page": 1,
                "page_size": 50,
                "has_next": True,
            }
        }
    }
