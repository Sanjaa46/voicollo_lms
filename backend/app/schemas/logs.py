import ipaddress
import json
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, computed_field, field_validator

from app.core.config import get_settings
from app.core.time import UTCDateTime, as_aware_utc, utcnow

MAX_JSON_BYTES = 64 * 1024


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


class ActorType(StrEnum):
    USER = "USER"
    SERVICE = "SERVICE"
    SYSTEM = "SYSTEM"


class Outcome(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    PARTIAL = "PARTIAL"


class LogType(StrEnum):
    APP = "app"
    AUDIT = "audit"
    BOTH = "both"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


_LEVEL_ALIASES = {"WARNING": "WARN", "CRITICAL": "FATAL", "ERR": "ERROR", "TRACE": "DEBUG"}


def _check_not_future(value: datetime) -> datetime:
    limit = timedelta(minutes=get_settings().max_future_skew_minutes)
    if as_aware_utc(value).replace(tzinfo=None) - utcnow() > limit:
        raise ValueError("timestamp is too far in the future (check the producer clock)")
    return value


def _check_json_size(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is not None and len(json.dumps(value, default=str)) > MAX_JSON_BYTES:
        raise ValueError(f"must serialise to at most {MAX_JSON_BYTES} bytes")
    return value


Slug = Annotated[str, Field(min_length=1, max_length=64)]


# ======================================================================= ingest
class AppLogRequest(BaseModel):
    source_service: Slug = Field(examples=["billing-api"])
    level: LogLevel
    message: str = Field(min_length=1, max_length=65_000)
    environment: str = Field(min_length=1, max_length=32, examples=["production"])
    created_at: datetime = Field(description="Event time. ISO-8601; offset-less = UTC.")
    trace_id: str | None = Field(default=None, max_length=64)
    context_json: dict[str, Any] | None = None

    @field_validator("source_service", "environment", mode="before")
    @classmethod
    def _strip(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("level", mode="before")
    @classmethod
    def _normalise_level(cls, value: Any) -> Any:
        if isinstance(value, str):
            upper = value.strip().upper()
            return _LEVEL_ALIASES.get(upper, upper)
        return value

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value

    @field_validator("trace_id", mode="before")
    @classmethod
    def _empty_trace_is_none(cls, value: Any) -> Any:
        return None if isinstance(value, str) and not value.strip() else value

    _future = field_validator("created_at")(_check_not_future)
    _ctx_size = field_validator("context_json")(_check_json_size)


class AuditLogRequest(BaseModel):
    source_service: Slug
    environment: str = Field(min_length=1, max_length=32)
    actor_id: str = Field(min_length=1, max_length=128)
    actor_type: ActorType
    action: str = Field(min_length=1, max_length=128, examples=["RECORD_DELETE"])
    target_resource: str = Field(min_length=1, max_length=256, examples=["/api/records/42"])
    outcome: Outcome
    event_time: datetime
    ip_address: str | None = Field(default=None, max_length=45)
    detail_json: dict[str, Any] | None = None

    @field_validator("source_service", "environment", "actor_id", "target_resource", mode="before")
    @classmethod
    def _strip(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("actor_type", "outcome", mode="before")
    @classmethod
    def _upper(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("action")
    @classmethod
    def _verb_noun(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ch.isspace() for ch in value):
            raise ValueError("action must be VERB_NOUN without spaces, e.g. USER_LOGIN")
        return value.upper()

    @field_validator("ip_address", mode="before")
    @classmethod
    def _valid_ip(cls, value: Any) -> Any:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        try:
            return str(ipaddress.ip_address(str(value).strip()))
        except ValueError as exc:
            raise ValueError("ip_address must be a valid IPv4 or IPv6 address") from exc

    _future = field_validator("event_time")(_check_not_future)
    _detail_size = field_validator("detail_json")(_check_json_size)


class IngestResponse(BaseModel):
    log_id: int
    ingested_at: UTCDateTime


AppLogResponse = IngestResponse
AuditLogResponse = IngestResponse


class BatchAppLogRequest(BaseModel):
    """Entries are validated one by one so a single bad entry cannot reject the batch."""

    logs: list[dict[str, Any]] = Field(min_length=1, max_length=100)


class BatchAppLogResult(BaseModel):
    index: int
    success: bool
    log_id: int | None = None
    error_code: str | None = None
    message: str | None = None


class BatchAppLogResponse(BaseModel):
    results: list[BatchAppLogResult]
    total: int
    succeeded: int
    failed: int


# ======================================================================= query
class LogFilters(BaseModel):
    """Filters shared by query, export and stats endpoints."""

    log_type: LogType = LogType.BOTH
    level: list[LogLevel] | None = Field(default=None, description="App logs only.")
    outcome: list[Outcome] | None = Field(default=None, description="Audit logs only.")
    source_service: list[str] | None = Field(default=None)
    environment: str | None = Field(default=None, max_length=32)
    start_time: datetime | None = None
    end_time: datetime | None = None
    trace_id: str | None = Field(default=None, max_length=64, description="App logs only.")
    actor_id: str | None = Field(default=None, max_length=128, description="Audit logs only.")
    action: str | None = Field(default=None, max_length=128, description="Audit logs only.")
    q: str | None = Field(
        default=None,
        max_length=200,
        description="Substring search in message (app) or action/target/actor (audit).",
    )
    sort: SortOrder = SortOrder.DESC

    @field_validator("level", "outcome", "source_service", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> Any:
        # Accept both ?level=ERROR&level=FATAL and ?level=ERROR,FATAL
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            items = [part.strip() for raw in value for part in str(raw).split(",")]
            items = [item for item in items if item]
            return items or None
        return value

    @field_validator("level", mode="before")
    @classmethod
    def _level_aliases(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [_LEVEL_ALIASES.get(v.upper(), v.upper()) for v in value]
        return value

    @field_validator("environment", "trace_id", "actor_id", "action", "q", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("end_time")
    @classmethod
    def _range(cls, value: datetime | None, info) -> datetime | None:
        start = info.data.get("start_time")
        if value and start and as_aware_utc(start) > as_aware_utc(value):
            raise ValueError("end_time must not be before start_time")
        return value


class LogQueryParams(LogFilters):
    page: int = Field(default=1, ge=1, le=100_000)
    page_size: int = Field(default=50, ge=1, le=500)


class ExportParams(LogFilters):
    format: Literal["json", "csv"] = "json"
    limit: int = Field(default=1000, ge=1, le=10_000)


class AppLogEntry(BaseModel):
    log_type: Literal["app"] = "app"
    id: int
    source_service: str
    level: LogLevel
    message: str
    environment: str
    context_json: dict[str, Any] | None = None
    trace_id: str | None = None
    created_at: UTCDateTime
    ingested_at: UTCDateTime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def timestamp(self) -> UTCDateTime:
        return self.created_at


class AuditLogEntry(BaseModel):
    log_type: Literal["audit"] = "audit"
    id: int
    source_service: str
    environment: str | None = None
    actor_id: str
    actor_type: ActorType
    action: str
    target_resource: str
    outcome: Outcome
    ip_address: str | None = None
    detail_json: dict[str, Any] | None = None
    event_time: UTCDateTime
    ingested_at: UTCDateTime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def timestamp(self) -> UTCDateTime:
        return self.event_time


LogEntry = Annotated[AppLogEntry | AuditLogEntry, Field(discriminator="log_type")]


class PaginatedLogsResponse(BaseModel):
    data: list[LogEntry]
    total: int
    page: int
    page_size: int
    has_next: bool
