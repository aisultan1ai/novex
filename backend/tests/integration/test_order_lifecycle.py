from __future__ import annotations

import pytest

from app.core.exceptions import UnauthorizedError
from app.modules.identity.models import RoleCode
from app.modules.identity.schemas import LoginRequest, RegisterRequest
from app.modules.identity.service import IdentityService
from tests.integration.conftest import skip_no_db

pytestmark = skip_no_db


@pytest.fixture
def identity_svc() -> IdentityService:
    return IdentityService()


# ---------------------------------------------------------------------------
# User registration
# ---------------------------------------------------------------------------


def test_register_new_user(db, identity_svc):
    profile = identity_svc.register_user(
        db,
        RegisterRequest(
            email="lifecycle_test@example.com",
            password="StrongPass123",
        ),
    )
    assert profile.user_id is not None
    assert profile.email == "lifecycle_test@example.com"
    assert profile.role == RoleCode.CUSTOMER
    assert profile.is_active is True


def test_register_duplicate_email_raises_conflict(db, identity_svc):
    from app.core.exceptions import ConflictError

    payload = RegisterRequest(email="dup@example.com", password="StrongPass123")
    identity_svc.register_user(db, payload)

    with pytest.raises(ConflictError, match="уже зарегистрирован"):
        identity_svc.register_user(db, payload)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def test_login_correct_credentials(db, identity_svc):
    identity_svc.register_user(
        db,
        RegisterRequest(email="auth@example.com", password="CorrectPass1"),
    )
    db.flush()

    token_resp = identity_svc.authenticate_user(
        db,
        LoginRequest(email="auth@example.com", password="CorrectPass1"),
    )
    assert token_resp.access_token
    assert token_resp.profile.email == "auth@example.com"
    assert token_resp.profile.role == RoleCode.CUSTOMER


def test_login_wrong_password_raises_unauthorized(db, identity_svc):
    identity_svc.register_user(
        db,
        RegisterRequest(email="badpw@example.com", password="CorrectPass1"),
    )
    db.flush()

    with pytest.raises(UnauthorizedError):
        identity_svc.authenticate_user(
            db,
            LoginRequest(email="badpw@example.com", password="WrongPass999"),
        )


def test_login_nonexistent_user_raises_unauthorized(db, identity_svc):
    with pytest.raises(UnauthorizedError):
        identity_svc.authenticate_user(
            db,
            LoginRequest(email="nobody@example.com", password="AnyPass123"),
        )


# ---------------------------------------------------------------------------
# Profile retrieval
# ---------------------------------------------------------------------------


def test_get_profile_after_registration(db, identity_svc):
    profile = identity_svc.register_user(
        db,
        RegisterRequest(
            email="profile_check@example.com",
            password="ProfilePass1",
            full_name="Jane Doe",
        ),
    )
    db.flush()

    fetched = identity_svc.get_profile(db, profile.user_id)
    assert fetched.user_id == profile.user_id
    assert fetched.email == "profile_check@example.com"
    assert fetched.full_name == "Jane Doe"
