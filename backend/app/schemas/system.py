from typing import Literal

from pydantic import BaseModel, Field

from app.core.time import UTCDateTime


class DependencyStatus(BaseModel):
    status: Literal["ok", "error"]
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    version: str
    uptime_seconds: float
    database: DependencyStatus
    cache: DependencyStatus


class VersionResponse(BaseModel):
    version: str
    git_sha: str
    build_date: str
    environment: str


class RetentionRun(BaseModel):
    status: Literal["SUCCESS", "FAILURE"]
    started_at: UTCDateTime
    duration_seconds: float
    deleted_app_logs: int
    deleted_audit_logs: int
    trigger: Literal["schedule", "manual"]
    error: str | None = None


class RetentionPolicy(BaseModel):
    enabled: bool
    app_log_retention_days: int
    audit_log_retention_days: int
    schedule: str = Field(description="Daily run time, HH:MM in the scheduler timezone.")
    timezone: str
    next_run_at: UTCDateTime | None = None


class RetentionStatus(BaseModel):
    policy: RetentionPolicy
    last_run: RetentionRun | None = None
    running: bool = False


class MetricsResponse(BaseModel):
    ingestion_total: int
    query_total: int
    cache_hits: int
    cache_misses: int
    cache_hit_ratio: float = Field(ge=0, le=1)
    error_total: dict[str, int]
    since: UTCDateTime | None = Field(
        default=None, description="When the counters were first written."
    )


class SystemStatus(BaseModel):
    health: HealthResponse
    version: VersionResponse
    metrics: MetricsResponse
    retention: RetentionStatus
    rate_limit_per_minute: int
    signature_tolerance_seconds: int
