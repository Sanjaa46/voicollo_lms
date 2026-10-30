"""Service registry: CRUD for producers plus the ingest-time eligibility check."""

import contextlib
import logging
from datetime import timedelta

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ServiceAlreadyExistsError,
    ServiceDisabledError,
    ServiceNotFoundError,
    ServiceNotRegisteredError,
    ServiceProtectedError,
)
from app.core.time import utcnow
from app.models import ApplicationLog, AuditLog, Service
from app.schemas.services import ServiceActivity, ServiceCreate, ServiceOut, ServiceUpdate

logger = logging.getLogger(__name__)

SYSTEM_SERVICE_ID = "lms-system"
PROTECTED_SERVICES = frozenset({SYSTEM_SERVICE_ID})

STATE_KEY = "lms:svc:state:{id}"
STATE_TTL_SECONDS = 30
_ACTIVE, _DISABLED, _MISSING = "active", "disabled", "missing"


# ------------------------------------------------------------------ ingest check
async def _state(db: AsyncSession, redis: Redis, service_id: str) -> str:
    key = STATE_KEY.format(id=service_id)
    try:
        cached = await redis.get(key)
        if cached:
            return cached
    except RedisError:
        cached = None
    row = await db.scalar(select(Service.is_active).where(Service.id == service_id))
    state = _MISSING if row is None else (_ACTIVE if row else _DISABLED)
    with contextlib.suppress(RedisError):
        await redis.set(key, state, ex=STATE_TTL_SECONDS)
    return state


async def ensure_can_ingest(db: AsyncSession, redis: Redis, service_id: str) -> None:
    state = await _state(db, redis, service_id)
    if state == _MISSING:
        raise ServiceNotRegisteredError(service_id)
    if state == _DISABLED:
        raise ServiceDisabledError(service_id)


async def _forget_state(redis: Redis, service_id: str) -> None:
    try:
        await redis.delete(STATE_KEY.format(id=service_id))
    except RedisError as exc:
        logger.warning("Could not clear cached state for %s: %s", service_id, exc)


# ------------------------------------------------------------------ CRUD
def _to_out(service: Service, activity: ServiceActivity | None = None) -> ServiceOut:
    out = ServiceOut.model_validate(service)
    out.is_protected = service.id in PROTECTED_SERVICES
    out.activity = activity
    return out


async def _get(db: AsyncSession, service_id: str) -> Service:
    service = await db.get(Service, service_id)
    if service is None:
        raise ServiceNotFoundError(service_id)
    return service


async def _activity(db: AsyncSession, service_ids: list[str]) -> dict[str, ServiceActivity]:
    if not service_ids:
        return {}
    since = utcnow() - timedelta(hours=24)
    result = {sid: ServiceActivity() for sid in service_ids}

    app_rows = await db.execute(
        select(
            ApplicationLog.source_service,
            func.max(ApplicationLog.created_at),
            func.sum(case((ApplicationLog.created_at >= since, 1), else_=0)),
            func.sum(
                case(
                    (
                        and_(
                            ApplicationLog.created_at >= since,
                            ApplicationLog.level.in_(("ERROR", "FATAL")),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
        )
        .where(ApplicationLog.source_service.in_(service_ids))
        .group_by(ApplicationLog.source_service)
    )
    for sid, last_seen, count_24h, errors_24h in app_rows:
        result[sid].last_seen_at = last_seen
        result[sid].app_logs_24h = int(count_24h or 0)
        result[sid].errors_24h = int(errors_24h or 0)

    audit_rows = await db.execute(
        select(
            AuditLog.source_service,
            func.max(AuditLog.event_time),
            func.sum(case((AuditLog.event_time >= since, 1), else_=0)),
        )
        .where(AuditLog.source_service.in_(service_ids))
        .group_by(AuditLog.source_service)
    )
    for sid, last_seen, count_24h in audit_rows:
        activity = result[sid]
        if last_seen and (activity.last_seen_at is None or last_seen > activity.last_seen_at):
            activity.last_seen_at = last_seen
        activity.audit_logs_24h = int(count_24h or 0)
    return result


async def list_services(
    db: AsyncSession,
    q: str | None = None,
    status: str | None = None,
    with_activity: bool = True,
) -> list[ServiceOut]:
    stmt = select(Service).order_by(Service.is_active.desc(), Service.id)
    if q:
        pattern = f"%{escape_like(q)}%"
        stmt = stmt.where(
            or_(Service.id.ilike(pattern, escape="\\"), Service.name.ilike(pattern, escape="\\"))
        )
    if status == "active":
        stmt = stmt.where(Service.is_active.is_(True))
    elif status == "disabled":
        stmt = stmt.where(Service.is_active.is_(False))
    services = list((await db.scalars(stmt)).all())
    activity = await _activity(db, [s.id for s in services]) if with_activity else {}
    return [_to_out(s, activity.get(s.id)) for s in services]


async def get_service(db: AsyncSession, service_id: str) -> ServiceOut:
    service = await _get(db, service_id)
    activity = await _activity(db, [service.id])
    return _to_out(service, activity.get(service.id))


async def create_service(db: AsyncSession, redis: Redis, body: ServiceCreate) -> ServiceOut:
    if await db.get(Service, body.id) is not None:
        raise ServiceAlreadyExistsError(body.id)
    service = Service(id=body.id, name=body.name, description=body.description or None)
    db.add(service)
    await db.flush()
    await _forget_state(redis, service.id)
    logger.info("Service registered: %s", service.id)
    return _to_out(service, ServiceActivity())


async def update_service(db: AsyncSession, service_id: str, body: ServiceUpdate) -> ServiceOut:
    service = await _get(db, service_id)
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"]:
        service.name = changes["name"]
    if "description" in changes:
        service.description = changes["description"] or None
    service.updated_at = utcnow()
    await db.flush()
    return await get_service(db, service_id)


async def set_active(db: AsyncSession, redis: Redis, service_id: str, active: bool) -> ServiceOut:
    """Enable or disable a service. Idempotent: repeating the call is not an error."""
    service = await _get(db, service_id)
    if not active and service.id in PROTECTED_SERVICES:
        raise ServiceProtectedError(service.id)
    if service.is_active != active:
        service.is_active = active
        service.updated_at = utcnow()
        await db.flush()
        logger.info("Service %s %s", service.id, "enabled" if active else "disabled")
    await _forget_state(redis, service.id)
    return await get_service(db, service_id)


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
