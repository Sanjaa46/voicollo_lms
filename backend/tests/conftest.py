import os

os.environ.update(
    {
        "APP_ENV": "test",
        "APP_VERSION": "9.9.9-test",
        "GITHUB_CLIENT_ID": "test-client",
        "GITHUB_CLIENT_SECRET": "test-secret",
        "ALLOWED_GITHUB_USERNAME": "Owner",
        "JWT_SECRET_KEY": "x" * 48,
        "INGEST_SIGNING_SECRET": "ingest-secret-for-tests",
        "DATABASE_URL": "sqlite+aiosqlite://",
        "RETENTION_DATABASE_URL": "sqlite+aiosqlite://",
        "SERVE_FRONTEND": "false",
        "RETENTION_ENABLED": "false",
        "RATE_LIMIT_MAX": "1000",
        "PUBLIC_URL": "http://testserver",
    }
)

import json  # noqa: E402
import time  # noqa: E402
from datetime import UTC, datetime  # noqa: E402

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core import database  # noqa: E402
from app.core.dependencies import compute_signature  # noqa: E402
from app.core.redis import set_redis_client  # noqa: E402
from app.core.security import _issue_pair  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, Service  # noqa: E402

SIGNING_SECRET = os.environ["INGEST_SIGNING_SECRET"]


def _sqlite_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # pysqlite needs manual BEGIN for SAVEPOINT support (SQLAlchemy docs recipe).
    @event.listens_for(engine.sync_engine, "connect")
    def _connect(dbapi_conn, _):
        dbapi_conn.isolation_level = None

    @event.listens_for(engine.sync_engine, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN")

    return engine


@pytest.fixture
async def engine():
    eng = _sqlite_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    database.set_engines(eng)
    async with database.session_scope() as session:
        session.add_all(
            [
                Service(id="lms-system", name="LMS System"),
                Service(id="billing", name="Billing"),
                Service(id="auth-svc", name="Auth"),
                Service(id="old-svc", name="Old", is_active=False),
            ]
        )
    yield eng
    await eng.dispose()


@pytest.fixture
async def redis():
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    set_redis_client(client)
    yield client
    await client.aclose()


@pytest.fixture
async def client(engine, redis):
    app = create_app(with_lifespan=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
async def auth_headers(redis):
    pair = await _issue_pair(redis, "Owner")
    return {"Authorization": f"Bearer {pair.access_token}"}


def signed(payload, *, secret: str = SIGNING_SECRET, ts: int | None = None):
    body = json.dumps(payload).encode()
    stamp = str(ts if ts is not None else int(time.time()))
    return {
        "content": body,
        "headers": {
            "Content-Type": "application/json",
            "X-Timestamp": stamp,
            "X-Signature": compute_signature(secret, stamp, body),
        },
    }


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def app_log(**overrides):
    entry = {
        "source_service": "billing",
        "level": "INFO",
        "message": "payment processed",
        "environment": "production",
        "created_at": iso(datetime.now(UTC)),
    }
    entry.update(overrides)
    return entry


def audit_log(**overrides):
    entry = {
        "source_service": "auth-svc",
        "environment": "production",
        "actor_id": "user-1",
        "actor_type": "USER",
        "action": "USER_LOGIN",
        "target_resource": "/login",
        "outcome": "SUCCESS",
        "event_time": iso(datetime.now(UTC)),
        "ip_address": "10.0.0.1",
    }
    entry.update(overrides)
    return entry
