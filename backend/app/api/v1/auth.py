from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.core.limiter import limiter
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_TTL_SECONDS,
    consume_refresh_token,
    create_access_token,
    create_refresh_token,
    get_token_version,
    revoke_refresh_token,
)
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

_REFRESH_COOKIE = "refresh_token"


def _set_auth_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=REFRESH_TOKEN_TTL_SECONDS,
        path="/api/v1/auth",  # scope to auth endpoints only
    )


@router.post(
    "/register",
    response_model=ProfileResponse,
    status_code=201,
)
@limiter.limit("5/minute")
def register_user(
    request: Request,
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
    response: Response,
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    result = identity_service.authenticate_user(db, payload)
    _set_auth_cookie(response, result.access_token)
    user_id = int(result.profile.user_id)
    _set_refresh_cookie(response, create_refresh_token(user_id))
    return result


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=200,
    summary="Обновить access token по refresh token из cookie",
)
@limiter.limit("20/minute")
def refresh_access_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    from fastapi import HTTPException
    token = request.cookies.get(_REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token отсутствует")

    user_id = consume_refresh_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Refresh token недействителен или истёк")

    from app.modules.identity.repository import IdentityRepository
    user = IdentityRepository().get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Пользователь не найден или неактивен")

    role_code = user.role.code.value if user.role else "customer"
    new_access = create_access_token({
        "sub": str(user.id),
        "role": role_code,
        "ver": get_token_version(user.id),
    })
    new_refresh = create_refresh_token(user.id)

    _set_auth_cookie(response, new_access)
    _set_refresh_cookie(response, new_refresh)

    profile = identity_service.get_profile(db, user_id)
    return TokenResponse(
        access_token=new_access,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        profile=profile,
    )


@router.post(
    "/logout",
    status_code=200,
    summary="Завершить сессию — удаляет HttpOnly-cookie",
)
def logout_user(
    request: Request,
    response: Response,
) -> dict:
    token = request.cookies.get(_REFRESH_COOKIE)
    if token:
        revoke_refresh_token(token)
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key=_REFRESH_COOKIE, path="/api/v1/auth")
    return {"detail": "Вышли из системы"}


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
    return identity_service.update_profile(
        db, user_id=current_user_id, payload=payload
    )


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
