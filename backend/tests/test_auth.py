import jwt
import pytest

from app.core import security
from app.core.config import get_settings


async def test_login_url_is_encoded(client, redis):
    resp = await client.get("/api/v1/auth/login")
    url = resp.json()["authorization_url"]
    assert "redirect_uri=http%3A%2F%2Ftestserver%2Fauth%2Fcallback" in url
    assert "scope=read%3Auser" in url


async def test_me_and_logout_revokes_access_token(client, auth_headers):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.json() == {"username": "Owner"}
    assert (await client.post("/api/v1/auth/logout", headers=auth_headers)).status_code == 204
    after = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert after.status_code == 401


async def test_refresh_rotation_single_use(client, redis):
    pair = await security._issue_pair(redis, "Owner")
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": pair.refresh_token})
    assert resp.status_code == 200
    new = resp.json()
    assert new["refresh_token"] != pair.refresh_token and new["username"] == "Owner"
    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": pair.refresh_token})
    assert reuse.status_code == 401


async def test_refresh_accepts_legacy_jti_field(client, redis):
    pair = await security._issue_pair(redis, "Owner")
    jti, secret = pair.refresh_token.split(".", 1)
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": secret, "jti": jti})
    assert resp.status_code == 200


async def test_refresh_accepts_v1_stored_format(client, redis):
    await redis.set(security.REFRESH_KEY.format(jti="legacy"), "Owner:oldsecret")
    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "oldsecret", "jti": "legacy"}
    )
    assert resp.status_code == 200


async def test_wrong_secret_token_rejected(client):
    token = jwt.encode(
        {"sub": "Owner", "jti": "a", "type": "access", "iss": "voicollo-lms", "iat": 1, "exp": 9e9},
        "y" * 48,
        algorithm="HS256",
    )
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_token_for_other_user_rejected(client):
    token, _ = security._create_access_token("intruder", "jti1")
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_callback_rejects_other_github_user(client, redis, monkeypatch):
    url = (await client.get("/api/v1/auth/login")).json()["authorization_url"]
    state = url.split("state=")[1].split("&")[0]

    async def fake_identity(code):
        return "someone-else", 42

    monkeypatch.setattr(security, "_github_identity", fake_identity)
    resp = await client.post("/api/v1/auth/callback", json={"code": "c", "state": state})
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "AUTH_USER_NOT_ALLOWED"


async def test_callback_success_and_state_single_use(client, monkeypatch):
    url = (await client.get("/api/v1/auth/login")).json()["authorization_url"]
    state = url.split("state=")[1].split("&")[0]

    async def fake_identity(code):
        return "owner", 7  # case-insensitive match

    monkeypatch.setattr(security, "_github_identity", fake_identity)
    ok = await client.post("/api/v1/auth/callback", json={"code": "c", "state": state})
    assert ok.status_code == 200
    assert ok.json()["expires_in"] == get_settings().access_token_expire_minutes * 60
    again = await client.post("/api/v1/auth/callback", json={"code": "c", "state": state})
    assert again.status_code == 401


def test_settings_require_strong_jwt_secret(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("JWT_SECRET_KEY", "short")
    with pytest.raises(ValueError):
        Settings()
