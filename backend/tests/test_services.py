from tests.conftest import app_log, signed


async def test_list_with_activity(client, auth_headers):
    await client.post("/api/v1/logs/app", **signed(app_log(level="ERROR")))
    resp = await client.get("/api/v1/services", headers=auth_headers)
    body = resp.json()
    assert body["total"] == 4
    billing = next(s for s in body["data"] if s["id"] == "billing")
    assert billing["activity"]["app_logs_24h"] == 1
    assert billing["activity"]["errors_24h"] == 1
    assert billing["activity"]["last_seen_at"].endswith("Z")
    system = next(s for s in body["data"] if s["id"] == "lms-system")
    assert system["is_protected"] is True


async def test_filters_combine_with_and(client, auth_headers):
    resp = await client.get(
        "/api/v1/services", params={"q": "bill", "status": "disabled"}, headers=auth_headers
    )
    assert resp.json()["total"] == 0
    resp = await client.get("/api/v1/services", params={"q": "bill"}, headers=auth_headers)
    assert [s["id"] for s in resp.json()["data"]] == ["billing"]


async def test_create_validate_and_conflict(client, auth_headers):
    bad = await client.post(
        "/api/v1/services", json={"id": "Bad Id!", "name": "x"}, headers=auth_headers
    )
    assert bad.status_code == 422
    ok = await client.post(
        "/api/v1/services", json={"id": "New-API", "name": " New API "}, headers=auth_headers
    )
    assert ok.status_code == 201
    assert ok.json()["id"] == "new-api" and ok.json()["name"] == "New API"
    dup = await client.post(
        "/api/v1/services", json={"id": "new-api", "name": "x"}, headers=auth_headers
    )
    assert dup.status_code == 409


async def test_update_and_toggle(client, auth_headers):
    resp = await client.patch(
        "/api/v1/services/billing", json={"description": "Payments"}, headers=auth_headers
    )
    assert resp.json()["description"] == "Payments"

    # Ingest allowed, then disabled takes effect immediately (cache cleared).
    assert (await client.post("/api/v1/logs/app", **signed(app_log()))).status_code == 201
    off = await client.post("/api/v1/services/billing/disable", headers=auth_headers)
    assert off.json()["is_active"] is False
    again = await client.post("/api/v1/services/billing/disable", headers=auth_headers)
    assert again.status_code == 200  # idempotent
    blocked = await client.post("/api/v1/logs/app", **signed(app_log(message="x")))
    assert blocked.status_code == 403
    on = await client.patch("/api/v1/services/billing/enable", headers=auth_headers)
    assert on.json()["is_active"] is True


async def test_system_service_cannot_be_disabled(client, auth_headers):
    resp = await client.post("/api/v1/services/lms-system/disable", headers=auth_headers)
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "SERVICE_PROTECTED"


async def test_unknown_service_404(client, auth_headers):
    resp = await client.get("/api/v1/services/nope", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "SERVICE_NOT_FOUND"
