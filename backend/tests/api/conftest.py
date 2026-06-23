from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.core.redis as _redis_module
from app.core.db import get_async_db, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.identity.models import RoleCode
from app.modules.identity.schemas import ProfileResponse, TokenResponse

# ---------------------------------------------------------------------------
# Redis mock — applied to every API test so get_redis() never dials real Redis
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    m = MagicMock()
    m.get.return_value = None   # token version defaults to 0, matches ver=0 in tokens
    m.setex.return_value = True
    m.set.return_value = True
    m.incr.return_value = 1
    m.delete.return_value = 1
    monkeypatch.setattr(_redis_module, "_client", m)
    return m


# ---------------------------------------------------------------------------
# Shared DB mock
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.scalar.return_value = 0   # safe default: count queries return 0
    return db


# ---------------------------------------------------------------------------
# TestClient — injects mock DB, clears dependency overrides after each test
# ---------------------------------------------------------------------------


@pytest.fixture
def client(mock_db):
    async def _async_db():
        yield mock_db

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_async_db] = _async_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def make_token(user_id: int, role: str, ver: int = 0) -> str:
    return create_access_token({"sub": str(user_id), "role": role, "ver": ver})


@pytest.fixture
def customer_token() -> str:
    return make_token(user_id=1, role="customer")


@pytest.fixture
def admin_token() -> str:
    return make_token(user_id=2, role="admin")


# ---------------------------------------------------------------------------
# Mock user objects for dependency overrides
# ---------------------------------------------------------------------------


def make_mock_user(user_id: int, role: RoleCode) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.is_active = True
    role_obj = MagicMock()
    role_obj.code = role
    user.role = role_obj
    return user


@pytest.fixture
def customer_user() -> MagicMock:
    return make_mock_user(1, RoleCode.CUSTOMER)


@pytest.fixture
def admin_user() -> MagicMock:
    return make_mock_user(2, RoleCode.ADMIN)


# ---------------------------------------------------------------------------
# Reusable ProfileResponse / TokenResponse builders
# ---------------------------------------------------------------------------


def make_profile(
    user_id: int = 1,
    email: str = "user@example.com",
    role: RoleCode = RoleCode.CUSTOMER,
) -> ProfileResponse:
    return ProfileResponse(
        user_id=user_id,
        email=email,
        full_name="Test User",
        phone=None,
        is_active=True,
        role=role,
    )


def make_token_response(profile: ProfileResponse) -> TokenResponse:
    token = make_token(profile.user_id, profile.role.value)
    return TokenResponse(access_token=token, expires_in=3600, profile=profile)
