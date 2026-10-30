"""Read path: filtering, global ordering across both log tables, pagination."""

from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import LogNotFoundError
from app.core.time import to_utc_naive
from app.models import ApplicationLog, AuditLog
from app.schemas.logs import (
    AppLogEntry,
    AuditLogEntry,
    LogFilters,
    LogType,
    PaginatedLogsResponse,
    SortOrder,
)
from app.services.service_registry import escape_like

AnyEntry = AppLogEntry | AuditLogEntry


@dataclass(frozen=True)
class _Plan:
    include_app: bool
    include_audit: bool
    app_where: list[ColumnElement[bool]]
    audit_where: list[ColumnElement[bool]]


def _like(column, text: str) -> ColumnElement[bool]:
    return column.ilike(f"%{escape_like(text)}%", escape="\\")


def build_plan(f: LogFilters) -> _Plan:
    """Translate filters into WHERE clauses for each table.

    Type-specific filters narrow `log_type=both`: asking for level=ERROR means
    "error application logs", not "error app logs plus every audit log".
    """
    app_only = bool(f.level or f.trace_id)
    audit_only = bool(f.outcome or f.actor_id or f.action)
    include_app = f.log_type in (LogType.APP, LogType.BOTH) and not audit_only
    include_audit = f.log_type in (LogType.AUDIT, LogType.BOTH) and not app_only

    start = to_utc_naive(f.start_time) if f.start_time else None
    end = to_utc_naive(f.end_time) if f.end_time else None

    app: list[ColumnElement[bool]] = []
    if f.source_service:
        app.append(ApplicationLog.source_service.in_(f.source_service))
    if f.environment:
        app.append(ApplicationLog.environment == f.environment)
    if f.level:
        app.append(ApplicationLog.level.in_([lv.value for lv in f.level]))
    if f.trace_id:
        app.append(ApplicationLog.trace_id == f.trace_id)
    if start:
        app.append(ApplicationLog.created_at >= start)
    if end:
        app.append(ApplicationLog.created_at <= end)
    if f.q:
        app.append(_like(ApplicationLog.message, f.q))

    audit: list[ColumnElement[bool]] = []
    if f.source_service:
        audit.append(AuditLog.source_service.in_(f.source_service))
    if f.environment:
        audit.append(AuditLog.environment == f.environment)
    if f.outcome:
        audit.append(AuditLog.outcome.in_([o.value for o in f.outcome]))
    if f.actor_id:
        audit.append(AuditLog.actor_id == f.actor_id)
    if f.action:
        audit.append(AuditLog.action == f.action.strip().upper())
    if start:
        audit.append(AuditLog.event_time >= start)
    if end:
        audit.append(AuditLog.event_time <= end)
    if f.q:
        audit.append(
            or_(
                _like(AuditLog.action, f.q),
                _like(AuditLog.target_resource, f.q),
                _like(AuditLog.actor_id, f.q),
            )
        )
    return _Plan(include_app, include_audit, app, audit)


async def count_logs(db: AsyncSession, plan: _Plan) -> int:
    total = 0
    if plan.include_app:
        total += (
            await db.scalar(select(func.count()).select_from(ApplicationLog).where(*plan.app_where))
            or 0
        )
    if plan.include_audit:
        total += (
            await db.scalar(select(func.count()).select_from(AuditLog).where(*plan.audit_where))
            or 0
        )
    return total


def _ordered_keys(plan: _Plan, sort: SortOrder) -> Select:
    """(log_type, id, ts) for every matching row, globally ordered across tables."""
    parts = []
    if plan.include_app:
        parts.append(
            select(
                literal("app").label("log_type"),
                ApplicationLog.id.label("id"),
                ApplicationLog.created_at.label("ts"),
            ).where(*plan.app_where)
        )
    if plan.include_audit:
        parts.append(
            select(
                literal("audit").label("log_type"),
                AuditLog.id.label("id"),
                AuditLog.event_time.label("ts"),
            ).where(*plan.audit_where)
        )
    keys = (union_all(*parts) if len(parts) > 1 else parts[0]).subquery("k")
    if sort == SortOrder.DESC:
        order = (keys.c.ts.desc(), keys.c.id.desc(), keys.c.log_type.desc())
    else:
        order = (keys.c.ts.asc(), keys.c.id.asc(), keys.c.log_type.asc())
    return select(keys.c.log_type, keys.c.id).order_by(*order)


async def fetch_logs(
    db: AsyncSession, plan: _Plan, sort: SortOrder, offset: int, limit: int
) -> list[AnyEntry]:
    if not (plan.include_app or plan.include_audit):
        return []
    keys = (await db.execute(_ordered_keys(plan, sort).offset(offset).limit(limit))).all()
    app_ids = [row.id for row in keys if row.log_type == "app"]
    audit_ids = [row.id for row in keys if row.log_type == "audit"]

    by_key: dict[tuple[str, int], AnyEntry] = {}
    if app_ids:
        for row in await db.scalars(select(ApplicationLog).where(ApplicationLog.id.in_(app_ids))):
            by_key[("app", row.id)] = AppLogEntry.model_validate(row)
    if audit_ids:
        for row in await db.scalars(select(AuditLog).where(AuditLog.id.in_(audit_ids))):
            by_key[("audit", row.id)] = AuditLogEntry.model_validate(row)
    return [by_key[(row.log_type, row.id)] for row in keys if (row.log_type, row.id) in by_key]


async def query_logs(
    db: AsyncSession, filters: LogFilters, page: int, page_size: int
) -> PaginatedLogsResponse:
    plan = build_plan(filters)
    if not (plan.include_app or plan.include_audit):
        return PaginatedLogsResponse(
            data=[], total=0, page=page, page_size=page_size, has_next=False
        )
    offset = (page - 1) * page_size
    total = await count_logs(db, plan)
    data = await fetch_logs(db, plan, filters.sort, offset, page_size) if offset < total else []
    return PaginatedLogsResponse(
        data=data,
        total=total,
        page=page,
        page_size=page_size,
        has_next=offset + len(data) < total,
    )


async def get_log(db: AsyncSession, log_type: str, log_id: int) -> AnyEntry:
    if log_type == "app":
        app_row = await db.get(ApplicationLog, log_id)
        if app_row is None:
            raise LogNotFoundError("app", log_id)
        return AppLogEntry.model_validate(app_row)
    audit_row = await db.get(AuditLog, log_id)
    if audit_row is None:
        raise LogNotFoundError("audit", log_id)
    return AuditLogEntry.model_validate(audit_row)
