# =============================================================================
# purpose:  FastAPI Depends() factories. No roles — just authenticated or not.
#           Any valid access token = full access to all endpoints.
# =============================================================================

import logging
from typing import Annotated

import hmac
import hashlib
import time
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser, decode_access_token, extract_bearer_token
from app.core.database import get_db as _get_db
from app.core.config import get_settings
from app.core.redis_client import get_redis as _get_redis
from app.core.exceptions import SignatureInvalidError, SignatureExpiredError

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

SIGNATURE_TOLERANCE_SECONDS = 30

# ---------------------------------------------------------------------------
# Infrastructure dependencies
# ---------------------------------------------------------------------------

async def get_db() -> AsyncSession:  # type: ignore[return]
    async for session in _get_db():
        yield session


async def get_redis() -> Redis:  # type: ignore[return]
    async for client in _get_redis():
        yield client


DBSession    = Annotated[AsyncSession, Depends(get_db)]
RedisClient  = Annotated[Redis,        Depends(get_redis)]


# ---------------------------------------------------------------------------
# Authentication — single gate, no roles
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> AuthenticatedUser:
    """
    Validates the Bearer access token and returns the authenticated user.
    This is the only auth gate — no roles, no hierarchy.
    Any valid token from the allowed GitHub user = full access.

    Raises:
        AuthTokenMissingError  (401) — no Authorization header
        AuthTokenInvalidError  (401) — expired or invalid token
    """
    raw = f"Bearer {credentials.credentials}" if credentials else None
    token = extract_bearer_token(raw)
    return decode_access_token(token)


async def verify_service_signature(
    request: Request,
    x_timestamp: Annotated[str | None, Header()] = None,
    x_signature: Annotated[str | None, Header()] = None,
) -> None:
    """
    Verifies HMAC-SHA256 request signature from producer services.
    
    Producer must send:
        X-Timestamp: unix timestamp (seconds)
        X-Signature: hmac_sha256(secret, f"{timestamp}.{body_bytes}")
    """
    if not x_timestamp or not x_signature:
        raise SignatureInvalidError("Missing X-Timestamp or X-Signature header.")

    # Replay attack guard
    try:
        ts = int(x_timestamp)
    except ValueError:
        raise SignatureInvalidError("X-Timestamp must be an integer.")
    
    if abs(time.time() - ts) > SIGNATURE_TOLERANCE_SECONDS:
        raise SignatureExpiredError()

    body = await request.body()
    settings = get_settings()

    expected = hmac.new(
        settings.ingest_signing_secret.encode(),
        f"{x_timestamp}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, x_signature):
        raise SignatureInvalidError("Signature mismatch.")


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
ServiceSignature = Annotated[None, Depends(verify_service_signature)]
