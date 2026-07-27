from __future__ import annotations

import math
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.dependencies import get_current_carrier_id, require_carrier
from app.core.storage import MAX_FILE_SIZE, get_storage
from app.modules.carriers.models import (
    Carrier,
    CarrierCommissionConfig,
    CarrierService,
    CarrierTariffRate,
)
from app.modules.carriers.webhook_config import (
    CarrierWebhookConfig,
    CarrierWebhookRepository,
)
from app.modules.commissions.schemas import CommissionSummary
from app.modules.commissions.service import CommissionsService
from app.modules.dispatch.models import OrderStatusHistory
from app.modules.documents.models import Document, DocumentType
from app.modules.identity.models import User
from app.modules.notifications.repository import NotificationsRepository
from app.modules.orders.models import OrderDraft, ShipmentPackage, ShipmentParty
from app.modules.shipments.models import Shipment
from app.modules.tracking.models import TrackingEvent

router = APIRouter(prefix="/carrier", tags=["carrier-portal"])

_CARRIER_VISIBLE_STATUSES = {
    "sent_to_carrier", "pending_manual", "pending_manual_dispatch",
    "dispatch_failed", "picked_up", "in_transit", "arrived", "delivered",
}
_ACCEPT_ALLOWED_STATUSES = {"sent_to_carrier", "pending_manual", "pending_manual_dispatch", "dispatch_failed"}
_REJECT_ALLOWED_STATUSES = {"sent_to_carrier", "pending_manual", "pending_manual_dispatch"}
_POD_ALLOWED_STATUSES = {"in_transit", "arrived", "picked_up", "delivered"}

_notif_repo = NotificationsRepository()

_webhook_repo = CarrierWebhookRepository()

_commissions_service = CommissionsService()


def _mask_secret(secret: str | None) -> str | None:
    if not secret:
        return None
    prefix = "nvx_live_"
    raw = secret[len(prefix):] if secret.startswith(prefix) else secret
    if len(raw) <= 8:
        return prefix + "*" * len(raw)
    return prefix + "*" * (len(raw) - 4) + raw[-4:]


@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    carrier_id: int = Depends(get_current_carrier_id),
) -> dict:
    carrier = db.get(Carrier, carrier_id)
    if not carrier:
        raise HTTPException(404, "Перевозчик не найден")

    webhook = db.scalar(
        select(CarrierWebhookConfig).where(
            CarrierWebhookConfig.carrier_code == carrier.code
        )
    )

    return {
        "carrier": {
            "id": carrier.id,
            "code": carrier.code,
            "name": carrier.name,
            "description": carrier.description,
            "is_active": carrier.is_active,
        },
        "integration": {
            "push_url": webhook.push_url if webhook else None,
            "webhook_secret_masked": _mask_secret(webhook.webhook_secret if webhook else None),
            "is_active": webhook.is_active if webhook else False,
            "retry_count": webhook.retry_count if webhook else 3,
            "timeout_seconds": webhook.timeout_seconds if webhook else 10,
        },
    }


@router.get("/integration-config")
def get_integration_config(
    db: Session = Depends(get_db),
    carrier_id: int = Depends(get_current_carrier_id),
) -> dict:
    """Returns full integration configuration for both push and pull methods."""
    carrier = db.get(Carrier, carrier_id)
    if not carrier:
        raise HTTPException(404, "Перевозчик не найден")

    webhook = db.scalar(
        select(CarrierWebhookConfig).where(
            CarrierWebhookConfig.carrier_code == carrier.code
        )
    )

    return {
        "carrier_code": carrier.code,
        "methods": {
            "outbound": {
                "description": "Novex отправляет заказы на ваш API (push)",
                "novex_calls_your_url": webhook.push_url if webhook else None,
                "method": "POST",
                "hmac_header": "X-Novex-Signature",
                "hmac_algorithm": "HMAC-SHA256",
                "hmac_description": "signature = HMAC-SHA256(secret, timestamp + raw_body)",
                "secret_key_masked": _mask_secret(webhook.webhook_secret if webhook else None),
                "active": bool(webhook and webhook.push_url),
                "example_payload": {
                    "novex_order_id": 12345,
                    "order_reference": "NOVEX-012345",
                    "tariff_code": "standard",
                    "sender": {"full_name": "...", "phone": "+77001234567", "city": "Almaty", "address": "..."},
                    "recipient": {"full_name": "...", "phone": "+77007654321", "city": "Astana", "address": "..."},
                    "packages": [{"weight_kg": 1.5, "width_cm": 20, "height_cm": 15, "depth_cm": 10, "quantity": 1}],
                    "declared_value": 3500.0,
                    "currency": "KZT",
                },
                "expected_response": {"tracking_number": "YOUR_TRACK_NUMBER"},
            },
            "inbound": {
                "description": "Вы отправляете трекинг-события на наш webhook (push)",
                "your_calls_our_url": f"/api/v1/carriers/{carrier.code}/tracking-webhook",
                "method": "POST",
                "hmac_header": "X-Carrier-Signature",
                "hmac_algorithm": "HMAC-SHA256",
                "hmac_description": "signature = HMAC-SHA256(secret, raw_body). Include X-Novex-Timestamp header.",
                "secret_key_masked": _mask_secret(webhook.webhook_secret if webhook else None),
                "example_payload": {
                    "novex_order_id": 12345,
                    "event_id": "unique-event-id-per-event",
                    "status": "in_transit",
                    "location": "Almaty sorting center",
                    "description": "Package arrived at sorting center",
                },
                "supported_statuses": [
                    "picked_up", "in_transit", "arrived",
                    "delivered", "returned", "return_in_progress",
                ],
            },
        },
    }


@router.post("/integration-config/regenerate-secret")
def regenerate_secret(
    db: Session = Depends(get_db),
    carrier_id: int = Depends(get_current_carrier_id),
) -> dict:
    """Regenerate webhook secret. Returns the new secret once (store it safely)."""
    carrier = db.get(Carrier, carrier_id)
    if not carrier:
        raise HTTPException(404, "Перевозчик не найден")

    webhook = db.scalar(
        select(CarrierWebhookConfig).where(
            CarrierWebhookConfig.carrier_code == carrier.code
        )
    )
    if not webhook:
        raise HTTPException(404, "Конфигурация webhook не найдена")

    new_secret = "nvx_live_" + secrets.token_hex(24)
    webhook.webhook_secret = new_secret
    db.commit()

    return {
        "webhook_secret": new_secret,
        "warning": "Store this secret securely — it will not be shown again in full.",
    }


# ── Tariffs (read-only) ───────────────────────────────────────────────────────


def _service_dict(s: CarrierService) -> dict:
    return {
        "id": s.id,
        "code": s.code,
        "name": s.name,
        "shipment_type": s.shipment_type,
        "is_active": s.is_active,
    }


def _rate_dict(r: CarrierTariffRate) -> dict:
    return {
        "id": r.id,
        "zone": r.zone,
        "weight_from_kg": float(r.weight_from_kg),
        "weight_to_kg": float(r.weight_to_kg) if r.weight_to_kg is not None else None,
        "base_price": float(r.base_price),
        "per_unit_price": float(r.per_unit_price) if r.per_unit_price is not None else None,
        "per_unit_weight_kg": float(r.per_unit_weight_kg) if r.per_unit_weight_kg is not None else None,
        "currency": r.currency,
        "eta_days_min": r.eta_days_min,
        "eta_days_max": r.eta_days_max,
        "is_active": r.is_active,
    }


@router.get("/services", summary="Список услуг перевозчика (read-only)")
def list_own_services(
    db: Session = Depends(get_db),
    carrier_id: int = Depends(get_current_carrier_id),
) -> list[dict]:
    services = db.scalars(
        select(CarrierService)
        .where(CarrierService.carrier_id == carrier_id)
        .order_by(CarrierService.code)
    ).all()
    return [_service_dict(s) for s in services]


@router.get("/services/{service_id}/rates", summary="Тарифная сетка услуги (read-only)")
def list_own_rates(
    service_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    carrier_id: int = Depends(get_current_carrier_id),
) -> dict:
    service = db.get(CarrierService, service_id)
    if not service or service.carrier_id != carrier_id:
        raise HTTPException(404, "Услуга не найдена")

    base = (
        select(CarrierTariffRate)
        .where(CarrierTariffRate.service_id == service_id)
        .order_by(CarrierTariffRate.zone, CarrierTariffRate.weight_from_kg)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rates = db.scalars(base.offset((page - 1) * size).limit(size)).all()
    pages = math.ceil(total / size) if total > 0 else 1
    return {
        "items": [_rate_dict(r) for r in rates],
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


# ── Orders ────────────────────────────────────────────────────────────────────

def _get_carrier_or_404(db: Session, carrier_id: int) -> Carrier:
    carrier = db.get(Carrier, carrier_id)
    if not carrier:
        raise HTTPException(404, "Перевозчик не найден")
    return carrier


def _get_order_for_carrier(db: Session, order_id: int, carrier_code: str) -> OrderDraft:
    order = db.get(OrderDraft, order_id)
    if not order or order.carrier_code_snapshot != carrier_code:
        raise HTTPException(404, "Заказ не найден")
    return order


def _order_to_dict(
    order: OrderDraft,
    parties: list,
    packages: list,
    shipment: Shipment | None = None,
) -> dict:
    # Perevozchik sees only their side of the transaction: carrier_price_snapshot
    # (what Novex owes them) — never the customer-facing price that includes
    # the Novex markup. Fall back to price_snapshot for orders created before
    # migration 032, where the customer paid the raw carrier amount and there
    # is no separate carrier value.
    carrier_payout = (
        float(order.carrier_price_snapshot)
        if order.carrier_price_snapshot is not None
        else float(order.price_snapshot)
    )
    return {
        "id": order.id,
        "status": order.status,
        "carrier_code": order.carrier_code_snapshot,
        "tariff_name": order.tariff_name_snapshot,
        "price": carrier_payout,
        "currency": order.currency_snapshot,
        "from_city": order.from_city_snapshot,
        "to_city": order.to_city_snapshot,
        "eta_days_min": order.eta_days_min_snapshot,
        "eta_days_max": order.eta_days_max_snapshot,
        "created_at": order.created_at.isoformat(),
        # Carrier-side identifiers — shown to the carrier operator so they can
        # match Novex orders to entries in their own back-office / physical shipments.
        "tracking_number": shipment.tracking_number if shipment else None,
        "carrier_tracking_number": shipment.carrier_tracking_number if shipment else None,
        "carrier_barcode": shipment.carrier_barcode if shipment else None,
        "parties": [
            {
                "role": p.role,
                "full_name": p.full_name,
                "phone": p.phone,
                "city": p.city,
                "address_line1": p.address_line1,
                "address_line2": p.address_line2,
                "postal_code": p.postal_code,
                "comment": p.comment,
            }
            for p in parties
        ],
        "packages": [
            {
                "description": pkg.description,
                "quantity": pkg.quantity,
                "weight_kg": float(pkg.weight_kg),
                "width_cm": float(pkg.width_cm),
                "height_cm": float(pkg.height_cm),
                "depth_cm": float(pkg.depth_cm),
                "declared_value": float(pkg.declared_value) if pkg.declared_value else None,
                "declared_value_currency": pkg.declared_value_currency,
            }
            for pkg in packages
        ],
    }


@router.get("/orders", summary="Список заказов перевозчика")
def list_orders(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    carrier_id: int = Depends(get_current_carrier_id),
) -> dict:
    carrier = _get_carrier_or_404(db, carrier_id)

    base_where = [
        OrderDraft.carrier_code_snapshot == carrier.code,
        OrderDraft.status.in_(_CARRIER_VISIBLE_STATUSES),
    ]
    if status:
        base_where.append(OrderDraft.status == status)

    total = db.scalar(select(func.count(OrderDraft.id)).where(*base_where)) or 0

    orders = db.scalars(
        select(OrderDraft)
        .options(
            selectinload(OrderDraft.parties),
            selectinload(OrderDraft.packages),
        )
        .where(*base_where)
        .order_by(OrderDraft.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()

    order_ids = [o.id for o in orders]
    shipments_map: dict[int, Shipment] = {}
    if order_ids:
        shps = db.scalars(select(Shipment).where(Shipment.order_draft_id.in_(order_ids))).all()
        shipments_map = {s.order_draft_id: s for s in shps}

    items = [
        _order_to_dict(
            order, list(order.parties), list(order.packages),
            shipment=shipments_map.get(order.id),
        )
        for order in orders
    ]

    return {"items": items, "total": total or 0, "page": page, "size": size}


@router.get("/orders/{order_id}", summary="Детали заказа")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    carrier_id: int = Depends(get_current_carrier_id),
) -> dict:
    carrier = _get_carrier_or_404(db, carrier_id)
    order = _get_order_for_carrier(db, order_id, carrier.code)

    if order.status not in _CARRIER_VISIBLE_STATUSES:
        raise HTTPException(403, "Заказ недоступен")

    parties = db.scalars(select(ShipmentParty).where(ShipmentParty.order_draft_id == order.id)).all()
    packages = db.scalars(select(ShipmentPackage).where(ShipmentPackage.order_draft_id == order.id)).all()

    pods = db.scalars(
        select(Document).where(
            Document.order_id == order.id,
            Document.document_type == DocumentType.PROOF_OF_DELIVERY,
        ).order_by(Document.created_at.desc())
    ).all()

    events = db.scalars(
        select(TrackingEvent)
        .where(TrackingEvent.order_draft_id == order.id)
        .order_by(TrackingEvent.occurred_at.desc())
    ).all()

    shipment = db.scalar(select(Shipment).where(Shipment.order_draft_id == order.id))
    result = _order_to_dict(order, list(parties), list(packages), shipment=shipment)
    result["proof_of_delivery"] = [
        {
            "id": d.id,
            "file_url": d.file_url,
            "file_name": d.file_name,
            "mime_type": d.mime_type,
            "created_at": d.created_at.isoformat(),
        }
        for d in pods
    ]
    result["tracking_events"] = [
        {
            "status": e.status,
            "description": e.description,
            "location": e.location,
            "occurred_at": e.occurred_at.isoformat(),
        }
        for e in events
    ]
    return result


@router.post("/orders/{order_id}/accept", summary="Принять заказ")
def accept_order(
    order_id: int,
    db: Session = Depends(get_db),
    carrier_id: int = Depends(get_current_carrier_id),
    current_user: User = Depends(require_carrier),
) -> dict:
    carrier = _get_carrier_or_404(db, carrier_id)
    order = _get_order_for_carrier(db, order_id, carrier.code)

    if order.status not in _ACCEPT_ALLOWED_STATUSES:
        raise HTTPException(400, f"Нельзя принять заказ со статусом «{order.status}»")

    old_status = order.status
    order.status = "picked_up"
    order.dispatch_error = None

    db.add(OrderStatusHistory(
        order_id=order.id,
        old_status=old_status,
        new_status="picked_up",
        changed_by_user_id=current_user.id,
        source="carrier_portal",
        comment="Перевозчик подтвердил приёмку заказа",
    ))
    db.add(TrackingEvent(
        order_draft_id=order.id,
        status="picked_up",
        description="Заказ принят перевозчиком",
    ))

    _notif_repo.create(
        db,
        user_id=order.user_id,
        type="order_status",
        title="Заказ принят перевозчиком",
        body=f"Заказ #{order.id} принят перевозчиком {carrier.name} и готовится к отправке.",
    )

    db.commit()
    return {"order_id": order.id, "status": order.status, "message": "Заказ принят"}


@router.post("/orders/{order_id}/reject", summary="Отклонить заказ")
def reject_order(
    order_id: int,
    reason: str = Form(..., min_length=1, max_length=500),
    db: Session = Depends(get_db),
    carrier_id: int = Depends(get_current_carrier_id),
    current_user: User = Depends(require_carrier),
) -> dict:
    carrier = _get_carrier_or_404(db, carrier_id)
    order = _get_order_for_carrier(db, order_id, carrier.code)

    if order.status not in _REJECT_ALLOWED_STATUSES:
        raise HTTPException(400, f"Нельзя отклонить заказ со статусом «{order.status}»")

    old_status = order.status
    order.status = "dispatch_failed"
    order.dispatch_error = f"Отклонено перевозчиком: {reason}"

    db.add(OrderStatusHistory(
        order_id=order.id,
        old_status=old_status,
        new_status="dispatch_failed",
        changed_by_user_id=current_user.id,
        source="carrier_portal",
        comment=f"Перевозчик отклонил заказ: {reason}",
    ))
    db.add(TrackingEvent(
        order_draft_id=order.id,
        status="dispatch_failed",
        description=f"Перевозчик отклонил заказ: {reason}",
    ))

    from app.modules.identity.models import Role, RoleCode
    admins = db.scalars(
        select(User).join(User.role).where(Role.code == RoleCode.ADMIN, User.is_active.is_(True))
    ).all()
    for admin in admins:
        _notif_repo.create(
            db,
            user_id=admin.id,
            type="carrier_rejection",
            title=f"Перевозчик отклонил заказ #{order.id}",
            body=f"Причина: {reason}. Требуется ручная обработка.",
        )

    db.commit()
    return {"order_id": order.id, "status": order.status, "message": "Заказ отклонён, администраторы уведомлены"}


@router.post("/orders/{order_id}/pod", summary="Загрузить подтверждение доставки (POD)")
async def upload_pod(
    order_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    carrier_id: int = Depends(get_current_carrier_id),
    current_user: User = Depends(require_carrier),
) -> dict:
    carrier = _get_carrier_or_404(db, carrier_id)
    order = _get_order_for_carrier(db, order_id, carrier.code)

    if order.status not in _POD_ALLOWED_STATUSES:
        raise HTTPException(400, f"Нельзя загрузить POD для заказа со статусом «{order.status}»")

    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"Файл слишком большой (максимум {MAX_FILE_SIZE // (1024 * 1024)} МБ)")  # noqa: E501
    file_data = await file.read()
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"Файл слишком большой (максимум {MAX_FILE_SIZE // (1024 * 1024)} МБ)")  # noqa: E501
    mime_type = file.content_type or "application/octet-stream"
    original_name = file.filename or "pod"

    try:
        uploaded = get_storage().upload_file(
            file_data=file_data,
            original_name=original_name,
            mime_type=mime_type,
            folder="pod",
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))

    doc = Document(
        order_id=order.id,
        document_type=DocumentType.PROOF_OF_DELIVERY,
        file_url=uploaded.file_url,
        file_name=uploaded.file_name,
        mime_type=uploaded.file_mime_type,
        created_by_user_id=current_user.id,
    )
    db.add(doc)

    if order.status != "delivered":
        old_status = order.status
        order.status = "delivered"
        db.add(OrderStatusHistory(
            order_id=order.id,
            old_status=old_status,
            new_status="delivered",
            changed_by_user_id=current_user.id,
            source="carrier_portal",
            comment="Перевозчик загрузил подтверждение доставки",
        ))
        db.add(TrackingEvent(
            order_draft_id=order.id,
            status="delivered",
            description="Заказ доставлен. Подтверждение загружено перевозчиком.",
        ))
        _notif_repo.create(
            db,
            user_id=order.user_id,
            type="order_status",
            title="Заказ доставлен",
            body=f"Заказ #{order.id} доставлен. Подтверждение доставки прикреплено.",
        )

    db.commit()
    db.refresh(doc)
    return {
        "document_id": doc.id,
        "file_url": doc.file_url,
        "file_name": doc.file_name,
        "order_status": order.status,
        "message": "Подтверждение доставки загружено",
    }


# ─── Финансы / комиссии перевозчика (read-only) ─────────────────────────────
#
# Reuses CommissionsService (same code that powers /admin/commissions) and
# just forces carrier_code = current carrier's code — perevozchik cannot spy
# on other carriers' financials. Config endpoint returns the rate admin has
# set for them; no PATCH/PUT here on purpose (только чтение).


@router.get("/commissions", summary="Список комиссий по своим заказам")
def list_own_commissions(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    carrier_id: int = Depends(get_current_carrier_id),
) -> dict:
    carrier = _get_carrier_or_404(db, carrier_id)
    return _commissions_service.list_commissions(
        db,
        page=page,
        size=size,
        date_from=date_from,
        date_to=date_to,
        carrier_code=carrier.code,
    )


@router.get(
    "/commissions/summary",
    response_model=CommissionSummary,
    summary="Итоги по комиссиям",
)
def own_commissions_summary(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    carrier_id: int = Depends(get_current_carrier_id),
) -> CommissionSummary:
    carrier = _get_carrier_or_404(db, carrier_id)
    return _commissions_service.get_summary(
        db,
        date_from=date_from,
        date_to=date_to,
        carrier_code=carrier.code,
    )


@router.get(
    "/commissions/config",
    summary="Текущая ставка комиссии (установлена админом, read-only)",
)
def own_commission_config(
    db: Session = Depends(get_db),
    carrier_id: int = Depends(get_current_carrier_id),
) -> dict:
    carrier = _get_carrier_or_404(db, carrier_id)
    config = db.scalar(
        select(CarrierCommissionConfig).where(
            CarrierCommissionConfig.carrier_code == carrier.code
        )
    )
    if config is None:
        # No per-carrier config → admin uses the global rate. Frontend renders
        # "не установлена / по умолчанию платформы" в таком случае.
        return {
            "carrier_code": carrier.code,
            "commission_type": None,
            "commission_rate": None,
            "fixed_amount": None,
            "currency": "KZT",
            "is_set": False,
        }
    return {
        "carrier_code": config.carrier_code,
        "commission_type": config.commission_type,
        "commission_rate": str(config.commission_rate) if config.commission_rate is not None else None,
        "fixed_amount": str(config.fixed_amount) if config.fixed_amount is not None else None,
        "currency": config.currency,
        "is_set": True,
    }
