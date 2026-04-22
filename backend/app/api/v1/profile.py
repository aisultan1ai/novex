from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.modules.identity.schemas import ProfileResponse, ProfileUpdateRequest
from app.modules.identity.service import IdentityService

router = APIRouter(prefix="/profile", tags=["profile"])
identity_service = IdentityService()


@router.get(
    "",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
)
def get_profile(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    try:
        return identity_service.get_profile(db, current_user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch(
    "",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
)
def update_profile(
    payload: ProfileUpdateRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    try:
        return identity_service.update_profile(
            db,
            user_id=current_user_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc