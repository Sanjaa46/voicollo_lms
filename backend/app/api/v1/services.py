"""Service registry endpoints (user session required)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUser, DBSession, RedisClient
from app.schemas.common import ErrorResponse
from app.schemas.services import ServiceCreate, ServiceListResponse, ServiceOut, ServiceUpdate
from app.services import service_registry

router = APIRouter(prefix="/services", tags=["Services"])

_NOT_FOUND = {404: {"model": ErrorResponse}, 401: {"model": ErrorResponse}}


@router.get("", response_model=ServiceListResponse, responses={401: {"model": ErrorResponse}})
async def list_services(
    db: DBSession,
    _: CurrentUser,
    q: Annotated[str | None, Query(max_length=128, description="Search id or name")] = None,
    status: Literal["active", "disabled"] | None = None,
) -> ServiceListResponse:
    data = await service_registry.list_services(db, q=q, status=status)
    return ServiceListResponse(data=data, total=len(data))


@router.post(
    "",
    status_code=201,
    response_model=ServiceOut,
    responses={409: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
async def create_service(
    body: ServiceCreate, db: DBSession, redis: RedisClient, _: CurrentUser
) -> ServiceOut:
    return await service_registry.create_service(db, redis, body)


@router.get("/{service_id}", response_model=ServiceOut, responses=_NOT_FOUND)
async def get_service(service_id: str, db: DBSession, _: CurrentUser) -> ServiceOut:
    return await service_registry.get_service(db, service_id)


@router.patch("/{service_id}", response_model=ServiceOut, responses=_NOT_FOUND)
async def update_service(
    service_id: str, body: ServiceUpdate, db: DBSession, _: CurrentUser
) -> ServiceOut:
    return await service_registry.update_service(db, service_id, body)


@router.post("/{service_id}/enable", response_model=ServiceOut, responses=_NOT_FOUND)
@router.patch("/{service_id}/enable", response_model=ServiceOut, include_in_schema=False)
async def enable_service(
    service_id: str, db: DBSession, redis: RedisClient, _: CurrentUser
) -> ServiceOut:
    return await service_registry.set_active(db, redis, service_id, True)


@router.post(
    "/{service_id}/disable",
    response_model=ServiceOut,
    responses={**_NOT_FOUND, 409: {"model": ErrorResponse}},
)
@router.patch("/{service_id}/disable", response_model=ServiceOut, include_in_schema=False)
async def disable_service(
    service_id: str, db: DBSession, redis: RedisClient, _: CurrentUser
) -> ServiceOut:
    return await service_registry.set_active(db, redis, service_id, False)
