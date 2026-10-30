"""GitHub OAuth single-user authentication and session tokens.

Flow (unchanged from v1):
  1. GET  /auth/login     -> GitHub authorize URL (state stored in Redis, 10 min)
  2. GitHub redirects the browser to PUBLIC_URL/auth/callback?code&state
  3. POST /auth/callback  -> code exchanged, GitHub user checked against
                             ALLOWED_GITHUB_USERNAME (and optional user id),
                             then our own token pair is issued.
  4. POST /auth/refresh   -> refresh-token rotation
  5. POST /auth/logout    -> refresh token deleted, access token revoked

Tokens:
  * access token  — HS256 JWT {sub, jti, type="access", iss, iat, exp}
  * refresh token — opaque "<jti>.<secret>". Redis stores only sha256(secret).
"""

import hashlib
import hmac
import json
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import jwt
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.exceptions import (
    AuthProviderError,
    AuthTokenInvalidError,
    AuthTokenMissingError,
    AuthUserNotAllowedError,
)

logger = logging.getLogger(__name__)

TOKEN_ISSUER = "voicollo-lms"
REFRESH_KEY = "lms:auth:refresh:{jti}"
REVOKED_KEY = "lms:auth:revoked:{jti}"
STATE_KEY = "lms:auth:state:{state}"
STATE_TTL_SECONDS = 600

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


@dataclass(frozen=True)
class AuthenticatedUser:
    github_username: str
    jti: str


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    username: str
    expires_in: int


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# --------------------------------------------------------------------- OAuth
async def build_authorization_url(redis: Redis) -> str:
    settings = get_settings()
    state = secrets.token_urlsafe(32)
    await redis.set(STATE_KEY.format(state=state), "1", ex=STATE_TTL_SECONDS)
    query = urlencode(
        {
            "client_id": settings.github_client_id,
            "redirect_uri": settings.oauth_redirect_uri,
            "scope": "read:user",
            "state": state,
            "allow_signup": "false",
        }
    )
    return f"{GITHUB_AUTHORIZE_URL}?{query}"


async def _consume_state(redis: Redis, state: str) -> None:
    try:
        deleted = await redis.delete(STATE_KEY.format(state=state))
    except RedisError as exc:
        logger.error("Redis unavailable while verifying OAuth state: %s", exc)
        raise AuthTokenInvalidError("Could not verify login state. Please retry.") from exc
    if not deleted:
        raise AuthTokenInvalidError("Login link expired or already used. Please sign in again.")


async def _github_identity(code: str) -> tuple[str, int]:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": settings.oauth_redirect_uri,
                },
            )
            token_data = token_resp.json() if token_resp.status_code == 200 else {}
            github_token = token_data.get("access_token")
            if not github_token:
                reason = token_data.get("error_description") or token_data.get("error")
                raise AuthTokenInvalidError(
                    f"GitHub rejected the authorization code{f': {reason}' if reason else ''}."
                )
            user_resp = await client.get(
                GITHUB_USER_URL,
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
    except httpx.HTTPError as exc:
        raise AuthProviderError("GitHub is unreachable. Please retry.") from exc

    if user_resp.status_code != 200:
        raise AuthProviderError(f"GitHub user lookup failed (HTTP {user_resp.status_code}).")
    data = user_resp.json()
    if not data.get("login"):
        raise AuthProviderError("GitHub did not return a username.")
    return data["login"], int(data.get("id") or 0)


def _assert_allowed(username: str, user_id: int | None = None) -> None:
    settings = get_settings()
    if username.lower() != settings.allowed_github_username.lower():
        logger.warning("Rejected login for GitHub user %r", username)
        raise AuthUserNotAllowedError(username)
    if (
        user_id is not None
        and settings.allowed_github_user_id is not None
        and user_id != settings.allowed_github_user_id
    ):
        logger.warning("Rejected login: GitHub id %s does not match configured id", user_id)
        raise AuthUserNotAllowedError(username)


async def complete_login(code: str, state: str, redis: Redis) -> TokenPair:
    await _consume_state(redis, state)
    username, user_id = await _github_identity(code)
    _assert_allowed(username, user_id)
    logger.info("GitHub login succeeded for %s", username)
    return await _issue_pair(redis, username)


# --------------------------------------------------------------------- tokens
def _create_access_token(username: str, jti: str) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(UTC)
    ttl = settings.access_token_expire_minutes * 60
    payload = {
        "sub": username,
        "jti": jti,
        "type": "access",
        "iss": TOKEN_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256"), ttl


async def _issue_pair(redis: Redis, username: str) -> TokenPair:
    settings = get_settings()
    jti = uuid.uuid4().hex
    secret = secrets.token_urlsafe(48)
    record = json.dumps({"sub": username, "hash": _hash(secret)})
    try:
        await redis.set(
            REFRESH_KEY.format(jti=jti), record, ex=settings.refresh_token_expire_days * 86400
        )
    except RedisError as exc:
        logger.error("Could not store refresh token: %s", exc)
        raise AuthTokenInvalidError("Could not create a session. Please retry.") from exc
    access, ttl = _create_access_token(username, jti)
    return TokenPair(access, f"{jti}.{secret}", username, ttl)


def _split_refresh_token(refresh_token: str, jti: str | None) -> tuple[str, str]:
    # v2 format "<jti>.<secret>"; v1 clients sent an opaque secret plus a separate jti.
    if jti is None and "." in refresh_token:
        token_jti, secret = refresh_token.split(".", 1)
        return token_jti, secret
    if jti is None:
        raise AuthTokenInvalidError("Malformed refresh token.")
    if refresh_token.startswith(f"{jti}."):
        return jti, refresh_token.split(".", 1)[1]
    return jti, refresh_token


def _parse_record(raw: str) -> tuple[str, str]:
    """Return (username, secret_hash). Handles the v1 'username:secret' format."""
    if raw.startswith("{"):
        data = json.loads(raw)
        return data["sub"], data["hash"]
    username, _, secret = raw.partition(":")
    return username, _hash(secret)


async def rotate_refresh_token(redis: Redis, refresh_token: str, jti: str | None) -> TokenPair:
    token_jti, secret = _split_refresh_token(refresh_token, jti)
    key = REFRESH_KEY.format(jti=token_jti)
    try:
        # GETDEL makes rotation atomic: a token can be exchanged exactly once.
        raw = await redis.getdel(key)
    except RedisError as exc:
        raise AuthTokenInvalidError("Session store unavailable. Please sign in again.") from exc
    if not raw:
        raise AuthTokenInvalidError("Session expired or revoked. Please sign in again.")

    username, expected_hash = _parse_record(raw)
    if not hmac.compare_digest(expected_hash, _hash(secret)):
        logger.warning("Refresh token mismatch for jti=%s; session revoked", token_jti)
        raise AuthTokenInvalidError("Invalid refresh token. Please sign in again.")
    _assert_allowed(username)
    return await _issue_pair(redis, username)


async def revoke_session(redis: Redis, jti: str) -> None:
    settings = get_settings()
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.delete(REFRESH_KEY.format(jti=jti))
            pipe.set(REVOKED_KEY.format(jti=jti), "1", ex=settings.access_token_expire_minutes * 60)
            await pipe.execute()
    except RedisError as exc:
        logger.warning("Failed to revoke session %s: %s", jti, exc)


def decode_access_token(token: str) -> AuthenticatedUser:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=["HS256"],
            issuer=TOKEN_ISSUER,
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthTokenInvalidError("Access token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthTokenInvalidError("Access token is invalid.") from exc
    if payload.get("type") != "access":
        raise AuthTokenInvalidError("Token is not an access token.")
    # Changing ALLOWED_GITHUB_USERNAME immediately invalidates old sessions.
    if payload["sub"].lower() != settings.allowed_github_username.lower():
        raise AuthTokenInvalidError("Session belongs to a user that is no longer allowed.")
    return AuthenticatedUser(github_username=payload["sub"], jti=payload["jti"])


async def is_revoked(redis: Redis, jti: str) -> bool:
    try:
        return bool(await redis.exists(REVOKED_KEY.format(jti=jti)))
    except RedisError as exc:
        logger.warning("Revocation check skipped (Redis unavailable): %s", exc)
        return False


def parse_bearer(header: str | None) -> str:
    if not header:
        raise AuthTokenMissingError()
    scheme, _, token = header.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthTokenInvalidError("Authorization header must be 'Bearer <token>'.")
    return token.strip()
