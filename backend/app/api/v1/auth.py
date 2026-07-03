# =============================================================================
# purpose:  GitHub OAuth 2.0 authentication endpoints.
#
#   GET  /api/v1/auth/login           → returns GitHub authorization URL
#   GET  /api/v1/auth/callback        → exchanges code, issues JWT pair
#   POST /api/v1/auth/refresh         → rotates refresh token, new access token
#   POST /api/v1/auth/logout          → revokes refresh token / ends session
#   GET  /api/v1/auth/me              → returns current user info
#
# Frontend flow:
#   1. Call GET /auth/login  → get { authorization_url }
#   2. Redirect user to authorization_url (GitHub login page)
#   3. GitHub redirects back to your redirect_uri with ?code=...&state=...
#   4. Frontend sends code+state to GET /auth/callback
#   5. Backend returns { access_token, refresh_token, username }
#   6. Frontend stores tokens; uses access_token as Bearer on every request
#   7. When access_token expires, call POST /auth/refresh with refresh_token
# =============================================================================

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.auth import (
    get_github_authorization_url,
    handle_oauth_callback,
    refresh_access_token,
    revoke_session,
)
from app.core.dependencies import CurrentUser, RedisClient
from app.schemas.error_schemas import ErrorResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginUrlResponse(BaseModel):
    authorization_url: str = Field(
        ...,
        description="Redirect the user to this GitHub URL to begin OAuth login.",
    )


class TokenResponse(BaseModel):
    access_token:  str = Field(..., description="Short-lived JWT. Use as Bearer token.")
    refresh_token: str = Field(..., description="Long-lived opaque token. Store securely.")
    token_type:    str = Field(default="bearer")
    username:      str = Field(..., description="Authenticated GitHub username.")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="The refresh token from the last login or refresh.")
    jti:           str = Field(..., description="The jti claim from your current access token.")


class MeResponse(BaseModel):
    username: str
    message:  str = "Authenticated"


# ---------------------------------------------------------------------------
# GET /auth/login — Step 1: get GitHub authorization URL
# ---------------------------------------------------------------------------

@router.get(
    "/login",
    response_model=LoginUrlResponse,
    summary="Get GitHub Login URL",
    description=(
        "Returns the GitHub OAuth authorization URL. "
        "Redirect your user to this URL. "
        "GitHub will redirect back to the configured redirect_uri with a code."
    ),
)
async def get_login_url(redis: RedisClient) -> LoginUrlResponse:
    """
    Frontend calls this first. No auth required.
    Returns the URL to send the user to for GitHub login.
    """
    url = await get_github_authorization_url(redis)
    return LoginUrlResponse(authorization_url=url)


# ---------------------------------------------------------------------------
# GET /auth/callback
# ---------------------------------------------------------------------------

class OAuthCallbackRequest(BaseModel):
    code: str
    state: str


@router.post(
    "/callback",
    response_model=TokenResponse,
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Unauthorized GitHub user or invalid code",
        },
    },
    summary="GitHub OAuth Callback",
    description=(
        "Receives the GitHub authorization code and state from the frontend, "
        "verifies the GitHub user, and issues access and refresh tokens."
    ),
)
async def github_callback(
    payload: OAuthCallbackRequest,
    redis: RedisClient,
) -> TokenResponse:
    access_token, refresh_token = await handle_oauth_callback(
        code=payload.code,
        state=payload.state,
        redis=redis,
    )

    from app.core.auth import decode_access_token

    user = decode_access_token(access_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        username=user.github_username,
    )


# ---------------------------------------------------------------------------
# POST /auth/refresh — rotate refresh token
# ---------------------------------------------------------------------------

@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired refresh token"},
    },
    summary="Refresh Access Token",
    description=(
        "Exchange a refresh token for a new access token + refresh token. "
        "The old refresh token is immediately invalidated (rotation). "
        "Store the new refresh token for the next refresh."
    ),
)
async def refresh(
    body:  RefreshRequest,
    redis: RedisClient,
) -> TokenResponse:
    """
    Call this when your access token expires (401 response).
    Send the refresh_token and the jti from your old access token.
    (Decode the JWT locally to extract jti — it's in the payload.)
    """
    new_access, new_refresh = await refresh_access_token(
        refresh_token=body.refresh_token,
        jti=body.jti,
        redis=redis,
    )
    from app.core.auth import decode_access_token
    user = decode_access_token(new_access)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        username=user.github_username,
    )


# ---------------------------------------------------------------------------
# POST /auth/logout — revoke session
# ---------------------------------------------------------------------------

@router.post(
    "/logout",
    status_code=204,
    summary="Logout",
    description="Revokes the current session. The refresh token is deleted from the server.",
)
async def logout(
    current_user: CurrentUser,
    redis:        RedisClient,
) -> None:
    """
    Invalidates the refresh token stored in Redis for this session.
    The access token remains technically valid until it expires naturally
    (short TTL makes this acceptable for personal use).
    """
    await revoke_session(current_user.jti, redis)


# ---------------------------------------------------------------------------
# GET /auth/me — who am I?
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=MeResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Current User",
    description="Returns the currently authenticated GitHub username.",
)
async def me(current_user: CurrentUser) -> MeResponse:
    return MeResponse(username=current_user.github_username)
