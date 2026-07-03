# =============================================================================
# purpose:  SQLAlchemy ORM model for the `services` table.
#           The services table is the authoritative registry of all log
#           producers. source_service on every log entry is a soft FK
#           validated at the application layer against this table.
# implements: LMS-DB-003 §3.1 (services table DDL)
#             LMS-DB-003 §2 (Entity Relationship Overview)
#             LMS-API-004 §2.1 ("Must match a registered services.id")
# =============================================================================

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Service(Base):
    """
    Registry of services authorised to produce logs.

    Column notes (LMS-DB-003 §3.1):
      id          — VARCHAR(64) PK. Slug-style, e.g. 'xyp-backend'.
      name        — VARCHAR(128). Human-readable display name.
      description — TEXT, nullable. Optional description.
      is_active   — TINYINT(1), default 1. Soft-disable without deleting.
      created_at  — DATETIME(3), server default CURRENT_TIMESTAMP(3).
      updated_at  — DATETIME(3), ON UPDATE CURRENT_TIMESTAMP(3).

    The application DB user (lms_app) has SELECT, INSERT, UPDATE on this
    table but no DELETE. LMS-DB-003 §4.
    """

    __tablename__ = "services"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="Slug-style service identifier, e.g. 'xyp-backend'",
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Human-readable service name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional service description",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
        comment="Soft-disable flag. Inactive services are rejected on ingestion.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),  # Stored as UTC; no TZ offset in MariaDB DATETIME.
        nullable=False,
        server_default=func.current_timestamp(3),
        comment="Record creation timestamp (UTC)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(3),
        onupdate=func.current_timestamp(3),
        comment="Record last-update timestamp (UTC)",
    )

    def __repr__(self) -> str:
        return (
            f"<Service id={self.id!r} name={self.name!r} "
            f"is_active={self.is_active}>"
        )
