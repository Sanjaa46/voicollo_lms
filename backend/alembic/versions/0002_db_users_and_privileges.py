# =============================================================================
# filename: alembic/versions/0002_db_users_and_privileges.py
# purpose:  Creates application DB users and grants minimum required
#           privileges as defined in LMS-DB-003 §4 (DB User Privilege Matrix).
#           Two users are created:
#             lms_app       — used by the FastAPI application (SELECT, INSERT)
#             lms_retention — used by the nightly purge job (DELETE only)
#           Passwords are read from environment variables — never hardcoded.
# implements: LMS-DB-003 §4 (DB User Privilege Matrix)
#             LMS-SDD-002 §5.2 (Environment Variables)
#             LMS-BRD-001 §6 (Security — minimum privilege principle)
# =============================================================================


from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None

# ---------------------------------------------------------------------------
# Helper: read passwords from environment.
# Passwords must be set before running migrations.
# These variables are intentionally separate from DATABASE_URL so that
# the migration runner (which connects as a superuser/root) can create
# lower-privilege users.
# ---------------------------------------------------------------------------


def _get_password(attr: str) -> str:
    from app.core.config import DatabaseSettings

    value = getattr(DatabaseSettings(), attr)
    if not value:
        raise RuntimeError(
            f"{attr.upper()} is not set; cannot create the database user without a password."
        )
    return value


def upgrade() -> None:
    """
    Create lms_app and lms_retention MariaDB users and grant
    exact privileges per LMS-DB-003 §4 privilege matrix.

    Privilege matrix (LMS-DB-003 §4):
    ┌────────────────────────────┬────────┬────────┬────────┬────────┬──────┐
    │ Table                      │ SELECT │ INSERT │ UPDATE │ DELETE │ DROP │
    ├────────────────────────────┼────────┼────────┼────────┼────────┼──────┤
    │ services       (lms_app)   │  YES   │  YES   │  YES   │  NO    │  NO  │
    │ application_logs (lms_app) │  YES   │  YES   │  NO    │  NO    │  NO  │
    │ audit_logs     (lms_app)   │  YES   │  YES   │  NO    │  NO    │  NO  │
    │ application_logs (lms_ret) │  NO    │  NO    │  NO    │  YES   │  NO  │
    │ audit_logs     (lms_ret)   │  NO    │  NO    │  NO    │  YES   │  NO  │
    └────────────────────────────┴────────┴────────┴────────┴────────┴──────┘

    NOTE: This migration requires the migration runner to connect as a
    MariaDB user with GRANT OPTION privilege (typically root or a DBA account).
    The DATABASE_URL used by lms-migrate container must be a superuser URL.
    """
    app_password = _get_password("db_app_password")
    retention_password = _get_password("db_retention_password")

    bind = op.get_bind()

    # Determine the current database name dynamically.
    result = bind.execute(sa.text("SELECT DATABASE()"))
    db_name = result.scalar()
    if not db_name:
        raise RuntimeError("Could not determine current database name.")

    # -------------------------------------------------------------------------
    # Create lms_app user
    # -------------------------------------------------------------------------
    bind.execute(sa.text(
        f"CREATE USER IF NOT EXISTS 'lms_app'@'%' "
        f"IDENTIFIED BY :password"
    ), {"password": app_password})

    # services: SELECT, INSERT, UPDATE (no DELETE, no DROP)
    bind.execute(sa.text(
        f"GRANT SELECT, INSERT, UPDATE ON `{db_name}`.`services` TO 'lms_app'@'%'"
    ))

    # application_logs: SELECT, INSERT only
    bind.execute(sa.text(
        f"GRANT SELECT, INSERT ON `{db_name}`.`application_logs` TO 'lms_app'@'%'"
    ))

    # audit_logs: SELECT, INSERT only — no UPDATE, no DELETE (immutability)
    # LMS-DB-003 §3.3: "CRITICAL: This table has no UPDATE or DELETE
    # permissions granted to the application DB user."
    bind.execute(sa.text(
        f"GRANT SELECT, INSERT ON `{db_name}`.`audit_logs` TO 'lms_app'@'%'"
    ))


    # -------------------------------------------------------------------------
    # Create lms_retention user
    # -------------------------------------------------------------------------
    bind.execute(sa.text(
        f"CREATE USER IF NOT EXISTS 'lms_retention'@'%' "
        f"IDENTIFIED BY :password"
    ), {"password": retention_password})

    # application_logs: DELETE only — used by purge job
    bind.execute(sa.text(
        f"GRANT DELETE ON `{db_name}`.`application_logs` TO 'lms_retention'@'%'"
    ))

    # audit_logs: DELETE only — used by purge job (365-day threshold)
    # LMS-DB-003 §4: "Audit log DELETE for lms_retention is intentionally
    # allowed only for rows where event_time is beyond the 365-day threshold.
    # This is enforced by the WHERE clause in the retention job."
    bind.execute(sa.text(
        f"GRANT DELETE ON `{db_name}`.`audit_logs` TO 'lms_retention'@'%'"
    ))

    # Also needs SELECT to verify row counts and support the retention
    # job's self-logging (reads ingested_at for threshold calculation).
    bind.execute(sa.text(
        f"GRANT SELECT ON `{db_name}`.`application_logs` TO 'lms_retention'@'%'"
    ))
    bind.execute(sa.text(
        f"GRANT SELECT ON `{db_name}`.`audit_logs` TO 'lms_retention'@'%'"
    ))

    # Flush privileges to ensure grants take effect immediately.
    bind.execute(sa.text("FLUSH PRIVILEGES"))


def downgrade() -> None:
    """
    Revoke all grants and drop both application DB users.
    Only run in development/test environments.
    """
    bind = op.get_bind()

    result = bind.execute(sa.text("SELECT DATABASE()"))
    db_name = result.scalar()

    if db_name:
        for table in ("services", "application_logs", "audit_logs", "schema_migrations"):
            bind.execute(sa.text(
                f"REVOKE ALL PRIVILEGES ON `{db_name}`.`{table}` "
                f"FROM 'lms_app'@'%'"
            ))
        for table in ("application_logs", "audit_logs"):
            bind.execute(sa.text(
                f"REVOKE ALL PRIVILEGES ON `{db_name}`.`{table}` "
                f"FROM 'lms_retention'@'%'"
            ))

    bind.execute(sa.text("DROP USER IF EXISTS 'lms_app'@'%'"))
    bind.execute(sa.text("DROP USER IF EXISTS 'lms_retention'@'%'"))
    bind.execute(sa.text("FLUSH PRIVILEGES"))
