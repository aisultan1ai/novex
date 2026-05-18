from __future__ import annotations

from typing import Any

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
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
            detail="Authorization credentials are required",
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
            detail="Token subject is missing",
        )

    try:
        return int(subject)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        ) from exc


def get_current_user(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
) -> User:
    user = identity_repository.get_user_by_id(db, current_user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current user not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current user is inactive",
        )

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    from app.modules.identity.models import RoleCode

    if current_user.role.code != RoleCode.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для администраторов",
        )
    return current_user


def require_carrier(current_user: User = Depends(get_current_user)) -> User:
    from app.modules.identity.models import RoleCode

    if current_user.role.code != RoleCode.CARRIER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для перевозчиков",
        )
    return current_user
