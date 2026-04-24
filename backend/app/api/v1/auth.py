from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.modules.identity.schemas import (
    LoginRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    TokenResponse,
)
from app.modules.identity.service import IdentityService

router = APIRouter(prefix="/auth", tags=["auth"])
identity_service = IdentityService()


@router.post(
    "/register",
    response_model=ProfileResponse,
    status_code=201,
)
def register_user(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> ProfileResponse:
    return identity_service.register_user(db, payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=200,
)
def login_user(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    return identity_service.authenticate_user(db, payload)


@router.get(
    "/profile",
    response_model=ProfileResponse,
    status_code=200,
)
def get_my_profile(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    return identity_service.get_profile(db, current_user_id)


@router.patch(
    "/profile",
    response_model=ProfileResponse,
    status_code=200,
)
def update_my_profile(
    payload: ProfileUpdateRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    return identity_service.update_profile(db, user_id=current_user_id, payload=payload)
