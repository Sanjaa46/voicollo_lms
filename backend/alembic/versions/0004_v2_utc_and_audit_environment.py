"""v2.0.0 schema changes.

* audit_logs.environment — the API always accepted it but v1 silently dropped it.
* Legacy timezone repair — v1 let MariaDB fill `ingested_at` / services timestamps
  with CURRENT_TIMESTAMP in the server's local zone (Asia/Ulaanbaatar, UTC+8)
  while the API treated them as UTC. Existing rows are shifted back to UTC.
  Set LMS_LEGACY_TZ_OFFSET_HOURS=0 to skip (e.g. if your DB already ran in UTC).
  On a fresh install there are no log rows, so nothing is shifted.
* DATETIME -> DATETIME(3): v1 silently truncated producer milliseconds.
* lms_app loses the unneeded grant on schema_migrations.

(DB user passwords are re-synced on every deploy by `python -m app.cli migrate`.)

Revision ID: 0004
Revises: 0003
"""

import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels = None
depends_on = None

_SHIFTED_COLUMNS = (
    ("application_logs", "ingested_at"),
    ("audit_logs", "ingested_at"),
    ("services", "created_at"),
    ("services", "updated_at"),
)


_MS_COLUMNS = (
    ("application_logs", "created_at"),
    ("application_logs", "ingested_at"),
    ("audit_logs", "event_time"),
    ("audit_logs", "ingested_at"),
    ("services", "created_at"),
    ("services", "updated_at"),
)


def _offset_hours() -> int:
    return int(os.environ.get("LMS_LEGACY_TZ_OFFSET_HOURS", "8"))


def _has_legacy_rows(bind) -> bool:
    for table in ("application_logs", "audit_logs"):
        if bind.execute(sa.text(f"SELECT 1 FROM `{table}` LIMIT 1")).first():
            return True
    return False


def _shift(bind, hours: int) -> None:
    for table, column in _SHIFTED_COLUMNS:
        bind.execute(
            sa.text(
                f"UPDATE `{table}` SET `{column}` = DATE_SUB(`{column}`, INTERVAL :h HOUR)"
            ),
            {"h": hours},
        )


def _try(bind, statement: str) -> None:
    try:
        bind.execute(sa.text(statement))
    except Exception:  # grant may not exist (fresh installs never had it)
        pass


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column(
        "audit_logs",
        sa.Column(
            "environment",
            sa.String(32),
            nullable=True,
            comment="Deployment environment of the producer",
        ),
    )

    # Millisecond precision for every timestamp (v1 columns truncated to seconds).
    for table, column in _MS_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(),
            type_=mysql.DATETIME(fsp=3),
            existing_nullable=False,
        )

    hours = _offset_hours()
    if hours and _has_legacy_rows(bind):
        _shift(bind, hours)

    db_name = bind.execute(sa.text("SELECT DATABASE()")).scalar()
    _try(bind, f"REVOKE ALL PRIVILEGES ON `{db_name}`.`schema_migrations` FROM 'lms_app'@'%'")
    # Services: timestamps are now written by the application in UTC.
    for table, column in (
        ("application_logs", "ingested_at"),
        ("audit_logs", "ingested_at"),
        ("services", "created_at"),
        ("services", "updated_at"),
    ):
        op.alter_column(
            table,
            column,
            existing_type=mysql.DATETIME(fsp=3),
            server_default=sa.text("CURRENT_TIMESTAMP(3)"),
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    hours = _offset_hours()
    if hours:
        _shift(bind, -hours)
    op.drop_column("audit_logs", "environment")
