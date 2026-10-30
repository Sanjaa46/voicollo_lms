from datetime import UTC, datetime, timedelta

from tests.conftest import app_log, audit_log, iso, signed

BASE = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


async def _seed(client):
    # 6 app logs and 4 audit logs, interleaved one minute apart.
    for i in range(10):
        ts = iso(BASE + timedelta(minutes=i))
        if i % 5 in (1, 3):
            payload = audit_log(event_time=ts, actor_id=f"user-{i}")
            assert (await client.post("/api/v1/logs/audit", **signed(payload))).status_code == 201
        else:
            level = "ERROR" if i == 4 else "INFO"
            payload = app_log(created_at=ts, level=level, message=f"msg {i}", trace_id=f"t{i % 2}")
            assert (await client.post("/api/v1/logs/app", **signed(payload))).status_code == 201


def _times(body):
    return [entry["timestamp"] for entry in body["data"]]


async def test_both_types_paginate_globally(client, auth_headers):
    await _seed(client)
    seen = []
    for page in (1, 2, 3, 4):
        resp = await client.get(
            "/api/v1/logs", params={"page": page, "page_size": 3}, headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 10
        seen.extend(_times(body))
        assert body["has_next"] == (page < 4)
    assert len(seen) == 10
    assert seen == sorted(seen, reverse=True)  # global DESC ordering, no gaps/dupes
    assert len(set(seen)) == 10


async def test_ascending_sort(client, auth_headers):
    await _seed(client)
    resp = await client.get("/api/v1/logs", params={"sort": "asc"}, headers=auth_headers)
    times = _times(resp.json())
    assert times == sorted(times)


async def test_level_filter_narrows_to_app_logs(client, auth_headers):
    await _seed(client)
    resp = await client.get("/api/v1/logs", params={"level": "ERROR"}, headers=auth_headers)
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["log_type"] == "app"


async def test_csv_level_filter_and_trace(client, auth_headers):
    await _seed(client)
    resp = await client.get(
        "/api/v1/logs", params={"level": "ERROR,INFO", "trace_id": "t0"}, headers=auth_headers
    )
    assert {e["trace_id"] for e in resp.json()["data"]} == {"t0"}


async def test_actor_filter_narrows_to_audit(client, auth_headers):
    await _seed(client)
    resp = await client.get("/api/v1/logs", params={"actor_id": "user-3"}, headers=auth_headers)
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["log_type"] == "audit"


async def test_time_range_and_search(client, auth_headers):
    await _seed(client)
    params = {
        "start_time": iso(BASE + timedelta(minutes=2)),
        "end_time": iso(BASE + timedelta(minutes=6)),
        "log_type": "app",
    }
    resp = await client.get("/api/v1/logs", params=params, headers=auth_headers)
    assert [e["message"] for e in resp.json()["data"]] == ["msg 5", "msg 4", "msg 2"]

    resp = await client.get("/api/v1/logs", params={"q": "msg 9"}, headers=auth_headers)
    assert resp.json()["total"] == 1


async def test_search_escapes_wildcards(client, auth_headers):
    await _seed(client)
    resp = await client.get("/api/v1/logs", params={"q": "%"}, headers=auth_headers)
    assert resp.json()["total"] == 0


async def test_invalid_range_rejected(client, auth_headers):
    resp = await client.get(
        "/api/v1/logs",
        params={"start_time": iso(BASE), "end_time": iso(BASE - timedelta(hours=1))},
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_cache_invalidated_by_writes(client, auth_headers):
    await _seed(client)
    first = await client.get("/api/v1/logs", headers=auth_headers)
    assert first.headers["X-Cache"] == "MISS"
    again = await client.get("/api/v1/logs", headers=auth_headers)
    assert again.headers["X-Cache"] == "HIT"
    await client.post("/api/v1/logs/app", **signed(app_log(message="new")))
    after = await client.get("/api/v1/logs", headers=auth_headers)
    assert after.headers["X-Cache"] == "MISS"
    assert after.json()["total"] == 11


async def test_get_single_log(client, auth_headers):
    created = await client.post("/api/v1/logs/app", **signed(app_log()))
    log_id = created.json()["log_id"]
    resp = await client.get(f"/api/v1/logs/app/{log_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == log_id
    missing = await client.get("/api/v1/logs/audit/999", headers=auth_headers)
    assert missing.status_code == 404
    assert missing.json()["error_code"] == "LOG_NOT_FOUND"


async def test_query_requires_auth(client):
    resp = await client.get("/api/v1/logs")
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "AUTH_TOKEN_MISSING"


async def test_export_csv_and_json(client, auth_headers):
    await _seed(client)
    await client.post("/api/v1/logs/app", **signed(app_log(message="=cmd()")))
    csv_resp = await client.get(
        "/api/v1/logs/export", params={"format": "csv"}, headers=auth_headers
    )
    assert csv_resp.status_code == 200
    lines = csv_resp.text.strip().splitlines()
    assert lines[0].startswith("log_type,id,timestamp")
    assert len(lines) == 12
    assert "'=cmd()" in csv_resp.text  # formula injection neutralised

    json_resp = await client.get(
        "/api/v1/logs/export", params={"format": "json", "limit": 5}, headers=auth_headers
    )
    doc = json_resp.json()
    assert doc["exported"] == 5 and doc["total_matching"] == 11 and doc["truncated"] is True
