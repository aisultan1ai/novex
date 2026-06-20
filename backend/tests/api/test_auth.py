from __future__ import annotations

from unittest.mock import patch

import pytest

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
            json={"email": "new@example.com", "password": "securepass1"},
            headers={"X-Real-IP": "10.0.0.1"},
        )
    assert r.status_code == 201
    assert r.json()["email"] == "new@example.com"
    assert r.json()["role"] == "customer"


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
