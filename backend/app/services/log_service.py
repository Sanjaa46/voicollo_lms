# =============================================================================
# purpose:  Core business logic for all log operations.
#           Implements write, batch-write, query, single-get, and export
#           operations against MariaDB via SQLAlchemy 2.0 async ORM.
#           Cache invalidation is triggered here on every successful write.
#           All DB queries use parameterised statements — no raw SQL strings.
# implements: LMS-SDD-002 §3.3 (Ingestion Flow)
#             LMS-SDD-002 §3.4 (Query Flow)
#             LMS-SDD-002 §6   (Security — parameterised queries)
#             LMS-API-004 §2.1–§2.6 (all log endpoints)
#             LMS-BRD-001 FR-01–FR-09, FR-11, FR-14, FR-16
#             LMS-DB-003  §3.1–§3.3 (table columns and constraints)
# =============================================================================

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    LogEntryNotFoundError,
    ServiceNotRegisteredError,
)
from app.models.application_log import ApplicationLog
from app.models.audit_log import AuditLog
from app.models.service import Service
from app.schemas.log_schemas import (
    AppLogRequest,
    AppLogResponse,
    AuditLogRequest,
    AuditLogResponse,
    BatchAppLogRequest,
    BatchAppLogResponse,
    BatchAppLogResult,
    LogQueryParams,
    LogType,
    SortOrder,
    AppLogEntry,
    AuditLogEntry,
    PaginatedLogsResponse,
    LogLevel,
    ActorType,
    Outcome,
)
from app.services.cache_service import (
    invalidate_app_log_query_cache,
    increment_ingestion_counter,
    increment_query_counter,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# Service validation helper
# LMS-API-004 §2.1: "source_service Must match a registered services.id"
# [AMBIGUITY-03]: Returns 422 SERVICE_NOT_REGISTERED for unknown services.
# ===========================================================================

async def _validate_service(db: AsyncSession, source_service: str) -> None:
    """
    Checks that source_service exists and is active in the services registry.
    Raises ServiceNotRegisteredError (422) if not found or inactive.

    LMS-DB-003 §2: soft FK — validated at application layer.
    [AMBIGUITY-03]: Returning 422 for unregistered service.
    TODO: Confirm with team whether unregistered services should be silently
          accepted (soft FK behaviour) or rejected (current implementation).
    """
    stmt = select(Service).where(
        and_(
            Service.id == source_service,
            Service.is_active == True,  # noqa: E712 — SQLAlchemy needs == True
        )
    )
    result = await db.execute(stmt)
    service = result.scalar_one_or_none()

    if service is None:
        raise ServiceNotRegisteredError(source_service)


# ===========================================================================
# Application Log — Write
# LMS-SDD-002 §3.3 (Ingestion Flow)
# LMS-API-004 §2.1
# ===========================================================================

async def write_app_log(
    db: AsyncSession,
    redis: Redis,
    request: AppLogRequest,
) -> AppLogResponse:
    """
    Ingests a single application log entry.

    Flow (LMS-SDD-002 §3.3):
      1. Validate source_service against services registry.
      2. Insert row into application_logs.
      3. Invalidate query cache for the affected service.
      4. Return log_id and ingested_at.

    Args:
        db:      AsyncSession (lms_app user — INSERT privilege).
        redis:   Redis client for cache invalidation.
        request: Validated AppLogRequest payload.

    Returns:
        AppLogResponse with assigned log_id and server ingested_at.

    Raises:
        ServiceNotRegisteredError (422) — unknown or inactive source_service.
    """
    # Step 1: Validate service registration.
    await _validate_service(db, request.source_service)

    # Step 2: Build and insert ORM object.
    log_entry = ApplicationLog(
        source_service=request.source_service,
        level=request.level.value,
        message=request.message,
        environment=request.environment,
        created_at=request.created_at.replace(tzinfo=None),  # Store as naive UTC.
        trace_id=request.trace_id,
        context_json=request.context_json,
        # ingested_at is set by server_default on INSERT.
    )
    db.add(log_entry)
    await db.flush()  # Flush to get the auto-generated id before commit.
    await db.refresh(log_entry)

    # Step 3: Invalidate query cache.
    # [CONFLICT-02 resolved]: Only app log ingestion triggers active cache bust.
    # Audit log ingestion uses TTL-expiry only (LMS-CACHE-005 §5).
    await invalidate_app_log_query_cache(redis, request.source_service)

    # Increment metrics counter (best-effort).
    await increment_ingestion_counter(redis)

    logger.debug(
        "App log ingested: id=%d service=%s level=%s",
        log_entry.id,
        log_entry.source_service,
        log_entry.level,
    )

    return AppLogResponse(
        log_id=log_entry.id,
        ingested_at=log_entry.ingested_at,
    )


# ===========================================================================
# Application Log — Batch Write
# LMS-API-004 §2.2, LMS-BRD-001 FR-05
# ===========================================================================

async def write_app_log_batch(
    db: AsyncSession,
    redis: Redis,
    request: BatchAppLogRequest,
) -> BatchAppLogResponse:
    """
    Ingests up to 100 application log entries in a single request.
    Partial success is allowed — entries are processed independently.
    LMS-API-004 §2.2: "HTTP 207 Multi-Status. Partial success is allowed."

    Each entry is validated and inserted individually. An error in one
    entry does not prevent other entries from being persisted.

    Args:
        db:      AsyncSession.
        redis:   Redis client.
        request: BatchAppLogRequest with 1–100 AppLogRequest entries.

    Returns:
        BatchAppLogResponse with per-entry results and aggregate counts.
    """
    results: list[BatchAppLogResult] = []
    succeeded = 0
    failed = 0
    services_written: set[str] = set()

    for index, log_request in enumerate(request.logs):
        try:
            # Validate service (cached in memory across the batch for performance).
            await _validate_service(db, log_request.source_service)

            log_entry = ApplicationLog(
                source_service=log_request.source_service,
                level=log_request.level.value,
                message=log_request.message,
                environment=log_request.environment,
                created_at=log_request.created_at.replace(tzinfo=None),
                trace_id=log_request.trace_id,
                context_json=log_request.context_json,
            )
            db.add(log_entry)
            await db.flush()
            await db.refresh(log_entry)

            results.append(BatchAppLogResult(
                index=index,
                success=True,
                log_id=log_entry.id,
            ))
            services_written.add(log_request.source_service)
            succeeded += 1

        except ServiceNotRegisteredError as exc:
            results.append(BatchAppLogResult(
                index=index,
                success=False,
                error_code="SERVICE_NOT_REGISTERED",
                message=str(exc),
            ))
            failed += 1

        except Exception as exc:
            # Catch-all for unexpected per-entry errors — do not abort the batch.
            logger.warning(
                "Batch entry %d failed unexpectedly: %s", index, exc, exc_info=True
            )
            results.append(BatchAppLogResult(
                index=index,
                success=False,
                error_code="INTERNAL_ERROR",
                message="An unexpected error occurred processing this entry.",
            ))
            failed += 1

    # Commit all successful entries together.
    # (db.flush() above staged them; the session commit happens in get_db().)

    # Invalidate cache for all services that had successful writes.
    for service_id in services_written:
        await invalidate_app_log_query_cache(redis, service_id)

    # Increment ingestion counter by number of successful entries.
    if succeeded > 0:
        from app.services.cache_service import _increment_counter, METRICS_INGESTION_TOTAL_KEY
        await _increment_counter(redis, METRICS_INGESTION_TOTAL_KEY, succeeded)

    logger.info(
        "Batch ingestion complete: %d succeeded, %d failed (total=%d)",
        succeeded,
        failed,
        len(request.logs),
    )

    return BatchAppLogResponse(
        results=results,
        total=len(request.logs),
        succeeded=succeeded,
        failed=failed,
    )


# ===========================================================================
# Audit Log — Write
# LMS-API-004 §2.3, LMS-BRD-001 FR-03
# ===========================================================================

async def write_audit_log(
    db: AsyncSession,
    redis: Redis,
    request: AuditLogRequest,
) -> AuditLogResponse:
    """
    Ingests a single audit log entry.

    Audit logs are append-only — no cache invalidation is triggered
    on write (TTL-expiry only per LMS-CACHE-005 §5).
    [CONFLICT-02 resolved]: Audit ingestion → TTL expiry only, no active bust.

    Args:
        db:      AsyncSession (lms_app user — INSERT on audit_logs only).
        redis:   Redis client (used only for metrics counter).
        request: Validated AuditLogRequest payload.

    Returns:
        AuditLogResponse with assigned log_id and server ingested_at.

    Raises:
        ServiceNotRegisteredError (422) — unknown or inactive source_service.
    """
    # Validate service registration.
    await _validate_service(db, request.source_service)

    audit_entry = AuditLog(
        source_service=request.source_service,
        actor_id=request.actor_id,
        actor_type=request.actor_type.value,
        action=request.action,
        target_resource=request.target_resource,
        outcome=request.outcome.value,
        event_time=request.event_time.replace(tzinfo=None),  # Store as naive UTC.
        ip_address=request.ip_address,
        detail_json=request.detail_json,
        # ingested_at is set by server_default on INSERT.
    )
    db.add(audit_entry)
    await db.flush()
    await db.refresh(audit_entry)

    # NOTE: No cache invalidation here — audit writes use TTL-expiry only.
    # LMS-CACHE-005 §5: "New audit log ingested → TTL expiry only."
    # [CONFLICT-02 resolved].

    await increment_ingestion_counter(redis)

    logger.debug(
        "Audit log ingested: id=%d service=%s action=%s outcome=%s",
        audit_entry.id,
        audit_entry.source_service,
        audit_entry.action,
        audit_entry.outcome,
    )

    return AuditLogResponse(
        log_id=audit_entry.id,
        ingested_at=audit_entry.ingested_at,
    )


# ===========================================================================
# Query Logs
# LMS-SDD-002 §3.4 (Query Flow)
# LMS-API-004 §2.4
# ===========================================================================

async def query_logs(
    db: AsyncSession,
    redis: Redis,
    params: LogQueryParams,
) -> PaginatedLogsResponse:
    """
    Queries logs with filters, pagination, and sort. Returns a paginated
    response. The cache layer (get/set) is handled by the route handler —
    this function only executes the DB query.

    Supported filters (LMS-API-004 §2.4):
      log_type, level, source_service, start_time, end_time,
      actor_id (audit only), trace_id (app only), sort, page, page_size.

    Returns:
        PaginatedLogsResponse with data, total, page, page_size, has_next.

    LMS-BRD-001 FR-07: all filter types supported.
    LMS-BRD-001 FR-08: paginated, default 50, max 500.
    LMS-BRD-001 FR-09: sortable by timestamp ASC/DESC.
    """
    await increment_query_counter(redis)

    offset = (params.page - 1) * params.page_size
    end_time = params.end_time or datetime.now(timezone.utc).replace(tzinfo=None)
    if hasattr(end_time, 'tzinfo') and end_time.tzinfo is not None:
        end_time = end_time.replace(tzinfo=None)

    app_entries: list[AppLogEntry] = []
    audit_entries: list[AuditLogEntry] = []
    total = 0

    include_app = params.log_type in (LogType.APP, LogType.BOTH)
    include_audit = params.log_type in (LogType.AUDIT, LogType.BOTH)

    # -------------------------------------------------------------------------
    # Application logs query
    # -------------------------------------------------------------------------
    if include_app:
        app_stmt = select(ApplicationLog)
        app_count_stmt = select(func.count()).select_from(ApplicationLog)

        # Apply filters.
        app_filters = []
        if params.source_service:
            app_filters.append(
                ApplicationLog.source_service == params.source_service
            )
        if params.level:
            level_values = [lv.value for lv in params.level]
            app_filters.append(ApplicationLog.level.in_(level_values))
        if params.start_time:
            start = params.start_time.replace(tzinfo=None)
            app_filters.append(ApplicationLog.created_at >= start)
        if end_time:
            app_filters.append(ApplicationLog.created_at <= end_time)
        if params.trace_id:
            app_filters.append(ApplicationLog.trace_id == params.trace_id)

        # actor_id is audit-only — silently ignored for app logs per API §2.4.

        if app_filters:
            app_stmt = app_stmt.where(and_(*app_filters))
            app_count_stmt = app_count_stmt.where(and_(*app_filters))

        # Apply sort (LMS-BRD-001 FR-09).
        if params.sort == SortOrder.DESC:
            app_stmt = app_stmt.order_by(ApplicationLog.created_at.desc())
        else:
            app_stmt = app_stmt.order_by(ApplicationLog.created_at.asc())

        # For log_type=app only, apply pagination directly.
        # For log_type=both, we fetch half the page from each table.
        # [AMBIGUITY-04]: For 'both', we split page_size evenly.
        # TODO: Consider a proper UNION-based query or cursor pagination
        #       for more accurate interleaving when log_type=both.
        if params.log_type == LogType.BOTH:
            app_page_size = params.page_size // 2
        else:
            app_page_size = params.page_size

        app_stmt = app_stmt.offset(offset).limit(app_page_size)

        app_result = await db.execute(app_stmt)
        app_rows = app_result.scalars().all()

        app_count_result = await db.execute(app_count_stmt)
        app_total = app_count_result.scalar_one()
        total += app_total

        for row in app_rows:
            app_entries.append(AppLogEntry(
                id=row.id,
                source_service=row.source_service,
                level=LogLevel(row.level),
                message=row.message,
                environment=row.environment,
                context_json=row.context_json,
                trace_id=row.trace_id,
                created_at=row.created_at,
                ingested_at=row.ingested_at,
            ))

    # -------------------------------------------------------------------------
    # Audit logs query
    # -------------------------------------------------------------------------
    if include_audit:
        audit_stmt = select(AuditLog)
        audit_count_stmt = select(func.count()).select_from(AuditLog)

        audit_filters = []
        if params.source_service:
            audit_filters.append(
                AuditLog.source_service == params.source_service
            )
        if params.start_time:
            start = params.start_time.replace(tzinfo=None)
            audit_filters.append(AuditLog.event_time >= start)
        if end_time:
            audit_filters.append(AuditLog.event_time <= end_time)
        if params.actor_id:
            audit_filters.append(AuditLog.actor_id == params.actor_id)

        # trace_id is app-only — silently ignored for audit logs per API §2.4.

        if audit_filters:
            audit_stmt = audit_stmt.where(and_(*audit_filters))
            audit_count_stmt = audit_count_stmt.where(and_(*audit_filters))

        if params.sort == SortOrder.DESC:
            audit_stmt = audit_stmt.order_by(AuditLog.event_time.desc())
        else:
            audit_stmt = audit_stmt.order_by(AuditLog.event_time.asc())

        if params.log_type == LogType.BOTH:
            audit_page_size = params.page_size - (params.page_size // 2)
        else:
            audit_page_size = params.page_size

        audit_stmt = audit_stmt.offset(offset).limit(audit_page_size)

        audit_result = await db.execute(audit_stmt)
        audit_rows = audit_result.scalars().all()

        audit_count_result = await db.execute(audit_count_stmt)
        audit_total = audit_count_result.scalar_one()
        total += audit_total

        for row in audit_rows:
            audit_entries.append(AuditLogEntry(
                id=row.id,
                source_service=row.source_service,
                actor_id=row.actor_id,
                actor_type=ActorType(row.actor_type),
                action=row.action,
                target_resource=row.target_resource,
                outcome=Outcome(row.outcome),
                ip_address=row.ip_address,
                detail_json=row.detail_json,
                event_time=row.event_time,
                ingested_at=row.ingested_at,
            ))

    # Merge and sort combined results for log_type=both.
    if params.log_type == LogType.BOTH:
        def _sort_key(entry):
            # Fetch the values, defaulting to None if the attributes don't exist
            timestamp = getattr(entry, "created_at", None) or getattr(entry, "event_time", None)
            
            if timestamp is None:
                # Fallback to the oldest possible aware datetime (or naive, depending on your data)
                return datetime.min.replace(tzinfo=timezone.utc) 
                
            return timestamp

        combined = sorted(
            [*app_entries, *audit_entries],
            key=_sort_key,
            reverse=(params.sort == SortOrder.DESC),
        )
        data = combined
    else:
        data = [*app_entries, *audit_entries]

    has_next = (offset + len(data)) < total

    return PaginatedLogsResponse(
        data=data,
        total=total,
        page=params.page,
        page_size=params.page_size,
        has_next=has_next,
    )


# ===========================================================================
# Get Single Log Entry
# LMS-API-004 §2.5
# ===========================================================================

async def get_single_log(
    db: AsyncSession,
    log_type: str,
    log_id: int,
    is_admin: bool,
) -> AppLogEntry | AuditLogEntry:
    """
    Retrieves a single log entry by type and ID.

    Privacy rule (LMS-API-004 §2.5):
      "Returns 404 (not 403) for audit logs when actor is not LOG_ADMIN —
       do not reveal existence."
    This is implemented by the is_admin flag:
      - LOG_ADMIN: returns audit entry or 404 if genuinely not found.
      - Non-admin:  always returns 404 for audit entries (existence hidden).

    Args:
        db:       AsyncSession.
        log_type: "app" or "audit".
        log_id:   Primary key of the log entry.
        is_admin: True if the requesting user has LOG_ADMIN role.

    Returns:
        AppLogEntry or AuditLogEntry.

    Raises:
        LogEntryNotFoundError (404) — not found, or audit entry hidden from
        non-admin users.
    """
    if log_type == "app":
        stmt = select(ApplicationLog).where(ApplicationLog.id == log_id)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            raise LogEntryNotFoundError("app", log_id)

        return AppLogEntry(
            id=row.id,
            source_service=row.source_service,
            level=LogLevel(row.level),
            message=row.message,
            environment=row.environment,
            context_json=row.context_json,
            trace_id=row.trace_id,
            created_at=row.created_at,
            ingested_at=row.ingested_at,
        )

    elif log_type == "audit":
        # Non-admin: always 404 — do not reveal whether audit entry exists.
        # LMS-API-004 §2.5: "Returns 404 (not 403) for audit logs when actor
        # is not LOG_ADMIN — do not reveal existence."
        if not is_admin:
            raise LogEntryNotFoundError("audit", log_id)

        stmt = select(AuditLog).where(AuditLog.id == log_id)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            raise LogEntryNotFoundError("audit", log_id)

        return AuditLogEntry(
            id=row.id,
            source_service=row.source_service,
            actor_id=row.actor_id,
            actor_type=ActorType(row.actor_type),
            action=row.action,
            target_resource=row.target_resource,
            outcome=Outcome(row.outcome),
            ip_address=row.ip_address,
            detail_json=row.detail_json,
            event_time=row.event_time,
            ingested_at=row.ingested_at,
        )

    else:
        # Invalid log_type — route handler validates this, but guard here too.
        raise LogEntryNotFoundError(log_type, log_id)


# ===========================================================================
# Export Logs
# LMS-API-004 §2.6, LMS-BRD-001 FR-16
# ===========================================================================

async def export_logs(
    db: AsyncSession,
    params: LogQueryParams,
    export_format: str,
) -> tuple[str, str]:
    """
    Exports log entries matching the given filters as JSON or CSV.

    LMS-API-004 §2.6:
      - LOG_ADMIN only (enforced by route handler).
      - Max 10,000 rows per request.
      - format=json|csv.
      - Response: application/json or text/csv as file download.

    [GAP-02]: Pagination uses same page/page_size params as GET /logs.
    TODO: Consider cursor-based streaming export for >10k rows.

    Args:
        db:            AsyncSession.
        params:        LogQueryParams (page_size capped at 10,000 by ExportQueryParams).
        export_format: "json" or "csv".

    Returns:
        Tuple of (content: str, content_type: str).
    """
    # Re-use query_logs logic but pass a dummy Redis client (no caching on export).
    # Export always hits the DB — results should be fresh for compliance.
    from unittest.mock import AsyncMock
    dummy_redis = AsyncMock()
    dummy_redis.incr = AsyncMock(return_value=1)

    paginated = await query_logs(db, dummy_redis, params)
    entries = paginated.data

    if export_format == "json":
        # Serialise each entry to a dict, converting datetime to ISO string.
        rows = [_entry_to_dict(entry) for entry in entries]
        content = json.dumps(
            {
                "exported_at": datetime.now(timezone.utc).isoformat() + "Z",
                "total_exported": len(rows),
                "filters_applied": params.to_cache_key_dict(),
                "data": rows,
            },
            default=str,
            indent=2,
        )
        return content, "application/json"

    elif export_format == "csv":
        if not entries:
            return "", "text/csv"

        output = io.StringIO()

        # Determine CSV columns from the first entry's type.
        # Mixed exports write all possible columns with empty values where N/A.
        fieldnames = _get_csv_fieldnames(entries)
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for entry in entries:
            writer.writerow(_entry_to_dict(entry))

        return output.getvalue(), "text/csv"

    else:
        raise ValueError(f"Unsupported export format: {export_format!r}")


def _entry_to_dict(entry: AppLogEntry | AuditLogEntry) -> dict[str, Any]:
    """Converts a log entry schema to a plain dict for serialisation."""
    return entry.model_dump(mode="json")


def _get_csv_fieldnames(entries: list) -> list[str]:
    """
    Returns a consistent ordered list of CSV column names.
    For mixed exports, combines columns from both entry types.
    """
    app_fields = [
        "log_type", "id", "source_service", "level", "message",
        "environment", "context_json", "trace_id", "created_at", "ingested_at",
    ]
    audit_fields = [
        "log_type", "id", "source_service", "actor_id", "actor_type",
        "action", "target_resource", "outcome", "ip_address",
        "detail_json", "event_time", "ingested_at",
    ]

    has_app = any(getattr(e, "log_type", None) == "app" for e in entries)
    has_audit = any(getattr(e, "log_type", None) == "audit" for e in entries)

    if has_app and has_audit:
        # Merge both field lists preserving order, deduplicating.
        seen = set()
        merged = []
        for field in app_fields + audit_fields:
            if field not in seen:
                merged.append(field)
                seen.add(field)
        return merged
    elif has_audit:
        return audit_fields
    else:
        return app_fields
