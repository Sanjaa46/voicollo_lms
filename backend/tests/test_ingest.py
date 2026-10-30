import time
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import select

from app.core import database
from app.models import ApplicationLog, AuditLog
from tests.conftest import app_log, audit_log, signed


async def test_app_log_created(client):
    resp = await client.post("/api/v1/logs/app", **signed(app_log()))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["log_id"] >= 1
    assert body["ingested_at"].endswith("Z")


async def test_offset_timestamp_is_stored_as_utc(client):
    local = datetime(2026, 1, 1, 10, 0, tzinfo=timezone(timedelta(hours=8)))
    resp = await client.post("/api/v1/logs/app", **signed(app_log(created_at=local.isoformat())))
    assert resp.status_code == 201
    async with database.session_scope() as s:
        row = await s.scalar(select(ApplicationLog))
    assert row.created_at == datetime(2026, 1, 1, 2, 0)


async def test_level_aliases_accepted(client):
    resp = await client.post("/api/v1/logs/app", **signed(app_log(level="warning")))
    assert resp.status_code == 201
    async with database.session_scope() as s:
        assert (await s.scalar(select(ApplicationLog.level))) == "WARN"


async def test_missing_signature_rejected(client):
    resp = await client.post("/api/v1/logs/app", json=app_log())
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "SIGNATURE_INVALID"


async def test_wrong_secret_rejected(client):
    resp = await client.post("/api/v1/logs/app", **signed(app_log(), secret="nope-nope-nope-nope"))
    assert resp.status_code == 401


async def test_expired_timestamp_rejected(client):
    resp = await client.post("/api/v1/logs/app", **signed(app_log(), ts=int(time.time()) - 3600))
    assert resp.json()["error_code"] == "SIGNATURE_EXPIRED"


async def test_replay_rejected(client):
    req = signed(app_log())
    assert (await client.post("/api/v1/logs/app", **req)).status_code == 201
    replay = await client.post("/api/v1/logs/app", **req)
    assert replay.status_code == 409
    assert replay.json()["error_code"] == "DUPLICATE_REQUEST"


async def test_unknown_and_disabled_services(client):
    unknown = await client.post("/api/v1/logs/app", **signed(app_log(source_service="ghost")))
    assert unknown.status_code == 422
    assert unknown.json()["error_code"] == "SERVICE_NOT_REGISTERED"
    disabled = await client.post("/api/v1/logs/app", **signed(app_log(source_service="old-svc")))
    assert disabled.status_code == 403
    assert disabled.json()["error_code"] == "SERVICE_DISABLED"


async def test_far_future_timestamp_rejected(client):
    future = datetime.now(UTC) + timedelta(days=3)
    resp = await client.post("/api/v1/logs/app", **signed(app_log(created_at=future.isoformat())))
    assert resp.status_code == 422


async def test_audit_log_stores_environment(client):
    resp = await client.post("/api/v1/logs/audit", **signed(audit_log(action="record delete")))
    assert resp.status_code == 422  # spaces not allowed in action
    resp = await client.post("/api/v1/logs/audit", **signed(audit_log(action="record_delete")))
    assert resp.status_code == 201
    async with database.session_scope() as s:
        row = await s.scalar(select(AuditLog))
    assert row.environment == "production"
    assert row.action == "RECORD_DELETE"


async def test_audit_invalid_ip_rejected(client):
    resp = await client.post("/api/v1/logs/audit", **signed(audit_log(ip_address="999.1.1.1")))
    assert resp.status_code == 422


async def test_batch_partial_success(client):
    batch = {
        "logs": [
            app_log(message="ok 1"),
            app_log(level="LOUD"),  # invalid level
            app_log(source_service="ghost"),
            app_log(source_service="old-svc"),
            app_log(message="ok 2"),
        ]
    }
    resp = await client.post("/api/v1/logs/app/batch", **signed(batch))
    assert resp.status_code == 207
    body = resp.json()
    assert (body["total"], body["succeeded"], body["failed"]) == (5, 2, 3)
    codes = [r["error_code"] for r in body["results"]]
    assert codes == [None, "VALIDATION_ERROR", "SERVICE_NOT_REGISTERED", "SERVICE_DISABLED", None]
    assert all(r["log_id"] for r in body["results"] if r["success"])


async def test_batch_rate_limit_counts_every_entry(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_max", 3)
    batch = {"logs": [app_log(message=f"m{i}") for i in range(4)]}
    resp = await client.post("/api/v1/logs/app/batch", **signed(batch))
    assert resp.status_code == 429
    assert resp.headers["Retry-After"]


async def test_audit_delete_not_allowed(client):
    resp = await client.delete("/api/v1/logs/audit/1")
    assert resp.status_code == 405
