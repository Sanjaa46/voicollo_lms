import hashlib
import json
import logging
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ServiceNotRegisteredError,
    ServiceAlreadyRegisteredError,
    ServiceAlreadyDisabledError
)
from app.models.service import Service
from app.schemas.service_schema import (
    AddServiceRequest,
    AddServiceResponse,
    ServiceQueryParams,
    ServiceQueryResponse,
    ServiceEntry,
    DisableServiceResponse,
    EnableServiceResponse
)

logger = logging.getLogger(__name__)

async def _validate_service(db: AsyncSession, source_service: str) -> None:
    stmt = select(Service).where(Service.id == source_service)
    result = await db.execute(stmt)
    service = result.scalar_one_or_none()

    if service:
        raise ServiceAlreadyRegisteredError(source_service)


async def add_service(
    db: AsyncSession,
    redis: Redis,
    request: AddServiceRequest,
) -> AddServiceResponse:
    await _validate_service(db, request.id)

    service = Service(
        id=request.id,
        name=request.name,
        description=request.description,
    )
    db.add(service)
    await db.flush()
    await db.refresh(service)
    await db.commit()

    logger.debug(
        "Services added: id=%d name=%s",
        service.id,
        service.name,
    )

    await _invalidate_service_cache(redis)

    return AddServiceResponse(
        id=service.id,
        created_at=service.created_at
    )


CACHE_TTL = 60
CACHE_PREFIX = "svc:query:"


def _cache_key(params: ServiceQueryParams) -> str:
    raw = f"{params.id}:{params.name}"
    return CACHE_PREFIX + hashlib.md5(raw.encode()).hexdigest()


async def query_services(
    db: AsyncSession,
    redis: Redis,
    params: ServiceQueryParams,
) -> ServiceQueryResponse:

    cache_key = _cache_key(params)

    # 1. Try cache
    cached = await redis.get(cache_key)
    if cached:
        entries = [ServiceEntry(**item) for item in json.loads(cached)]
        return ServiceQueryResponse(data=entries)

    # 2. Build query
    stmt = select(Service)  # your SQLAlchemy model

    filters = []
    if params.id:
        filters.append(Service.id.ilike(f"%{params.id}%"))
    if params.name:
        filters.append(Service.name.ilike(f"%{params.name}%"))

    if filters:
        stmt = stmt.where(or_(*filters))

    result = await db.execute(stmt)
    rows = result.scalars().all()

    # 3. Serialize
    data = [ServiceEntry.model_validate(row) for row in rows]

    # 4. Cache
    await redis.set(
        cache_key,
        json.dumps([e.model_dump(mode="json") for e in data]),
        ex=CACHE_TTL,
    )

    return ServiceQueryResponse(data=data)



async def get_single_service(
    db: AsyncSession,
    service_id: str,
) -> ServiceEntry :
    stmt = select(Service).where(Service.id == service_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if not row:
        raise ServiceNotRegisteredError(f"Service {service_id} not exists.")
    
    return ServiceEntry(
        id=row.id,
        name=row.name,
        description=row.description,
        is_active=row.is_active,
        created_at=row.created_at
    )

async def _invalidate_service_cache(redis: Redis) -> None:
    """Delete all service query cache entries."""
    keys = await redis.keys(f"{CACHE_PREFIX}*")
    if keys:
        await redis.delete(*keys)


async def disable_service(
    db: AsyncSession,
    redis: Redis,
    service_id: str,
) -> DisableServiceResponse:
    row = await db.scalar(select(Service).where(Service.id == service_id))

    if not row:
        raise ServiceNotRegisteredError(f"Service {service_id} not exists.")
    if not row.is_active:
        raise ServiceAlreadyDisabledError(f"Service {service_id} is already disabled.")

    row.is_active = False
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)

    await _invalidate_service_cache(redis)

    return DisableServiceResponse(id=row.id, is_active=row.is_active, updated_at=row.updated_at)


async def enable_service(
    db: AsyncSession,
    redis: Redis,          # ← add redis param
    service_id: str,
) -> EnableServiceResponse:
    row = await db.scalar(select(Service).where(Service.id == service_id))

    if not row:
        raise ServiceNotRegisteredError(f"Service {service_id} not exists.")

    row.is_active = True
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)

    await _invalidate_service_cache(redis)   # ← bust the cache

    return EnableServiceResponse(id=row.id, is_active=row.is_active, updated_at=row.updated_at)