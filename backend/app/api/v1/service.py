# =============================================================================
# purpose:  Service registry endpoints. Auth = valid access token, no roles.
# =============================================================================

import logging
from fastapi import APIRouter, Depends

from app.core.dependencies import CurrentUser, DBSession, RedisClient
from app.schemas.service_schema import (
    AddServiceRequest,
    AddServiceResponse,
    ServiceQueryParams,
    ServiceQueryResponse,
    ServiceEntry,
    DisableServiceResponse,
    EnableServiceResponse
)
from app.schemas.error_schemas import ErrorResponse
from app.services import add_srvc_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/services", tags=["Service Registry"])


@router.post(
    "",
    status_code=201,
    response_model=AddServiceResponse,
    responses={
        409: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
async def register_service(
    request: AddServiceRequest,
    db: DBSession,
    redis: RedisClient,
    _: CurrentUser,
) -> AddServiceResponse:
    return await add_srvc_service.add_service(db=db, redis=redis, request=request)


@router.get(
    "",
    status_code=200,
    response_model=ServiceQueryResponse,
    responses={
        401: {"model": ErrorResponse},
    },
)
async def query_services(
    db: DBSession,
    redis: RedisClient,
    _: CurrentUser,
    params: ServiceQueryParams = Depends(),
) -> ServiceQueryResponse:
    return await add_srvc_service.query_services(db=db, redis=redis, params=params)


@router.get(
    "/{service_id}",
    status_code=200,
    response_model=ServiceEntry,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
async def get_service(
    service_id: str,
    db: DBSession,
    _: CurrentUser,
) -> ServiceEntry:
    return await add_srvc_service.get_single_service(db=db, service_id=service_id)


@router.patch(
    "/{service_id}/disable",
    status_code=200,
    response_model=DisableServiceResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
async def disable_service(
    service_id: str,
    db: DBSession,
    redis: RedisClient,
    _: CurrentUser,
) -> DisableServiceResponse:
    return await add_srvc_service.disable_service(db=db, service_id=service_id, redis=redis)

@router.patch(
    "/{service_id}/enable",
    status_code=200,
    response_model=EnableServiceResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
async def enable_service(
    service_id: str,
    db: DBSession,
    redis: RedisClient,
    _: CurrentUser,
) -> EnableServiceResponse:
    return await add_srvc_service.enable_service(db=db, service_id=service_id, redis=redis)