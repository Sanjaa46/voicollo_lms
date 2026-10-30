"""GitHub OAuth endpoints (single allowed user)."""

from fastapi import APIRouter, Response

from app.core import security
from app.core.dependencies import CurrentUser, RedisClient
from app.schemas.auth import (
    CallbackRequest,
    LoginUrlResponse,
    MeResponse,
    RefreshRequest,
    TokenResponse,
)
from app.schemas.common import ErrorResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _tokens(pair: security.TokenPair) -> TokenResponse:
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        username=pair.username,
        expires_in=pair.expires_in,
    )


@router.get("/login", response_model=LoginUrlResponse, summary="Get the GitHub sign-in URL")
async def login(redis: RedisClient) -> LoginUrlResponse:
    return LoginUrlResponse(authorization_url=await security.build_authorization_url(redis))


@router.post(
    "/callback",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Exchange the GitHub code for a session",
)
async def callback(body: CallbackRequest, redis: RedisClient) -> TokenResponse:
    return _tokens(await security.complete_login(body.code, body.state, redis))


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Rotate the refresh token and get a new access token",
)
async def refresh(body: RefreshRequest, redis: RedisClient) -> TokenResponse:
    return _tokens(await security.rotate_refresh_token(redis, body.refresh_token, body.jti))


@router.post("/logout", status_code=204, summary="Sign out (revokes both tokens)")
async def logout(user: CurrentUser, redis: RedisClient) -> Response:
    await security.revoke_session(redis, user.jti)
    return Response(status_code=204)


@router.get("/me", response_model=MeResponse, responses={401: {"model": ErrorResponse}})
async def me(user: CurrentUser) -> MeResponse:
    return MeResponse(username=user.github_username)
