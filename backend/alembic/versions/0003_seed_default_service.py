# =============================================================================
# filename: alembic/versions/0003_seed_default_service.py
# purpose:  Seed migration — inserts the minimum required service entries
#           into the services registry table.
#           Without at least one registered service, no log producer can
#           ingest logs (source_service validation would reject all requests).
#           Also registers the LMS system itself so the retention job can
#           self-log its execution results (LMS-BRD-001 FR-15).
# implements: LMS-DB-003 §3.1 (services table)
#             LMS-API-004 §2.1 ("source_service Must match a registered services.id")
#             LMS-BRD-001 FR-15 (retention job SHOULD log its own execution)
#             Phase 1 analysis [GAP-01]: No seed data defined in spec documents.
# =============================================================================
# [GAP-01] NOTE: The LMS specification documents define no service registration
# API and no seed data. This migration provides the minimum viable entries.
# TODO: Implement a services management API or admin CLI so operators can
#       register new producer services without running migrations.
#       Candidate endpoint: POST /api/v1/admin/services (LOG_ADMIN role).
# =============================================================================

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None

# Seed timestamp — UTC, consistent across environments.
_NOW = datetime(2025, 6, 11, 0, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)

# ---------------------------------------------------------------------------
# Seed entries.
# Each entry represents a service expected to be present in every LMS
# deployment. Operators should add production services via the TODO admin API.
# ---------------------------------------------------------------------------
_SEED_SERVICES = [
    {
        "id": "lms-system",
        "name": "LMS Internal System",
        "description": (
            "Reserved service ID for LMS-generated log entries. "
            "Used by the retention job (FR-15), health checks, and "
            "internal system events. Do not use this ID from external services."
        ),
        "is_active": 1,
        "created_at": _NOW,
        "updated_at": _NOW,
    },
    {
        "id": "lms-api",
        "name": "LMS API Service",
        "description": (
            "The LMS FastAPI backend itself. Used when the API layer "
            "generates application log entries (e.g. startup, errors)."
        ),
        "is_active": 1,
        "created_at": _NOW,
        "updated_at": _NOW,
    },
    # -------------------------------------------------------------------------
    # TODO: Remove or replace the example entry below before production deploy.
    # This entry exists only to allow developers to test ingestion immediately
    # after running migrations without needing to register a service first.
    # -------------------------------------------------------------------------
    {
        "id": "example-service",
        "name": "Example Service (Dev/Test Only)",
        "description": (
            "Placeholder service for development and integration testing. "
            "Set is_active=0 or delete this row before production deployment."
        ),
        "is_active": 1,
        "created_at": _NOW,
        "updated_at": _NOW,
    },
]


def upgrade() -> None:
    """
    Insert seed service entries.
    Uses INSERT IGNORE to be idempotent — safe to run on a DB that already
    has these entries (e.g. if migration is re-run in CI).
    """
    services_table = sa.table(
        "services",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_active", sa.Integer),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    # INSERT IGNORE: skip silently if the row already exists (idempotent).
    for service in _SEED_SERVICES:
        op.get_bind().execute(
            sa.text(
                "INSERT IGNORE INTO services "
                "(id, name, description, is_active, created_at, updated_at) "
                "VALUES (:id, :name, :description, :is_active, :created_at, :updated_at)"
            ),
            service,
        )


def downgrade() -> None:
    """
    Remove seed entries.
    Only deletes the specific seeded IDs — does not touch operator-added services.
    """
    seed_ids = [s["id"] for s in _SEED_SERVICES]
    bind = op.get_bind()
    for service_id in seed_ids:
        bind.execute(
            sa.text("DELETE FROM services WHERE id = :id"),
            {"id": service_id},
        )
