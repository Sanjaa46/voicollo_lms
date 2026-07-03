# =============================================================================
# purpose:  Nightly log retention purge job.
#           Deletes application logs older than APP_LOG_RETENTION_DAYS
#           (by created_at) and audit logs older than AUDIT_LOG_RETENTION_DAYS
#           (by ingested_at). Runs via APScheduler at 02:00 Asia/Ulaanbaatar.
#
#           Post-run actions (LMS-SDD-002 §3.5):
#             1. Writes a summary application log entry (BRD FR-15).
#             2. Flushes all lms:query:* cache keys (CACHE-005 §5).
#             3. Stores retention metadata in Redis for /metrics endpoint.
#
#           Safety guarantees:
#             - Uses lms_retention DB user (DELETE only — no SELECT on other tables).
#             - WHERE clause enforces the day threshold — cannot delete newer rows.
#             - Errors are caught and written as ERROR-level app logs.
#             - Job failure does NOT crash the server (LMS-SDD-002 §3.5).
#
# implements: LMS-SDD-002 §3.5  (Retention Job)
#             LMS-BRD-001 FR-12 (app logs: 90 days by created_at)
#             LMS-BRD-001 FR-13 (audit logs: 365 days by ingested_at)
#             LMS-BRD-001 FR-14 (audit logs NOT deletable via public API)
#             LMS-BRD-001 FR-15 (job SHOULD log its own execution result)
#             LMS-CACHE-005 §5  (flush all lms:query:* on retention complete)
#             LMS-DB-003  §4    (lms_retention user for DELETE operations)
# =============================================================================

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_retention_db
from app.core.redis_client import get_redis_client
from app.models.application_log import ApplicationLog
from app.models.audit_log import AuditLog
from app.services.cache_service import invalidate_all_query_cache
from app.services.metrics_service import record_retention_run

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reserved source_service ID for LMS-generated log entries.
# Seeded in migration 0003. LMS-SDD-002 §3.5 + BRD FR-15.
# ---------------------------------------------------------------------------
LMS_SYSTEM_SERVICE_ID = "lms-system"
LMS_SYSTEM_ENVIRONMENT = "production"


async def run_retention_job() -> None:
    """
    Entry point for the nightly retention purge job.
    Called by APScheduler (app/jobs/scheduler.py).

    Execution order:
      1. Calculate deletion thresholds from config.
      2. Delete expired application_logs (by created_at).
      3. Delete expired audit_logs (by ingested_at).
      4. Flush all query cache keys.
      5. Write summary application log entry (self-logging).
      6. Store retention metadata in Redis for /metrics.

    All steps are wrapped in try/except — a failure in any step is logged
    as an ERROR-level app log but does NOT raise or crash the server.
    LMS-SDD-002 §3.5: "Job errors are caught and written as ERROR-level
    application logs. They do NOT crash the server."
    """
    settings = get_settings()
    run_start = datetime.now(timezone.utc)

    logger.info(
        "Retention job started at %s (app_retention=%dd, audit_retention=%dd)",
        run_start.isoformat(),
        settings.app_log_retention_days,
        settings.audit_log_retention_days,
    )

    deleted_app = 0
    deleted_audit = 0
    job_status = "SUCCESS"
    error_detail: str | None = None

    try:
        # -----------------------------------------------------------------
        # Step 1: Calculate thresholds.
        # -----------------------------------------------------------------
        app_threshold = _calculate_threshold(settings.app_log_retention_days)
        audit_threshold = _calculate_threshold(settings.audit_log_retention_days)

        logger.debug(
            "Thresholds — app_logs.created_at < %s | audit_logs.ingested_at < %s",
            app_threshold.isoformat(),
            audit_threshold.isoformat(),
        )

        # -----------------------------------------------------------------
        # Step 2 & 3: Execute deletions using lms_retention DB user.
        # LMS-DB-003 §4: lms_retention has DELETE on both log tables.
        # -----------------------------------------------------------------
        async with get_retention_db() as retention_session:
            deleted_app = await _delete_app_logs(retention_session, app_threshold)
            deleted_audit = await _delete_audit_logs(retention_session, audit_threshold)

        logger.info(
            "Retention deletions complete: app_logs=%d, audit_logs=%d",
            deleted_app,
            deleted_audit,
        )

    except Exception as exc:
        job_status = "FAILURE"
        error_detail = str(exc)
        logger.error(
            "Retention job failed during deletion phase: %s",
            exc,
            exc_info=True,
        )

    # -----------------------------------------------------------------
    # Step 4: Flush all query cache keys regardless of job success/failure.
    # LMS-CACHE-005 §5: "Stale counts are worse post-purge."
    # Even on partial success, flush so stale pre-deletion counts are not served.
    # -----------------------------------------------------------------
    try:
        redis = get_redis_client()
        await invalidate_all_query_cache(redis)
        logger.debug("Query cache flushed after retention run.")
    except Exception as exc:
        logger.warning("Failed to flush query cache after retention run: %s", exc)

    # -----------------------------------------------------------------
    # Step 5: Write self-log entry (BRD FR-15).
    # Uses the primary DB connection (lms_app INSERT on application_logs).
    # This is separate from the retention DB session to avoid privilege issues.
    # -----------------------------------------------------------------
    run_end = datetime.now(timezone.utc)
    duration_seconds = (run_end - run_start).total_seconds()

    try:
        await _write_retention_self_log(
            status=job_status,
            deleted_app=deleted_app,
            deleted_audit=deleted_audit,
            duration_seconds=duration_seconds,
            error_detail=error_detail,
            run_at=run_start,
        )
    except Exception as exc:
        # Self-logging failure must not propagate — the job's primary work
        # may have succeeded even if self-logging fails.
        logger.error(
            "Retention job could not write self-log entry: %s", exc, exc_info=True
        )

    # -----------------------------------------------------------------
    # Step 6: Store metadata in Redis for /metrics endpoint.
    # LMS-API-004 §2.8: retention_last_run, retention_deleted_count.
    # -----------------------------------------------------------------
    try:
        redis = get_redis_client()
        await record_retention_run(
            redis=redis,
            deleted_app_logs=deleted_app,
            deleted_audit_logs=deleted_audit,
            run_timestamp=run_start,
        )
    except Exception as exc:
        logger.warning(
            "Failed to store retention metadata for /metrics: %s", exc
        )

    logger.info(
        "Retention job finished: status=%s duration=%.2fs "
        "app_deleted=%d audit_deleted=%d",
        job_status,
        duration_seconds,
        deleted_app,
        deleted_audit,
    )


# ---------------------------------------------------------------------------
# Deletion helpers
# ---------------------------------------------------------------------------

def _calculate_threshold(retention_days: int) -> datetime:
    """
    Returns the naive UTC datetime before which log entries should be deleted.
    Rows with a timestamp strictly before this value are expired.

    Args:
        retention_days: Number of days to retain logs.

    Returns:
        Naive UTC datetime (timezone info stripped for MariaDB DATETIME column).
    """
    threshold = datetime.now(timezone.utc) - timedelta(days=retention_days)
    return threshold.replace(tzinfo=None)  # MariaDB stores naive UTC DATETIME.


async def _delete_app_logs(
    session: AsyncSession,
    threshold: datetime,
) -> int:
    """
    Deletes application_logs rows where created_at < threshold.

    LMS-BRD-001 FR-12: "Application logs older than 90 days MUST be
    automatically deleted by a scheduled background job."
    LMS-SDD-002 §3.5: "DELETE FROM application_logs WHERE created_at < NOW() - INTERVAL 90 DAY"

    Uses SQLAlchemy delete() with a WHERE clause — parameterised, safe from injection.
    LMS-SDD-002 §6: "All DB queries use SQLAlchemy parameterized statements."

    Args:
        session:   AsyncSession (lms_retention user).
        threshold: Rows with created_at strictly before this are deleted.

    Returns:
        Number of rows deleted.
    """
    stmt = (
        delete(ApplicationLog)
        .where(ApplicationLog.created_at < threshold)
        .execution_options(synchronize_session=False)
    )
    result = await session.execute(stmt)
    deleted = result.rowcount

    logger.debug(
        "Deleted %d application_logs rows (created_at < %s)",
        deleted,
        threshold.isoformat(),
    )
    return deleted


async def _delete_audit_logs(
    session: AsyncSession,
    threshold: datetime,
) -> int:
    """
    Deletes audit_logs rows where ingested_at < threshold.

    LMS-BRD-001 FR-13: "Audit logs older than 365 days MUST be automatically
    deleted by the same job."
    [CONFLICT-01 resolved]: Uses ingested_at (server receive time), NOT event_time.
    LMS-DB-003 §4: "Audit log DELETE for lms_retention is intentionally allowed
    only for rows where event_time is beyond the 365-day threshold. This is
    enforced by the WHERE clause in the retention job."
    NOTE: The DB-003 doc says event_time but CONFLICT-01 was resolved to use
    ingested_at per explicit instruction. WHERE clause enforces the boundary.

    Args:
        session:   AsyncSession (lms_retention user).
        threshold: Rows with ingested_at strictly before this are deleted.

    Returns:
        Number of rows deleted.
    """
    stmt = (
        delete(AuditLog)
        .where(AuditLog.ingested_at < threshold)
        .execution_options(synchronize_session=False)
    )
    result = await session.execute(stmt)
    deleted = result.rowcount

    logger.debug(
        "Deleted %d audit_logs rows (ingested_at < %s)",
        deleted,
        threshold.isoformat(),
    )
    return deleted


# ---------------------------------------------------------------------------
# Self-logging
# BRD FR-15: "The retention job SHOULD log its own execution result
# as an application log entry."
# ---------------------------------------------------------------------------

async def _write_retention_self_log(
    status: str,
    deleted_app: int,
    deleted_audit: int,
    duration_seconds: float,
    error_detail: str | None,
    run_at: datetime,
) -> None:
    """
    Writes a summary application log entry for the retention job run.
    Uses the primary DB connection (lms_app INSERT on application_logs).

    Log level is INFO on success, ERROR on failure.
    LMS-BRD-001 FR-15: "SHOULD log its own execution result."
    LMS-SDD-002 §3.5: "Job writes a summary application log entry on completion."

    Args:
        status:           "SUCCESS" or "FAILURE"
        deleted_app:      Rows deleted from application_logs.
        deleted_audit:    Rows deleted from audit_logs.
        duration_seconds: Wall-clock time of the job run.
        error_detail:     Exception message if failed, else None.
        run_at:           UTC start time of the job.
    """
    from app.core.database import get_db  # Local import to avoid circular deps.

    log_level = "INFO" if status == "SUCCESS" else "ERROR"
    message = (
        f"Retention job {status}: "
        f"deleted {deleted_app} app logs, {deleted_audit} audit logs "
        f"in {duration_seconds:.2f}s."
    )
    if error_detail:
        message += f" Error: {error_detail}"

    context = {
        "job": "retention",
        "status": status,
        "deleted_app_logs": deleted_app,
        "deleted_audit_logs": deleted_audit,
        "duration_seconds": round(duration_seconds, 3),
        "run_at": run_at.isoformat(),
    }
    if error_detail:
        context["error"] = error_detail

    async for session in get_db():
        log_entry = ApplicationLog(
            source_service=LMS_SYSTEM_SERVICE_ID,
            level=log_level,
            message=message,
            environment=LMS_SYSTEM_ENVIRONMENT,
            created_at=run_at.replace(tzinfo=None),
            context_json=context,
        )
        session.add(log_entry)
        # Session commit is handled by the get_db() context manager.

    logger.debug("Retention self-log written: level=%s", log_level)
