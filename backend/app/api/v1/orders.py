from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.core.db import get_db
from app.core.dependencies import get_current_user_id, require_verified_email
from app.core.limiter import limiter
from app.modules.orders.schemas import (
    CancelOrderResponse,
    CreateDraftFromQuoteRequest,
    CseRecalcRequest,
    CseRecalcResponse,
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
    statuses: list[str] | None = Query(
        default=None,
        description="Фильтр по статусам (можно передавать несколько раз или через запятую)",
    ),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> OrderDraftListResponse:
    # Разрешаем клиенту прислать `statuses=a,b,c` одной строкой или несколько
    # `statuses=` параметров подряд — в обоих случаях получаем плоский список.
    flat_statuses: list[str] | None = None
    if statuses:
        flat_statuses = []
        for entry in statuses:
            flat_statuses.extend(s.strip() for s in entry.split(",") if s.strip())
        if not flat_statuses:
            flat_statuses = None
    return orders_service.list_order_drafts(
        db,
        user_id=current_user_id,
        page_params=PageParams(page=page, size=size),
        statuses=flat_statuses,
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
    _verified = Depends(require_verified_email),
    db: Session = Depends(get_db),
) -> OrderDraftResponse:
    return orders_service.proceed_to_checkout(
        db, user_id=current_user_id, draft_id=draft_id
    )


@router.post(
    "/drafts/{draft_id}/pay/mock",
    response_model=OrderDraftResponse,
    status_code=200,
    summary="Подтвердить оплату (заглушка — только dev/test)",
    include_in_schema=False,
)
def mock_pay_order_draft(
    draft_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> OrderDraftResponse:
    from app.core.config import get_settings
    if get_settings().is_production:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Mock payment is disabled in production")
    return orders_service.confirm_payment_mock(
        db, user_id=current_user_id, draft_id=draft_id
    )


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


class CancelOrderRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


@router.post(
    "/{order_id}/cancel",
    response_model=CancelOrderResponse,
    status_code=200,
    summary="Отменить заказ (клиент)",
)
@limiter.limit("5/minute")
def cancel_order(
    order_id: int,
    payload: CancelOrderRequest,
    request: Request,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CancelOrderResponse:
    """Отменить заказ по инициативе клиента.

    Два возможных исхода:
      • outcome="cancelled" — заказ уже cancelled (CSE/Exline подтвердил
        отмену через API). Комиссия сторнирована, платежи переведены в
        refund_pending для последующей обработки админом.
      • outcome="requested" — создали заявку на отмену для перевозчика
        (Azimuth — всегда; CSE/Exline — если API отказал или недоступен).
        Заказ остаётся в текущем статусе, пока перевозчик или админ не
        подтвердит заявку.
    """
    return orders_service.cancel_order(
        db,
        user_id=current_user_id,
        order_id=order_id,
        reason=payload.reason,
    )


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


@router.post(
    "/drafts/{draft_id}/cse-recalc",
    response_model=CseRecalcResponse,
    status_code=200,
    summary="Recalc CSE quote with add-on services",
)
def cse_recalc_draft(
    draft_id: int,
    payload: CseRecalcRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CseRecalcResponse:
    """FE calls this from the checkout form (debounced) whenever the customer
    toggles insurance / delivery type / declared value. Returns the fully
    loaded final price for the currently-selected urgency. For non-CSE
    drafts it silently echoes the current price so the FE can call it
    unconditionally.
    """
    return orders_service.cse_recalc(
        db, user_id=current_user_id, draft_id=draft_id, payload=payload,
    )
