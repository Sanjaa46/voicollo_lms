# =============================================================================
# purpose:  SQLAlchemy ORM model for the `application_logs` table.
#           General-purpose time-series log storage for all internal services.
#           This table supports INSERT and SELECT only for the lms_app user.
#           No UPDATE or DELETE via the application layer.
# implements: LMS-DB-003 §3.2 (application_logs DDL and indexes)
#             LMS-BRD-001 FR-01, FR-02 (log ingestion requirements)
#             LMS-API-004 §2.1 (AppLog request fields)
# =============================================================================

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Enum,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import BIGINT as MySQLBigInt
from app.core.database import Base


class ApplicationLog(Base):
    """
    Time-series table for application and infrastructure logs.

    Column notes (LMS-DB-003 §3.2):
      id             — BIGINT UNSIGNED AUTO_INCREMENT PK.
      source_service — VARCHAR(64). Soft-ref to services.id.
      level          — ENUM('DEBUG','INFO','WARN','ERROR','FATAL').
      message        — TEXT. Max 65,535 chars (LMS-API-004 §2.1: 65,000).
      environment    — VARCHAR(32). e.g. 'production', 'staging'.
      context_json   — JSON, nullable. Arbitrary key-value metadata.
      trace_id       — VARCHAR(64), nullable. Distributed trace correlation.
      created_at     — DATETIME(3). Log event timestamp (UTC). Indexed.
      ingested_at    — DATETIME(3). Server receive time. Server default.

    Indexes (LMS-DB-003 §3.2):
      idx_app_service_time  (source_service, created_at DESC) — primary query pattern
      idx_app_level_time    (level, created_at DESC)          — filter by level
      idx_app_created_at    (created_at)                      — retention job DELETE
      idx_app_trace_id      (trace_id)                        — trace correlation

    Retention: deleted by lms_retention user when created_at < NOW() - 90 days.
    LMS-BRD-001 FR-12. LMS-SDD-002 §3.5.
    """

    __tablename__ = "application_logs"

    # ENUM values must exactly match LMS-DB-003 §3.2 and LMS-API-004 §2.1.
    LEVEL_ENUM = Enum(
        "DEBUG", "INFO", "WARN", "ERROR", "FATAL",
        name="app_log_level",
        create_constraint=True,
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(MySQLBigInt(unsigned=True), "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="Auto-increment primary key",
    )
    source_service: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=False,  # Covered by composite index idx_app_service_time.
        comment="Soft FK to services.id — validated at application layer",
    )
    level: Mapped[str] = mapped_column(
        LEVEL_ENUM,
        nullable=False,
        comment="Log severity: DEBUG | INFO | WARN | ERROR | FATAL",
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Log message body. Max 65,535 chars (TEXT column limit).",
    )
    environment: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Deployment environment: production | staging | development",
    )
    context_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Optional structured metadata (request_id, user_id, etc.)",
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Distributed trace ID for cross-service correlation",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        comment="Log event timestamp (UTC). Set by the producer.",
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(3),
        comment="Server receive timestamp (UTC). Set automatically on INSERT.",
    )

    # -------------------------------------------------------------------------
    # Composite indexes — defined as __table_args__ per SQLAlchemy convention.
    # Names and column order match LMS-DB-003 §3.2 exactly.
    # -------------------------------------------------------------------------
    __table_args__ = (
        Index(
            "idx_app_service_time",
            "source_service",
            # DESC sort expressed via text() is not supported in all dialects
            # for Index definitions; MariaDB/InnoDB will use the index for both
            # ASC and DESC scans. The index name matches the spec.
            "created_at",
            info={"description": "Primary query pattern: filter by service + time range"},
        ),
        Index(
            "idx_app_level_time",
            "level",
            "created_at",
            info={"description": "Filter by log level within a time range"},
        ),
        Index(
            "idx_app_created_at",
            "created_at",
            info={"description": "Retention job DELETE — scans by created_at threshold"},
        ),
        Index(
            "idx_app_trace_id",
            "trace_id",
            info={"description": "Trace correlation lookups"},
        ),
        {
            "comment": (
                "Application logs table. "
                "Retention: 90 days by created_at (LMS-BRD-001 FR-12)."
            )
        },
    )

    def __repr__(self) -> str:
        return (
            f"<ApplicationLog id={self.id} level={self.level!r} "
            f"service={self.source_service!r} created_at={self.created_at}>"
        )
