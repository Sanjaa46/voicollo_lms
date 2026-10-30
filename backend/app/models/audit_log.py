from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow
from app.models.types import BigIntPK, Timestamp

ACTOR_TYPES = ("USER", "SERVICE", "SYSTEM")
OUTCOMES = ("SUCCESS", "FAILURE", "PARTIAL")


class AuditLog(Base):
    """Append-only audit trail.

    The application DB user has SELECT/INSERT only; there is no update or delete
    path in the API. Rows are purged after AUDIT_LOG_RETENTION_DAYS by ingested_at.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    source_service: Mapped[str] = mapped_column(String(64), nullable=False)
    environment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_type: Mapped[str] = mapped_column(
        Enum(*ACTOR_TYPES, name="audit_actor_type"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_resource: Mapped[str] = mapped_column(String(256), nullable=False)
    outcome: Mapped[str] = mapped_column(Enum(*OUTCOMES, name="audit_outcome"), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    detail_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    event_time: Mapped[datetime] = mapped_column(Timestamp, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_audit_actor_time", "actor_id", "event_time"),
        Index("idx_audit_service_time", "source_service", "event_time"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_event_time", "event_time"),
        Index("idx_audit_ingested_at", "ingested_at"),
    )
