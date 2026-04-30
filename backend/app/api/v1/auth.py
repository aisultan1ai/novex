from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.core.config import get_settings
from app.core.limiter import limiter
from app.modules.identity.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    ResetPasswordRequest,
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
@limiter.limit("10/minute")
def login_user(
    request: Request,
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


@router.post(
    "/forgot-password",
    status_code=200,
    summary="Запросить сброс пароля — отправляет письмо со ссылкой",
)
@limiter.limit("5/minute")
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    identity_service.forgot_password(db, payload, frontend_url=settings.frontend_url)
    return {"detail": "Если аккаунт существует, письмо отправлено"}


@router.post(
    "/reset-password",
    status_code=200,
    summary="Установить новый пароль по токену из письма",
)
@limiter.limit("5/minute")
def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> dict:
    identity_service.reset_password(db, payload)
    return {"detail": "Пароль успешно изменён"}
