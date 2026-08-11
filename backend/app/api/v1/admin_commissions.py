from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import require_admin, require_admin_or_operator
from app.core.excel import MAX_EXPORT_ROWS, build_xlsx_response, fmt_dt
from app.core.limiter import limiter
from app.modules.commissions.models import Commission
from app.modules.commissions.repository import CommissionsRepository
from app.modules.commissions.schemas import CommissionSummary
from app.modules.commissions.service import CommissionsService
from app.modules.orders.models import OrderDraft
from app.modules.shipments.models import Shipment

router = APIRouter(prefix="/admin/commissions", tags=["admin:commissions"])
_service = CommissionsService()
_repo = CommissionsRepository()


# Русские подписи для типа операции — в списке комиссий это "начисление"
# (status=active), "возврат" (reversal — отрицательный оффсет), либо
# "отменено" (reversed — оригинал, который уже сторнирован).
_COMMISSION_STATUS_RU: dict[str, str] = {
    "active": "начисление",
    "reversal": "возврат",
    "reversed": "отменено (заменено сторно)",
}

_COMMISSION_EXPORT_HEADERS = [
    "Дата операции",
    "ID заказа",
    "Трек Novex",
    "Трек перевозчика",
    "Штрих-код",
    "Перевозчик",
    "Тип операции",
    "Статус заказа",
    "Сумма (клиент)",
    "Выплата перевозчику",
    "Комиссия Novex",
    "Ставка комиссии",
    "Валюта",
    "Причина возврата",
]


def _commission_export_rows(
    commissions: list[Commission],
    orders_map: dict[int, OrderDraft],
    shipments_map: dict[int, Shipment],
):
    for c in commissions:
        order = orders_map.get(c.order_draft_id)
        shipment = shipments_map.get(c.order_draft_id)
        yield [
            fmt_dt(c.created_at),
            c.order_draft_id,
            shipment.tracking_number if shipment else None,
            shipment.carrier_tracking_number if shipment else None,
            shipment.carrier_barcode if shipment else None,
            (order.carrier_name_snapshot if order else c.carrier_code),
            _COMMISSION_STATUS_RU.get(c.status, c.status),
            order.status if order else None,
            float(c.gross_amount) if c.gross_amount is not None else None,
            float(c.carrier_payout) if c.carrier_payout is not None else None,
            float(c.commission_amount) if c.commission_amount is not None else None,
            f"{float(c.commission_rate) * 100:.2f}%" if c.commission_rate is not None else None,
            c.currency,
            c.reversal_reason,
        ]


@router.get("", summary="Список комиссий")
def list_commissions(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    carrier_code: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    return _service.list_commissions(
        db,
        page=page,
        size=size,
        date_from=date_from,
        date_to=date_to,
        carrier_code=carrier_code,
    )


@router.get("/export", summary="Экспорт комиссий в Excel")
@limiter.limit("10/hour")
def export_commissions(
    request: Request,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    carrier_code: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(require_admin_or_operator),
):
    """XLSX-выгрузка списка комиссий (flat, начисления и возвраты отдельными
    строками, возвраты — отрицательные, чтобы автосумма Excel сошлась)."""
    # +1 к MAX для детекции «не влезло» без загрузки лишних миллионов.
    items, total = _repo.list_all(
        db,
        offset=0,
        limit=MAX_EXPORT_ROWS + 1,
        date_from=date_from,
        date_to=date_to,
        carrier_code=carrier_code,
    )
    if not items:
        raise HTTPException(422, "По этим фильтрам нет комиссий для экспорта")
    if len(items) > MAX_EXPORT_ROWS:
        raise HTTPException(
            422,
            f"Слишком много данных для экспорта (>{MAX_EXPORT_ROWS} строк). "
            "Сузьте период.",
        )

    order_ids = [c.order_draft_id for c in items]
    orders_map: dict[int, OrderDraft] = {}
    shipments_map: dict[int, Shipment] = {}
    if order_ids:
        orders = db.scalars(
            select(OrderDraft).where(OrderDraft.id.in_(order_ids))
        ).all()
        orders_map = {o.id: o for o in orders}
        shipments = db.scalars(
            select(Shipment).where(Shipment.order_draft_id.in_(order_ids))
        ).all()
        shipments_map = {s.order_draft_id: s for s in shipments}

    # Итоговая строка — суммы по трём денежным колонкам. Excel сам покажет
    # красное для отрицательных (после возврата итог обычно положительный).
    total_gross = sum(float(c.gross_amount) for c in items if c.gross_amount is not None)
    total_payout = sum(
        float(c.carrier_payout) for c in items if c.carrier_payout is not None
    )
    total_commission = sum(
        float(c.commission_amount) for c in items if c.commission_amount is not None
    )
    total_row: list = [None] * len(_COMMISSION_EXPORT_HEADERS)
    total_row[0] = f"Итого: {len(items)}"
    total_row[8] = total_gross
    total_row[9] = total_payout
    total_row[10] = total_commission

    rows = _commission_export_rows(list(items), orders_map, shipments_map)
    return build_xlsx_response(
        filename_base="commissions_admin",
        sheet_name="Комиссии",
        headers=_COMMISSION_EXPORT_HEADERS,
        rows=rows,
        money_cols=[9, 10, 11],
        datetime_cols=[1],
        total_row=total_row,
    )


@router.get("/summary", response_model=CommissionSummary, summary="Итоги по комиссиям")
def commissions_summary(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    carrier_code: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> CommissionSummary:
    return _service.get_summary(db, date_from=date_from, date_to=date_to, carrier_code=carrier_code)
