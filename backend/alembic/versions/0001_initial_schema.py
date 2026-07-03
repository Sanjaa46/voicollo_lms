# =============================================================================
# filename: alembic/versions/0001_initial_schema.py
# purpose:  Initial database schema migration.
#           Creates all four tables defined in LMS-DB-003:
#             - schema_migrations (managed by Alembic — exists implicitly)
#             - services
#             - application_logs
#             - audit_logs
#           All column types, nullability, defaults, ENUMs, and indexes
#           match LMS-DB-003 §3 exactly.
# implements: LMS-DB-003 §3.1 (services)
#             LMS-DB-003 §3.2 (application_logs)
#             LMS-DB-003 §3.3 (audit_logs)
#             LMS-DB-003 §5   (Migration Strategy)
# =============================================================================

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# Alembic revision identifiers.
revision: str = "0001"
down_revision: str | None = None  # This is the base migration.
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """
    Create the full initial schema.
    All DDL matches LMS-DB-003 §3 column-for-column.
    """

    # -------------------------------------------------------------------------
    # Table: services
    # LMS-DB-003 §3.1
    # -------------------------------------------------------------------------
    op.create_table(
        "services",
        sa.Column(
            "id",
            sa.String(64),
            primary_key=True,
            nullable=False,
            comment="Slug-style service identifier, e.g. 'xyp-backend'",
        ),
        sa.Column(
            "name",
            sa.String(128),
            nullable=False,
            comment="Human-readable service name",
        ),
        sa.Column(
            "description",
            sa.Text,
            nullable=True,
            comment="Optional service description",
        ),
        sa.Column(
            "is_active",
            mysql.TINYINT(1),
            nullable=False,
            server_default="1",
            comment="Soft-disable flag. 1=active, 0=disabled.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(3)"),
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"),
            comment="Record last-update timestamp (UTC)",
        ),
        comment="Registry of services authorised to produce logs.",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -------------------------------------------------------------------------
    # Table: application_logs
    # LMS-DB-003 §3.2
    # -------------------------------------------------------------------------
    op.create_table(
        "application_logs",
        sa.Column(
            "id",
            mysql.BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            nullable=False,
            comment="Auto-increment primary key",
        ),
        sa.Column(
            "source_service",
            sa.String(64),
            nullable=False,
            comment="Soft FK to services.id — validated at application layer",
        ),
        sa.Column(
            "level",
            sa.Enum("DEBUG", "INFO", "WARN", "ERROR", "FATAL", name="app_log_level"),
            nullable=False,
            comment="Log severity level",
        ),
        sa.Column(
            "message",
            sa.Text,
            nullable=False,
            comment="Log message body. Max 65,535 chars.",
        ),
        sa.Column(
            "environment",
            sa.String(32),
            nullable=False,
            comment="Deployment environment: production | staging | development",
        ),
        sa.Column(
            "context_json",
            mysql.JSON,
            nullable=True,
            comment="Optional structured metadata",
        ),
        sa.Column(
            "trace_id",
            sa.String(64),
            nullable=True,
            comment="Distributed trace correlation ID",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            comment="Log event timestamp (UTC). Set by the producer.",
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(3)"),
            comment="Server receive timestamp (UTC).",
        ),
        comment=(
            "General-purpose application log table. "
            "Retention: 90 days by created_at (LMS-BRD-001 FR-12)."
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # Indexes for application_logs — LMS-DB-003 §3.2
    op.create_index(
        "idx_app_service_time",
        "application_logs",
        ["source_service", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_app_level_time",
        "application_logs",
        ["level", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_app_created_at",
        "application_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "idx_app_trace_id",
        "application_logs",
        ["trace_id"],
        unique=False,
    )

    # -------------------------------------------------------------------------
    # Table: audit_logs
    # LMS-DB-003 §3.3
    # CRITICAL: This table is append-only. No UPDATE or DELETE permissions
    # are granted to lms_app. Immutability enforced at DB user level.
    # -------------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            mysql.BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            nullable=False,
            comment="Auto-increment primary key",
        ),
        sa.Column(
            "source_service",
            sa.String(64),
            nullable=False,
            comment="Service that generated the audit event",
        ),
        sa.Column(
            "actor_id",
            sa.String(128),
            nullable=False,
            comment="DAN SSO user ID or service account ID",
        ),
        sa.Column(
            "actor_type",
            sa.Enum("USER", "SERVICE", "SYSTEM", name="audit_actor_type"),
            nullable=False,
            comment="Type of actor",
        ),
        sa.Column(
            "action",
            sa.String(128),
            nullable=False,
            comment="Verb-noun action descriptor, e.g. USER_LOGIN",
        ),
        sa.Column(
            "target_resource",
            sa.String(256),
            nullable=False,
            comment="Resource path or identifier affected",
        ),
        sa.Column(
            "outcome",
            sa.Enum("SUCCESS", "FAILURE", "PARTIAL", name="audit_outcome"),
            nullable=False,
            comment="Result of the action",
        ),
        sa.Column(
            "ip_address",
            sa.String(45),  # VARCHAR(45) supports full IPv6 with zone ID.
            nullable=True,
            comment="Client IP address (IPv4 or IPv6)",
        ),
        sa.Column(
            "detail_json",
            mysql.JSON,
            nullable=True,
            comment="Diff, old/new values, or request context",
        ),
        sa.Column(
            "event_time",
            sa.DateTime(timezone=False),
            nullable=False,
            comment="When the action occurred (UTC). Set by the producer.",
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(3)"),
            comment=(
                "Server receive timestamp (UTC). "
                "Retention boundary column. [CONFLICT-01 resolved]"
            ),
        ),
        comment=(
            "Compliance audit trail. Append-only, immutable. "
            "lms_app user: SELECT + INSERT only. "
            "Retention: 365 days by ingested_at (LMS-BRD-001 FR-13)."
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # Indexes for audit_logs — LMS-DB-003 §3.3
    op.create_index(
        "idx_audit_actor_time",
        "audit_logs",
        ["actor_id", "event_time"],
        unique=False,
    )
    op.create_index(
        "idx_audit_service_time",
        "audit_logs",
        ["source_service", "event_time"],
        unique=False,
    )
    op.create_index(
        "idx_audit_action",
        "audit_logs",
        ["action"],
        unique=False,
    )
    op.create_index(
        "idx_audit_event_time",
        "audit_logs",
        ["event_time"],
        unique=False,
    )
    # Gap-fill index for ingested_at — required for efficient retention DELETEs.
    # [CONFLICT-01 resolved]: retention job uses ingested_at, not event_time.
    # TODO: Add idx_audit_ingested_at to LMS-DB-003 §3.3 formally.
    op.create_index(
        "idx_audit_ingested_at",
        "audit_logs",
        ["ingested_at"],
        unique=False,
    )


def downgrade() -> None:
    """
    Drop all tables in reverse dependency order.
    WARNING: This destroys all log data. Only run in development/test.
    LMS-BRD-001: Audit logs are immutable in production — downgrade is
    disabled in production by convention; enforce via deployment policy.
    """
    # Drop indexes before tables (MariaDB drops them with the table,
    # but explicit drops make the migration reversible cleanly).
    op.drop_index("idx_audit_ingested_at", table_name="audit_logs")
    op.drop_index("idx_audit_event_time", table_name="audit_logs")
    op.drop_index("idx_audit_action", table_name="audit_logs")
    op.drop_index("idx_audit_service_time", table_name="audit_logs")
    op.drop_index("idx_audit_actor_time", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("idx_app_trace_id", table_name="application_logs")
    op.drop_index("idx_app_created_at", table_name="application_logs")
    op.drop_index("idx_app_level_time", table_name="application_logs")
    op.drop_index("idx_app_service_time", table_name="application_logs")
    op.drop_table("application_logs")

    op.drop_table("services")

    # Drop ENUM types (required for PostgreSQL; harmless on MariaDB).
    sa.Enum(name="app_log_level").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="audit_actor_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="audit_outcome").drop(op.get_bind(), checkfirst=True)
