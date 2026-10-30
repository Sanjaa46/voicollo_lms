"""FastAPI dependencies: DB session, Redis, user auth, producer HMAC signature."""

import hashlib
import hmac
import logging
import time
from typing import Annotated

from fastapi import Depends, Header, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import (
    AuthTokenInvalidError,
    DuplicateRequestError,
    SignatureExpiredError,
    SignatureInvalidError,
)
from app.core.redis import get_redis
from app.core.security import AuthenticatedUser, decode_access_token, is_revoked, parse_bearer

logger = logging.getLogger(__name__)

DBSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]

SIGNATURE_SEEN_KEY = "lms:sig:{signature}"


async def get_current_user(
    redis: RedisClient,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser:
    user = decode_access_token(parse_bearer(authorization))
    if await is_revoked(redis, user.jti):
        raise AuthTokenInvalidError("Session has been signed out.")
    return user


def compute_signature(secret: str, timestamp: str, body: bytes) -> str:
    """HMAC-SHA256 over b"<timestamp>." + raw body, hex encoded."""
    return hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


async def verify_service_signature(
    request: Request,
    redis: RedisClient,
    x_timestamp: Annotated[str | None, Header()] = None,
    x_signature: Annotated[str | None, Header()] = None,
) -> None:
    """Authenticate a producer request.

    Producers send `X-Timestamp` (unix seconds) and
    `X-Signature = hex(HMAC_SHA256(INGEST_SIGNING_SECRET, f"{ts}." + body))`.
    A signature is accepted once; replays inside the window are rejected.
    """
    settings = get_settings()
    if not x_timestamp or not x_signature:
        raise SignatureInvalidError("Missing X-Timestamp or X-Signature header.")
    try:
        ts = int(x_timestamp)
    except ValueError as exc:
        raise SignatureInvalidError("X-Timestamp must be unix seconds.") from exc
    if abs(time.time() - ts) > settings.signature_tolerance_seconds:
        raise SignatureExpiredError()

    expected = compute_signature(settings.ingest_signing_secret, x_timestamp, await request.body())
    if not hmac.compare_digest(expected, x_signature.strip().lower()):
        raise SignatureInvalidError("Signature mismatch.")

    try:
        first_use = await redis.set(
            SIGNATURE_SEEN_KEY.format(signature=expected),
            "1",
            nx=True,
            ex=settings.signature_tolerance_seconds * 2,
        )
    except RedisError as exc:
        logger.warning("Replay check skipped (Redis unavailable): %s", exc)
        return
    if not first_use:
        raise DuplicateRequestError()


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
ServiceSignature = Annotated[None, Depends(verify_service_signature)]
