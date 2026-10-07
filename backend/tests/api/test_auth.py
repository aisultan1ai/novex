from __future__ import annotations

from unittest.mock import patch

from app.core.exceptions import UnauthorizedError
from tests.api.conftest import make_profile, make_token, make_token_response

# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


def test_register_returns_201(client):
    mock_profile = make_profile(email="new@example.com")
    with patch("app.api.v1.auth.identity_service.register_user", return_value=mock_profile):
        r = client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com", "password": "securepass1",
                "tax_id": "990101300123", "pd_consent": True,
            },
            headers={"X-Real-IP": "10.0.0.1"},
        )
    assert r.status_code == 201
    assert r.json()["email"] == "new@example.com"
    assert r.json()["role"] == "customer"


def test_register_requires_pd_consent(client):
    """KZ personal-data law: no account without consent (audit T10)."""
    with patch("app.api.v1.auth.identity_service.register_user") as register:
        r = client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "securepass1", "tax_id": "990101300123"},
            headers={"X-Real-IP": "10.0.0.2"},
        )
    assert r.status_code == 422
    assert "согласие" in r.text
    register.assert_not_called()


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


def test_login_returns_200_with_token(client):
    profile = make_profile(email="login@example.com")
    token_resp = make_token_response(profile)
    with patch(
        "app.api.v1.auth.identity_service.authenticate_user",
        return_value=token_resp,
    ):
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "securepass1"},
            headers={"X-Real-IP": "10.0.0.2"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["profile"]["email"] == "login@example.com"


def test_login_wrong_password_returns_401(client):
    with patch(
        "app.api.v1.auth.identity_service.authenticate_user",
        side_effect=UnauthorizedError("Invalid email or password"),
    ):
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "wrongpass"},
            headers={"X-Real-IP": "10.0.0.3"},
        )
    assert r.status_code == 401
    assert "Invalid" in r.json()["detail"]


# ---------------------------------------------------------------------------
# GET /auth/profile
# ---------------------------------------------------------------------------


def test_profile_with_valid_token_returns_200(client):
    token = make_token(user_id=1, role="customer")
    profile = make_profile(user_id=1, email="me@example.com")
    with patch("app.api.v1.auth.identity_service.get_profile", return_value=profile):
        r = client.get(
            "/api/v1/auth/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    assert r.json()["email"] == "me@example.com"
    assert r.json()["user_id"] == 1


def test_profile_without_token_returns_401(client):
    r = client.get("/api/v1/auth/profile")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Session cookie hygiene (audit 2026-10-08)
# ---------------------------------------------------------------------------


def _access_cookies(response) -> list[str]:
    return [c for c in response.headers.get_list("set-cookie") if c.startswith("access_token=")]


def test_login_expires_legacy_host_only_cookie_before_setting_shared_one(client, monkeypatch):
    """A stale host-only `access_token` (set before the `.domain` cookie existed)
    must not shadow the fresh token: login expires it, then sets the shared one."""
    import app.api.v1.auth as auth_api

    monkeypatch.setattr(auth_api, "_access_cookie_domain", lambda: ".novex.kz")
    profile = make_profile(email="login@example.com")
    with patch(
        "app.api.v1.auth.identity_service.authenticate_user",
        return_value=make_token_response(profile),
    ):
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "securepass1"},
            headers={"X-Real-IP": "10.0.0.7"},
        )

    assert r.status_code == 200
    cookies = _access_cookies(r)
    assert len(cookies) == 2
    expired, fresh = cookies
    assert "Max-Age=0" in expired and "Domain" not in expired      # legacy host-only → expired first
    assert "Domain=.novex.kz" in fresh and "HttpOnly" in fresh     # then the real one


def test_logout_clears_both_cookie_variants(client, monkeypatch):
    import app.api.v1.auth as auth_api

    monkeypatch.setattr(auth_api, "_access_cookie_domain", lambda: ".novex.kz")
    r = client.post("/api/v1/auth/logout", headers={"X-Real-IP": "10.0.0.8"})

    assert r.status_code == 200
    cookies = _access_cookies(r)
    assert any("Domain=.novex.kz" in c for c in cookies)
    assert any("Domain" not in c for c in cookies)
    assert all("Max-Age=0" in c for c in cookies)
