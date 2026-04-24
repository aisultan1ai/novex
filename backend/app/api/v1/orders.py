from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.modules.orders.schemas import (
    CreateDraftFromQuoteRequest,
    OrderDraftListResponse,
    OrderDraftResponse,
    UpdateShipmentDetailsRequest,
)
from app.modules.orders.service import OrdersService

router = APIRouter(prefix="/orders", tags=["orders"])
orders_service = OrdersService()


@router.post(
    "/drafts/from-quote",
    response_model=OrderDraftResponse,
    status_code=201,
)
def create_order_draft_from_quote(
    payload: CreateDraftFromQuoteRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> OrderDraftResponse:
    return orders_service.create_draft_from_quote(
        db,
        user_id=current_user_id,
        payload=payload,
    )


@router.get(
    "",
    response_model=OrderDraftListResponse,
    status_code=200,
    summary="Список заказов текущего клиента",
)
def list_orders(
    page: int = Query(default=1, ge=1, description="Номер страницы"),
    size: int = Query(default=20, ge=1, le=100, description="Элементов на странице"),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> OrderDraftListResponse:
    return orders_service.list_order_drafts(
        db,
        user_id=current_user_id,
        page_params=PageParams(page=page, size=size),
    )


@router.get(
    "/drafts/{draft_id}",
    response_model=OrderDraftResponse,
    status_code=200,
)
def get_order_draft(
    draft_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> OrderDraftResponse:
    return orders_service.get_order_draft(
        db,
        user_id=current_user_id,
        draft_id=draft_id,
    )


@router.post(
    "/drafts/{draft_id}/checkout",
    response_model=OrderDraftResponse,
    status_code=200,
    summary="Перейти к оплате",
)
def proceed_to_checkout(
    draft_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> OrderDraftResponse:
    return orders_service.proceed_to_checkout(db, user_id=current_user_id, draft_id=draft_id)


@router.post(
    "/drafts/{draft_id}/pay/mock",
    response_model=OrderDraftResponse,
    status_code=200,
    summary="Подтвердить оплату (заглушка — заменить реальным шлюзом)",
)
def mock_pay_order_draft(
    draft_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> OrderDraftResponse:
    return orders_service.confirm_payment_mock(db, user_id=current_user_id, draft_id=draft_id)


@router.delete(
    "/drafts/{draft_id}",
    status_code=204,
    summary="Удалить черновик заказа",
)
def delete_order_draft(
    draft_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None:
    orders_service.delete_draft(db, user_id=current_user_id, draft_id=draft_id)


@router.patch(
    "/drafts/{draft_id}/shipment",
    response_model=OrderDraftResponse,
    status_code=200,
)
def update_order_draft_shipment(
    draft_id: int,
    payload: UpdateShipmentDetailsRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> OrderDraftResponse:
    return orders_service.update_shipment_details(
        db,
        user_id=current_user_id,
        draft_id=draft_id,
        payload=payload,
    )
