from pydantic import BaseModel

from app.core.time import UTCDateTime
from app.schemas.logs import AppLogEntry


class TimeBucket(BaseModel):
    start: UTCDateTime
    debug: int = 0
    info: int = 0
    warn: int = 0
    error: int = 0
    fatal: int = 0
    audit: int = 0


class ServiceVolume(BaseModel):
    source_service: str
    app_logs: int
    errors: int
    audit_logs: int


class OverviewResponse(BaseModel):
    window_hours: int
    bucket_seconds: int
    generated_at: UTCDateTime
    totals: dict[str, int]
    levels: dict[str, int]
    outcomes: dict[str, int]
    error_rate: float
    timeline: list[TimeBucket]
    top_services: list[ServiceVolume]
    recent_errors: list[AppLogEntry]
