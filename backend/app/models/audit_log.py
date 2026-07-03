# =============================================================================
# purpose:  SQLAlchemy ORM model for the `audit_logs` table.
#           CRITICAL: This table is append-only and immutable.
#           - No UPDATE or DELETE permissions are granted to lms_app DB user.
#           - No DELETE route exists in the API layer.
#           - Immutability is enforced at three independent layers:
#               1. DB user privileges (LMS-DB-003 §4)
#               2. No API DELETE route (LMS-BRD-001 FR-14, LMS-SDD-002 §6)
#               3. This model has no update() helper methods by design.
# implements: LMS-DB-003 §3.3 (audit_logs DDL and indexes)
#             LMS-BRD-001 FR-03, FR-14 (audit requirements, immutability)
#             LMS-API-004 §2.3 (AuditLog request fields)
# =============================================================================

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Enum,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import BIGINT as MySQLBigInt
from app.core.database import Base


class AuditLog(Base):
    """
    Append-only compliance audit trail for user and system actions.

    IMMUTABILITY CONTRACT:
      - The lms_app DB user has SELECT and INSERT only on this table.
      - The lms_retention user has DELETE only (for rows beyond 365-day threshold).
      - No Python method on this model performs UPDATE or DELETE.
      - LMS-BRD-001 FR-14: "Audit logs MUST NOT be deletable via any
        public API endpoint. No DELETE route exists for audit logs."

    Column notes (LMS-DB-003 §3.3):
      id              — BIGINT UNSIGNED AUTO_INCREMENT PK.
      source_service  — VARCHAR(64). Service generating the event.
      actor_id        — VARCHAR(128). DAN SSO user ID or service account.
      actor_type      — ENUM('USER','SERVICE','SYSTEM').
      action          — VARCHAR(128). Verb-noun: USER_LOGIN, RECORD_DELETE.
      target_resource — VARCHAR(256). Resource path or identifier affected.
      outcome         — ENUM('SUCCESS','FAILURE','PARTIAL').
      ip_address      — VARCHAR(45), nullable. Supports IPv6 (45 chars).
      detail_json     — JSON, nullable. Diff, old/new values, request context.
      event_time      — DATETIME(3). When the action occurred (UTC).
      ingested_at     — DATETIME(3). Server receive time. Server default.

    Retention: deleted by lms_retention user when
      ingested_at < NOW() - 365 days.
    [CONFLICT-01 resolved]: Using ingested_at, NOT event_time.
    LMS-BRD-001 FR-13. LMS-SDD-002 §3.5.

    Indexes (LMS-DB-003 §3.3):
      idx_audit_actor_time    (actor_id, event_time DESC) — query by actor
      idx_audit_service_time  (source_service, event_time DESC) — query by service
      idx_audit_action        (action) — filter by action type
      idx_audit_event_time    (event_time) — retention job + time range queries
    """

    __tablename__ = "audit_logs"

    # ENUM values must exactly match LMS-DB-003 §3.3 and LMS-API-004 §2.3.
    ACTOR_TYPE_ENUM = Enum(
        "USER", "SERVICE", "SYSTEM",
        name="audit_actor_type",
        create_constraint=True,
    )
    OUTCOME_ENUM = Enum(
        "SUCCESS", "FAILURE", "PARTIAL",
        name="audit_outcome",
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
        comment="Service that generated the audit event. Soft FK to services.id.",
    )
    actor_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="DAN SSO user ID or service account ID performing the action",
    )
    actor_type: Mapped[str] = mapped_column(
        ACTOR_TYPE_ENUM,
        nullable=False,
        comment="Type of actor: USER | SERVICE | SYSTEM",
    )
    action: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Verb-noun action descriptor, e.g. USER_LOGIN, RECORD_DELETE",
    )
    target_resource: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Resource path or identifier affected by the action",
    )
    outcome: Mapped[str] = mapped_column(
        OUTCOME_ENUM,
        nullable=False,
        comment="Result of the action: SUCCESS | FAILURE | PARTIAL",
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),  # 45 chars accommodates full IPv6 with zone ID.
        nullable=True,
        comment="Client IP address. VARCHAR(45) supports IPv6.",
    )
    detail_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Diff, old/new values, or additional request context",
    )
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        comment="Timestamp when the action occurred (UTC). Set by the producer.",
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(3),
        comment=(
            "Server receive timestamp (UTC). Set automatically on INSERT. "
            "Used as retention boundary. [CONFLICT-01 resolved]"
        ),
    )

    # -------------------------------------------------------------------------
    # Composite indexes — names and columns match LMS-DB-003 §3.3 exactly.
    # -------------------------------------------------------------------------
    __table_args__ = (
        Index(
            "idx_audit_actor_time",
            "actor_id",
            "event_time",
            info={"description": "Query by actor across a time range (LMS-API-004 §2.4 actor_id filter)"},
        ),
        Index(
            "idx_audit_service_time",
            "source_service",
            "event_time",
            info={"description": "Query by source service across a time range"},
        ),
        Index(
            "idx_audit_action",
            "action",
            info={"description": "Filter by action type (e.g. all USER_LOGIN events)"},
        ),
        Index(
            "idx_audit_event_time",
            "event_time",
            info={"description": "Time range queries and retention job. Note: retention job uses ingested_at, not event_time. This index also supports event_time range queries from the API."},
        ),
        # Additional index for retention job — ingested_at is the actual
        # retention boundary column per [CONFLICT-01 resolution].
        # LMS-DB-003 §3.3 does not define this index explicitly, but it is
        # required for efficient retention DELETEs.
        # Assumption: adding idx_audit_ingested_at as a gap-fill.
        # TODO: Confirm with DB team whether this index should be added to
        #       the formal schema document (LMS-DB-003).
        Index(
            "idx_audit_ingested_at",
            "ingested_at",
            info={"description": "Retention job DELETE index — deletes by ingested_at threshold. Gap-fill index not in original LMS-DB-003 spec."},
        ),
        {
            "comment": (
                "Audit log table. Append-only, immutable. "
                "lms_app user: SELECT + INSERT only. "
                "Retention: 365 days by ingested_at (LMS-BRD-001 FR-13)."
            )
        },
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} action={self.action!r} "
            f"actor_id={self.actor_id!r} outcome={self.outcome!r} "
            f"event_time={self.event_time}>"
        )
