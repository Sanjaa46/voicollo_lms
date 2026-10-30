from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Enum, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow
from app.models.types import BigIntPK, Timestamp

LOG_LEVELS = ("DEBUG", "INFO", "WARN", "ERROR", "FATAL")


class ApplicationLog(Base):
    """Application / infrastructure logs. Purged after APP_LOG_RETENTION_DAYS by created_at."""

    __tablename__ = "application_logs"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    source_service: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(Enum(*LOG_LEVELS, name="app_log_level"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    context_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_app_service_time", "source_service", "created_at"),
        Index("idx_app_level_time", "level", "created_at"),
        Index("idx_app_created_at", "created_at"),
        Index("idx_app_trace_id", "trace_id"),
    )
