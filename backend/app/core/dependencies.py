from __future__ import annotations

from typing import Any

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token, get_token_version
from app.modules.identity.models import User
from app.modules.identity.repository import IdentityRepository

bearer_scheme = HTTPBearer(auto_error=False)
identity_repository = IdentityRepository()


def get_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    access_token: str | None = Cookie(default=None),
) -> dict[str, Any]:
    # HttpOnly cookie takes priority; Bearer header is accepted as fallback
    token = access_token
    if token is None and credentials is not None:
        if credentials.scheme.lower() == "bearer":
            token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Войдите в аккаунт, чтобы продолжить.",
        )

    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    return payload


def get_current_user_id(
    payload: dict[str, Any] = Depends(get_token_payload),
) -> int:
    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия недействительна. Войдите в аккаунт снова.",
        )

    try:
        return int(subject)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия недействительна. Войдите в аккаунт снова.",
        ) from exc


def get_current_user(
    db: Session = Depends(get_db),
    payload: dict[str, Any] = Depends(get_token_payload),
    current_user_id: int = Depends(get_current_user_id),
) -> User:
    user = identity_repository.get_user_by_id(db, current_user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Аккаунт не найден. Войдите в аккаунт снова.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт отключён. Обратитесь в поддержку.",
        )

    # Verify token version — invalidated when admin changes role or calls invalidate_user_tokens()
    ver_in_token = int(payload.get("ver", 0))
    if ver_in_token != get_token_version(user.id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия истекла. Войдите в аккаунт снова.",
        )

    return user


def require_verified_email(current_user: User = Depends(get_current_user)) -> User:
    """Guard for actions that require a confirmed email — placing orders,
    paying, etc. Returns 403 with a machine-readable error code so the
    frontend can render a "resend verification" prompt instead of a generic
    forbidden banner."""
    from app.modules.identity.models import RoleCode

    # Non-customer roles are trusted (admins/operators/carriers manage their
    # own auth flows and their emails are seeded / set up separately).
    if current_user.role.code != RoleCode.CUSTOMER:
        return current_user

    if current_user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "email_not_verified",
                "message": "Подтвердите email, чтобы продолжить.",
            },
        )
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    from app.modules.identity.models import RoleCode

    if current_user.role.code != RoleCode.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для этого действия.",
        )
    return current_user


def require_admin_or_operator(current_user: User = Depends(get_current_user)) -> User:
    from app.modules.identity.models import RoleCode

    if current_user.role.code not in (RoleCode.ADMIN, RoleCode.OPERATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для этого действия.",
        )
    return current_user


def require_carrier(current_user: User = Depends(get_current_user)) -> User:
    from app.modules.identity.models import RoleCode

    if current_user.role.code != RoleCode.CARRIER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для этого действия.",
        )
    return current_user


def get_current_carrier_id(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_carrier),
) -> int:
    from sqlalchemy import select

    from app.modules.identity.models import CarrierProfile

    profile = db.scalar(
        select(CarrierProfile).where(CarrierProfile.user_id == current_user.id)
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Профиль перевозчика не найден. Обратитесь в поддержку.",
        )
    return profile.carrier_id
