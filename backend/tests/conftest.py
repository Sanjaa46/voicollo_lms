import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.main import create_app
from app.core.dependencies import get_db, get_current_user, get_redis, verify_service_signature
from app.core.auth import AuthenticatedUser

FAKE_INGEST_SIGNING_SECRET = "fake_ingest_signing_secret"

def fake_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        github_username="sanjmyat4v",
        jti="test_jti_12345",
    )

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=True)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.ttl = AsyncMock(return_value=60)
    redis.scan = AsyncMock(return_value=(0, []))
    redis.ping = AsyncMock(return_value=True)

    # Pipe mock
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.get = AsyncMock()
    pipe.set = AsyncMock()
    pipe.incr = AsyncMock()
    pipe.expire = AsyncMock()
    pipe.ttl = AsyncMock()
    pipe.execute = AsyncMock(return_value=[None, 60])
    redis.pipeline = AsyncMock(return_value=pipe)

    return redis


# Fake DB
@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Test app with all real dependencies replaced
# ---------------------------------------------------------------------------
@pytest.fixture
def app(mock_db, mock_redis) -> FastAPI:
    application = create_app()

    # Replace real DB with mock
    application.dependency_overrides[get_db] = lambda: mock_db

    # Replace real Redis with mock
    application.dependency_overrides[get_redis] = lambda: mock_redis

    # Replace GitHub OAuth with a fake logged-in user
    application.dependency_overrides[get_current_user] = fake_user

    application.dependency_overrides[verify_service_signature] = lambda: None

    return application


# ---------------------------------------------------------------------------
# Async HTTP test client
# ---------------------------------------------------------------------------
@pytest.fixture
async def client(app) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Reusable sample payloads
# ---------------------------------------------------------------------------
@pytest.fixture
def app_log_payload():
    return {
        "source_service": "test-service",
        "level": "INFO",
        "message": "Test log message",
        "environment": "production",
        "created_at": "2025-06-11T06:30:00.000Z",
    }


@pytest.fixture
def audit_log_payload():
    return {
        "source_service": "test-service",
        "environment": "production",
        "actor_id": "user-123",
        "actor_type": "USER",
        "action": "RECORD_DELETE",
        "target_resource": "/api/records/42",
        "outcome": "SUCCESS",
        "event_time": "2025-06-11T06:30:00.000Z",
    }