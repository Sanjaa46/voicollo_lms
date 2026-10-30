from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core import database
from app.models import ApplicationLog, AuditLog
from tests.conftest import app_log, audit_log, iso, signed


async def test_health_and_version_public(client):
    health = await client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"
    version = await client.get("/api/v1/version")
    assert version.json()["version"] == "9.9.9-test"


async def test_metrics_count_errors(client, auth_headers):
    await client.get("/api/v1/logs")  # 401
    await client.post("/api/v1/logs/app", **signed(app_log()))
    metrics = (await client.get("/api/v1/metrics", headers=auth_headers)).json()
    assert metrics["ingestion_total"] == 1
    assert metrics["error_total"]["AUTH_TOKEN_MISSING"] == 1


async def test_stats_overview(client, auth_headers):
    now = datetime.now(UTC)
    for level in ("INFO", "INFO", "ERROR", "FATAL"):
        await client.post(
            "/api/v1/logs/app", **signed(app_log(level=level, message=level + str(now)))
        )
    await client.post("/api/v1/logs/audit", **signed(audit_log(outcome="FAILURE")))
    resp = await client.get("/api/v1/stats/overview", params={"hours": 6}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["levels"]["INFO"] == 2 and body["totals"]["errors"] == 2
    assert body["outcomes"]["FAILURE"] == 1
    assert body["error_rate"] == 0.5
    assert body["bucket_seconds"] == 300
    assert sum(b["info"] + b["error"] + b["fatal"] for b in body["timeline"]) == 4
    assert sum(b["audit"] for b in body["timeline"]) == 1
    assert body["top_services"][0]["source_service"] == "billing"
    assert len(body["recent_errors"]) == 2


async def test_manual_retention_purges_and_self_logs(client, auth_headers):
    old = datetime.now(UTC) - timedelta(days=200)
    async with database.session_scope() as s:
        s.add(
            ApplicationLog(
                source_service="billing",
                level="INFO",
                message="ancient",
                environment="production",
                created_at=old.replace(tzinfo=None),
            )
        )
        s.add(
            AuditLog(
                source_service="auth-svc",
                actor_id="u",
                actor_type="USER",
                action="X",
                target_resource="y",
                outcome="SUCCESS",
                event_time=old.replace(tzinfo=None),
                ingested_at=(old - timedelta(days=400)).replace(tzinfo=None),
            )
        )
    await client.post("/api/v1/logs/app", **signed(app_log()))

    run = await client.post("/api/v1/retention/run", headers=auth_headers)
    assert run.status_code == 200, run.text
    body = run.json()
    assert (body["status"], body["deleted_app_logs"], body["deleted_audit_logs"]) == (
        "SUCCESS",
        1,
        1,
    )
    async with database.session_scope() as s:
        messages = (await s.scalars(select(ApplicationLog.message))).all()
        assert await s.scalar(select(func.count()).select_from(AuditLog)) == 0
    assert any(m.startswith("Retention success") for m in messages)

    status = (await client.get("/api/v1/retention", headers=auth_headers)).json()
    assert status["last_run"]["trigger"] == "manual"


async def test_retention_lock_prevents_parallel_runs(client, auth_headers, redis):
    await redis.set("lms:lock:retention", "other-worker")
    resp = await client.post("/api/v1/retention/run", headers=auth_headers)
    assert resp.status_code == 409


async def test_system_status(client, auth_headers):
    resp = await client.get("/api/v1/system/status", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["retention"]["policy"]["app_log_retention_days"] == 90


async def test_request_id_sanitised(client):
    resp = await client.get("/api/v1/version", headers={"X-Request-ID": "bad id\nwith newline"})
    assert resp.headers["X-Request-ID"] != "bad id\nwith newline"
    good = await client.get("/api/v1/version", headers={"X-Request-ID": "trace-123"})
    assert good.headers["X-Request-ID"] == "trace-123"


async def test_timestamps_round_trip_as_utc(client, auth_headers):
    ts = datetime(2026, 5, 5, 5, 5, 5, 123000, tzinfo=UTC)
    created = await client.post("/api/v1/logs/app", **signed(app_log(created_at=iso(ts))))
    entry = (
        await client.get(f"/api/v1/logs/app/{created.json()['log_id']}", headers=auth_headers)
    ).json()
    assert entry["created_at"] == "2026-05-05T05:05:05.123Z"
