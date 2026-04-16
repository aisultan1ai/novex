from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.modules.orders.schemas import (
    CreateDraftFromQuoteRequest,
    OrderDraftResponse,
    UpdateShipmentDetailsRequest,
)
from app.modules.orders.service import OrdersService

router = APIRouter(prefix="/orders", tags=["orders"])
orders_service = OrdersService()


@router.post(
    "/drafts/from-quote",
    response_model=OrderDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_order_draft_from_quote(
    payload: CreateDraftFromQuoteRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> OrderDraftResponse:
    try:
        return orders_service.create_draft_from_quote(
            db,
            user_id=current_user_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/drafts/{draft_id}",
    response_model=OrderDraftResponse,
    status_code=status.HTTP_200_OK,
)
def get_order_draft(
    draft_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> OrderDraftResponse:
    try:
        return orders_service.get_order_draft(
            db,
            user_id=current_user_id,
            draft_id=draft_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch(
    "/drafts/{draft_id}/shipment",
    response_model=OrderDraftResponse,
    status_code=status.HTTP_200_OK,
)
def update_order_draft_shipment(
    draft_id: int,
    payload: UpdateShipmentDetailsRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> OrderDraftResponse:
    try:
        return orders_service.update_shipment_details(
            db,
            user_id=current_user_id,
            draft_id=draft_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc