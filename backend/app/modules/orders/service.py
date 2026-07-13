from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.modules.address_book.repository import AddressBookRepository
from app.modules.orders.models import OrderDraft, ShipmentPackage, ShipmentParty
from app.modules.orders.repository import OrdersRepository
from app.modules.orders.schemas import (
    CreateDraftFromQuoteRequest,
    CseRecalcRequest,
    CseRecalcResponse,
    OrderDraftListResponse,
    OrderDraftResponse,
    ShipmentPackageResponse,
    ShipmentPartyInput,
    ShipmentPartyResponse,
    UpdateShipmentDetailsRequest,
)
from app.modules.quotes.models import QuoteSession
from app.modules.shipments.models import Shipment

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class _RecalcOverrides:
    """Per-package override for the recalc path. All fields optional — a
    missing field falls back to the quote_session value."""

    __slots__ = ("weight_kg", "width_cm", "height_cm", "depth_cm", "quantity")

    def __init__(
        self,
        weight_kg: float | None = None,
        width_cm: float | None = None,
        height_cm: float | None = None,
        depth_cm: float | None = None,
        quantity: int | None = None,
    ) -> None:
        self.weight_kg = weight_kg
        self.width_cm = width_cm
        self.height_cm = height_cm
        self.depth_cm = depth_cm
        self.quantity = quantity

    @classmethod
    def from_payload(cls, payload: CseRecalcRequest) -> "_RecalcOverrides":
        return cls(
            weight_kg=float(payload.weight_kg) if payload.weight_kg is not None else None,
            width_cm=float(payload.width_cm) if payload.width_cm is not None else None,
            height_cm=float(payload.height_cm) if payload.height_cm is not None else None,
            depth_cm=float(payload.depth_cm) if payload.depth_cm is not None else None,
            quantity=payload.quantity,
        )

    @classmethod
    def from_order_draft(cls, order_draft: OrderDraft) -> "_RecalcOverrides":
        """Read the currently persisted first package as an override so a
        post-save recalc uses the same numbers that were just written."""
        if not order_draft.packages:
            return cls()
        pkg = order_draft.packages[0]
        return cls(
            weight_kg=float(pkg.weight_kg) if pkg.weight_kg is not None else None,
            width_cm=float(pkg.width_cm) if pkg.width_cm is not None else None,
            height_cm=float(pkg.height_cm) if pkg.height_cm is not None else None,
            depth_cm=float(pkg.depth_cm) if pkg.depth_cm is not None else None,
            quantity=int(pkg.quantity) if pkg.quantity is not None else None,
        )


class OrdersService:
    def __init__(
        self,
        repository: OrdersRepository | None = None,
        address_book_repo: AddressBookRepository | None = None,
    ) -> None:
        self.repository = repository or OrdersRepository()
        self.address_book_repo = address_book_repo or AddressBookRepository()

    def create_draft_from_quote(
        self,
        db: Session,
        *,
        user_id: int,
        payload: CreateDraftFromQuoteRequest,
    ) -> OrderDraftResponse:
        logger.info(
            "Creating order draft: user_id=%s quote_session_id=%s",
            user_id,
            payload.quote_session_id,
        )

        quote_session = self.repository.get_quote_session_by_id(
            db, payload.quote_session_id
        )
        if quote_session is None:
            logger.warning(
                "Quote session not found: quote_session_id=%s user_id=%s",
                payload.quote_session_id,
                user_id,
            )
            raise NotFoundError("Quote session not found")

        if payload.public_token != quote_session.public_token:
            logger.warning(
                "Invalid quote token: quote_session_id=%s user_id=%s",
                payload.quote_session_id,
                user_id,
            )
            raise ForbiddenError("Invalid or missing quote token")

        if quote_session.expires_at and quote_session.expires_at < _utcnow():
            logger.warning(
                "Expired quote session: quote_session_id=%s user_id=%s",
                payload.quote_session_id,
                user_id,
            )
            raise ValidationError("Quote session has expired")

        selected_rate_quote = self.repository.get_selected_rate_quote_for_session(
            db,
            payload.quote_session_id,
        )
        if selected_rate_quote is None:
            logger.warning(
                "No selected rate quote: quote_session_id=%s user_id=%s",
                payload.quote_session_id,
                user_id,
            )
            raise NotFoundError("No selected rate quote for the given quote session")

        existing_draft = self.repository.get_order_draft_by_user_and_quote_session(
            db,
            user_id=user_id,
            quote_session_id=payload.quote_session_id,
        )

        if existing_draft is not None:
            logger.info(
                "Updating existing draft: draft_id=%s user_id=%s",
                existing_draft.id,
                user_id,
            )
            self.repository.update_order_draft_snapshot(
                db,
                order_draft=existing_draft,
                selected_rate_quote_id=selected_rate_quote.id,
                carrier_code_snapshot=selected_rate_quote.carrier_code,
                carrier_name_snapshot=selected_rate_quote.carrier_name,
                tariff_name_snapshot=selected_rate_quote.tariff_name,
                price_snapshot=selected_rate_quote.price,
                carrier_price_snapshot=selected_rate_quote.carrier_price,
                markup_amount_snapshot=selected_rate_quote.markup_amount,
                currency_snapshot=selected_rate_quote.currency,
                eta_days_min_snapshot=selected_rate_quote.eta_days_min,
                eta_days_max_snapshot=selected_rate_quote.eta_days_max,
                from_country_snapshot=quote_session.from_country,
                from_city_snapshot=quote_session.from_city,
                to_country_snapshot=quote_session.to_country,
                to_city_snapshot=quote_session.to_city,
                shipment_type_snapshot=quote_session.shipment_type,
            )

            self._ensure_prefill_package(
                db,
                order_draft=existing_draft,
                quote_session=quote_session,
            )

            db.commit()

            refreshed_draft = self.repository.get_order_draft_by_id(
                db, existing_draft.id
            )
            if refreshed_draft is None:
                raise NotFoundError("Failed to load updated order draft")

            return self._build_order_draft_response(refreshed_draft)

        created_draft = self.repository.create_order_draft(
            db,
            user_id=user_id,
            quote_session_id=payload.quote_session_id,
            selected_rate_quote_id=selected_rate_quote.id,
            carrier_code_snapshot=selected_rate_quote.carrier_code,
            carrier_name_snapshot=selected_rate_quote.carrier_name,
            tariff_name_snapshot=selected_rate_quote.tariff_name,
            price_snapshot=selected_rate_quote.price,
            carrier_price_snapshot=selected_rate_quote.carrier_price,
            markup_amount_snapshot=selected_rate_quote.markup_amount,
            currency_snapshot=selected_rate_quote.currency,
            eta_days_min_snapshot=selected_rate_quote.eta_days_min,
            eta_days_max_snapshot=selected_rate_quote.eta_days_max,
            from_country_snapshot=quote_session.from_country,
            from_city_snapshot=quote_session.from_city,
            to_country_snapshot=quote_session.to_country,
            to_city_snapshot=quote_session.to_city,
            shipment_type_snapshot=quote_session.shipment_type,
        )

        self._ensure_prefill_package(
            db,
            order_draft=created_draft,
            quote_session=quote_session,
        )

        db.commit()
        db.expire(
            created_draft
        )  # force fresh load — expire_on_commit=False leaves packages=[] stale

        draft = self.repository.get_order_draft_by_id(db, created_draft.id)
        if draft is None:
            raise NotFoundError("Failed to load created order draft")

        logger.info(
            "Order draft created: draft_id=%s user_id=%s carrier=%s",
            draft.id,
            user_id,
            draft.carrier_code_snapshot,
        )
        return self._build_order_draft_response(draft)

    def get_order_draft(
        self,
        db: Session,
        *,
        user_id: int,
        draft_id: int,
    ) -> OrderDraftResponse:
        order_draft = self.repository.get_order_draft_by_id(db, draft_id)
        if order_draft is None:
            logger.warning(
                "Order draft not found: draft_id=%s user_id=%s", draft_id, user_id
            )
            raise NotFoundError("Order draft not found")

        if order_draft.user_id != user_id:
            logger.warning(
                "Access denied to draft: draft_id=%s owner_id=%s requester_id=%s",
                draft_id,
                order_draft.user_id,
                user_id,
            )
            raise ForbiddenError("Order draft does not belong to the current user")

        from sqlalchemy import select as _select
        shipment = db.scalar(_select(Shipment).where(Shipment.order_draft_id == draft_id))
        return self._build_order_draft_response(
            order_draft, tracking_number=shipment.tracking_number if shipment else None
        )

    def list_order_drafts(
        self,
        db: Session,
        *,
        user_id: int,
        page_params: PageParams,
    ) -> OrderDraftListResponse:
        import math

        items, total = self.repository.list_drafts_by_user(
            db,
            user_id=user_id,
            offset=page_params.offset,
            limit=page_params.size,
        )
        logger.debug(
            "Listed order drafts: user_id=%s page=%s size=%s total=%s",
            user_id,
            page_params.page,
            page_params.size,
            total,
        )
        from sqlalchemy import select as _select
        draft_ids = [d.id for d in items]
        shipments = (
            db.scalars(_select(Shipment).where(Shipment.order_draft_id.in_(draft_ids))).all()
            if draft_ids else []
        )
        tracking_map = {s.order_draft_id: s.tracking_number for s in shipments}
        return OrderDraftListResponse(
            items=[
                self._build_order_draft_response(d, tracking_number=tracking_map.get(d.id))
                for d in items
            ],
            total=total,
            page=page_params.page,
            size=page_params.size,
            pages=math.ceil(total / page_params.size) if total > 0 else 1,
        )

    def proceed_to_checkout(
        self,
        db: Session,
        *,
        user_id: int,
        draft_id: int,
    ) -> OrderDraftResponse:
        order_draft = self.repository.get_order_draft_by_id(db, draft_id)
        if order_draft is None:
            raise NotFoundError("Order draft not found")
        if order_draft.user_id != user_id:
            raise ForbiddenError("Order draft does not belong to the current user")
        if order_draft.status != "shipment_details_completed":
            raise ValidationError(
                f"Cannot proceed to checkout from status '{order_draft.status}'. "
                "Expected 'shipment_details_completed'."
            )
        if not order_draft.parties or not order_draft.packages:
            raise ValidationError(
                "Sender, recipient and at least one package are required"
            )

        # Final CSE recalc at the payment gate. The customer may have toggled
        # insurance / delivery type on the form; we source the truth from the
        # persisted draft (update_shipment_details ran before us) so what the
        # payment gateway charges equals what CSE will bill. Non-CSE drafts
        # and any recalc failure fall back to the existing snapshots — no
        # silent price change ever.
        declared_total = sum(
            float(p.declared_value or 0) for p in order_draft.packages
        )
        recalc = self._run_cse_recalc(
            db, order_draft,
            delivery_type=order_draft.delivery_type,
            insurance=order_draft.insurance,
            declared_value=declared_total,
        )
        if recalc is not None:
            from decimal import Decimal
            carrier_price, price, currency = recalc
            old_price = order_draft.price_snapshot
            markup = (price - carrier_price).quantize(Decimal("0.01"))
            order_draft.carrier_price_snapshot = carrier_price
            order_draft.markup_amount_snapshot = markup
            order_draft.price_snapshot = price
            order_draft.currency_snapshot = currency
            logger.info(
                "CSE recalc persisted at checkout: draft_id=%s %s → %s %s",
                draft_id, old_price, price, currency,
            )

        self.repository.update_order_draft_status(
            db, order_draft=order_draft, status="ready_for_checkout"
        )
        db.commit()

        refreshed = self.repository.get_order_draft_by_id(db, draft_id)
        if refreshed is None:
            raise NotFoundError("Failed to load order draft")

        logger.info(
            "Order draft moved to checkout: draft_id=%s user_id=%s", draft_id, user_id
        )
        return self._build_order_draft_response(refreshed)

    def confirm_payment_mock(
        self,
        db: Session,
        *,
        user_id: int,
        draft_id: int,
    ) -> OrderDraftResponse:
        """Заглушка подтверждения оплаты.

        Заменить вызовом реального шлюза при интеграции.
        """
        order_draft = self.repository.get_order_draft_by_id(db, draft_id)
        if order_draft is None:
            raise NotFoundError("Order draft not found")
        if order_draft.user_id != user_id:
            raise ForbiddenError("Order draft does not belong to the current user")
        if order_draft.status not in ("ready_for_checkout", "awaiting_payment"):
            raise ValidationError(
                f"Cannot confirm payment from status '{order_draft.status}'"
            )

        self.repository.update_order_draft_status(
            db, order_draft=order_draft, status="paid"
        )
        db.commit()

        refreshed = self.repository.get_order_draft_by_id(db, draft_id)
        if refreshed is None:
            raise NotFoundError("Failed to load order draft")

        logger.info(
            "Order draft paid (mock): draft_id=%s user_id=%s", draft_id, user_id
        )
        return self._build_order_draft_response(refreshed)

    def delete_draft(
        self,
        db: Session,
        *,
        user_id: int,
        draft_id: int,
    ) -> None:
        order_draft = self.repository.get_order_draft_by_id(db, draft_id)
        if order_draft is None:
            logger.warning(
                "Order draft not found: draft_id=%s user_id=%s", draft_id, user_id
            )
            raise NotFoundError("Order draft not found")

        if order_draft.user_id != user_id:
            logger.warning(
                "Access denied to draft: draft_id=%s owner_id=%s requester_id=%s",
                draft_id,
                order_draft.user_id,
                user_id,
            )
            raise ForbiddenError("Order draft does not belong to the current user")

        if order_draft.status not in ("draft", "shipment_details_completed"):
            logger.warning(
                "Delete rejected — wrong status: draft_id=%s status=%s",
                draft_id,
                order_draft.status,
            )
            raise ValidationError("Only unpaid orders can be deleted")

        self.repository.delete_order_draft_by_id(db, draft_id=draft_id)
        db.commit()
        logger.info("Order draft deleted: draft_id=%s user_id=%s", draft_id, user_id)

    def cancel_order(
        self,
        db: Session,
        *,
        user_id: int,
        order_id: int,
        reason: str,
    ) -> OrderDraftResponse:
        """Cancel a paid order at the customer's request.

        Cancellable statuses:
          paid, dispatch_queued, dispatch_failed, pending_manual,
          pending_manual_dispatch, sent_to_carrier.

        For sent_to_carrier we call the carrier API via carrier-gateway. If the
        carrier refuses (already in transit / not supported) we surface 409 and
        instruct the customer to contact support.
        """
        from sqlalchemy import select as _select

        from app.common.status_machine import can_transition
        from app.core.carrier_gateway_client import get_gateway_client
        from app.modules.carriers.api_credentials import CarrierAPICredentialsRepository
        from app.modules.dispatch.models import (
            DispatchJob,
            DispatchJobStatus,
            OrderStatusHistory,
        )
        from app.modules.identity.models import Role, RoleCode, User
        from app.modules.notifications.repository import NotificationsRepository
        from app.modules.notifications.service import NotificationsService
        from app.modules.payments.transaction_models import (
            PaymentStatusHistory,
            PaymentTransaction,
            TxStatus,
        )
        from app.modules.tracking.models import TrackingEvent

        _CANCELLABLE = {
            "paid",
            "dispatch_queued",
            "dispatch_failed",
            "pending_manual",
            "pending_manual_dispatch",
            "sent_to_carrier",
        }

        reason = (reason or "").strip()
        if len(reason) < 3:
            raise ValidationError("Причина отмены должна содержать минимум 3 символа")
        if len(reason) > 500:
            raise ValidationError("Причина отмены не должна превышать 500 символов")

        order = self.repository.get_order_draft_by_id(db, order_id)
        if order is None:
            raise NotFoundError("Заказ не найден")
        if order.user_id != user_id:
            raise ForbiddenError("Заказ не принадлежит текущему пользователю")

        if order.status not in _CANCELLABLE:
            raise ValidationError(
                f"Отмена невозможна для статуса «{order.status}». "
                "Если посылка уже в пути, обратитесь в поддержку."
            )
        if not can_transition(order.status, "cancelled"):
            raise ValidationError(
                f"Переход из статуса «{order.status}» в «cancelled» не разрешён"
            )

        old_status = order.status

        # 1) sent_to_carrier — need to cancel on the carrier's side first.
        if old_status == "sent_to_carrier":
            from app.modules.shipments.models import Shipment as _Shipment
            shipment = db.scalar(
                _select(_Shipment).where(_Shipment.order_draft_id == order.id)
            )
            invoice_id = None
            if shipment:
                invoice_id = (
                    shipment.carrier_tracking_number or shipment.tracking_number
                )
            if not invoice_id:
                raise ValidationError(
                    "Не удалось определить номер накладной перевозчика. "
                    "Обратитесь в поддержку."
                )

            creds = CarrierAPICredentialsRepository().get_by_carrier_code(
                db, order.carrier_code_snapshot
            )
            if not creds or not creds.is_active:
                raise ValidationError(
                    "Отмена через API перевозчика недоступна. Обратитесь в поддержку."
                )
            api_creds = {
                "api_url": creds.api_url,
                "api_token": creds.api_token,
                **(creds.extra_config or {}),
            }
            try:
                ok = get_gateway_client().cancel_invoice(
                    order.carrier_code_snapshot, invoice_id, api_creds
                )
            except Exception as exc:
                logger.warning(
                    "cancel_order: carrier API refused: order_id=%s carrier=%s error=%s",
                    order.id, order.carrier_code_snapshot, exc,
                )
                raise ConflictError(
                    "Перевозчик отклонил отмену. Возможно, заказ уже в пути. "
                    "Обратитесь в поддержку."
                ) from exc
            if not ok:
                raise ConflictError(
                    "Перевозчик отклонил отмену. Обратитесь в поддержку."
                )

        # 2) Cancel queued dispatch job so the worker does not fire after cancel.
        if old_status in ("dispatch_queued", "dispatch_failed", "pending_manual", "pending_manual_dispatch"):
            active_jobs = db.scalars(
                _select(DispatchJob).where(
                    DispatchJob.order_id == order.id,
                    DispatchJob.status.in_(
                        [DispatchJobStatus.QUEUED, DispatchJobStatus.FAILED]
                    ),
                )
            ).all()
            for job in active_jobs:
                job.status = DispatchJobStatus.CANCELLED

        # 3) Flip the order to cancelled.
        self.repository.update_order_draft_status(
            db, order_draft=order, status="cancelled"
        )
        db.add(OrderStatusHistory(
            order_id=order.id,
            old_status=old_status,
            new_status="cancelled",
            changed_by_user_id=user_id,
            source="customer_cancel",
            comment=reason,
        ))
        db.add(TrackingEvent(
            order_draft_id=order.id,
            status="cancelled",
            description=f"Заказ отменён клиентом: {reason}",
        ))

        # 4) Mark the paid payment(s) as refund_pending so admin can initiate refund.
        paid_txs = db.scalars(
            _select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.status == TxStatus.PAID,
            )
        ).all()
        for tx in paid_txs:
            db.add(PaymentStatusHistory(
                payment_id=tx.id,
                old_status=tx.status.value if hasattr(tx.status, "value") else str(tx.status),
                new_status=TxStatus.REFUND_PENDING.value,
                changed_by_user_id=user_id,
                comment=f"Клиент отменил заказ: {reason}",
            ))
            tx.status = TxStatus.REFUND_PENDING

        # 5) Notify admins so they can process the refund.
        notif_repo = NotificationsRepository()
        admins = db.scalars(
            _select(User).join(User.role).where(
                Role.code == RoleCode.ADMIN, User.is_active.is_(True)
            )
        ).all()
        for admin in admins:
            notif_repo.create(
                db,
                user_id=admin.id,
                type="order_cancelled_by_customer",
                title=f"Клиент отменил заказ #{order.id}",
                body=(
                    f"Причина: {reason}. "
                    + (
                        "Требуется оформить возврат средств."
                        if paid_txs else "Возврат средств не требуется."
                    )
                ),
            )

        # 6) Confirm to the customer.
        NotificationsService().notify_order_status(
            db, user_id=order.user_id, order_id=order.id, status="cancelled"
        )

        db.commit()

        refreshed = self.repository.get_order_draft_by_id(db, order_id)
        if refreshed is None:
            raise NotFoundError("Failed to reload order")

        logger.info(
            "Order cancelled by customer: order_id=%s user_id=%s from_status=%s "
            "refund_pending=%d",
            order.id, user_id, old_status, len(paid_txs),
        )
        return self._build_order_draft_response(refreshed)

    def update_shipment_details(
        self,
        db: Session,
        *,
        user_id: int,
        draft_id: int,
        payload: UpdateShipmentDetailsRequest,
    ) -> OrderDraftResponse:
        order_draft = self.repository.get_order_draft_by_id(db, draft_id)
        if order_draft is None:
            logger.warning(
                "Order draft not found: draft_id=%s user_id=%s", draft_id, user_id
            )
            raise NotFoundError("Order draft not found")

        if order_draft.user_id != user_id:
            logger.warning(
                "Access denied to draft: draft_id=%s owner_id=%s requester_id=%s",
                draft_id,
                order_draft.user_id,
                user_id,
            )
            raise ForbiddenError("Order draft does not belong to the current user")

        _EDITABLE_STATUSES = {"draft", "shipment_details_completed"}
        if order_draft.status not in _EDITABLE_STATUSES:
            logger.warning(
                "update_shipment_details rejected — wrong status: draft_id=%s status=%s",
                draft_id,
                order_draft.status,
            )
            raise ValidationError(
                f"Cannot edit shipment details for order in status '{order_draft.status}'"
            )

        self.repository.delete_shipment_parties(db, order_draft_id=draft_id)
        self.repository.delete_shipment_packages(db, order_draft_id=draft_id)

        self._create_party(
            db, order_draft_id=draft_id, role="sender", payload=payload.sender
        )
        self._create_party(
            db, order_draft_id=draft_id, role="recipient", payload=payload.recipient
        )

        for item in payload.packages:
            self.repository.create_shipment_package(
                db,
                order_draft_id=draft_id,
                description=item.description,
                quantity=item.quantity,
                weight_kg=item.weight_kg,
                width_cm=item.width_cm,
                height_cm=item.height_cm,
                depth_cm=item.depth_cm,
                declared_value=item.declared_value,
                declared_value_currency=item.declared_value_currency,
            )

        order_draft.call_before_delivery = payload.call_before_delivery
        order_draft.insurance = payload.insurance
        order_draft.fragile = payload.fragile

        order_draft.delivery_type = payload.delivery_type
        order_draft.sender_pvz_guid = payload.sender_pvz_guid
        order_draft.recipient_pvz_guid = payload.recipient_pvz_guid

        if payload.sender.save_to_address_book:
            self._save_address_book(db, user_id=user_id, party=payload.sender)
        if payload.recipient.save_to_address_book:
            self._save_address_book(db, user_id=user_id, party=payload.recipient)

        # Persist recalc: weight/dim edits in the shipment form must be
        # reflected in price_snapshot before proceed_to_checkout.
        db.flush()
        db.refresh(order_draft)
        self._persist_recalc(
            db, order_draft,
            delivery_type=payload.delivery_type,
            insurance=payload.insurance,
            declared_value=float(payload.packages[0].declared_value or 0)
                if payload.packages else 0.0,
        )

        self.repository.update_order_draft_status(
            db,
            order_draft=order_draft,
            status="shipment_details_completed",
        )

        db.commit()

        refreshed_draft = self.repository.get_order_draft_by_id(db, draft_id)
        if refreshed_draft is None:
            raise NotFoundError("Failed to load updated order draft")

        logger.info(
            "Shipment details updated: draft_id=%s user_id=%s packages=%s",
            draft_id,
            user_id,
            len(payload.packages),
        )
        return self._build_order_draft_response(refreshed_draft)

    def cse_recalc(
        self,
        db: Session,
        *,
        user_id: int,
        draft_id: int,
        payload: CseRecalcRequest,
    ) -> CseRecalcResponse:
        """Recalculate a draft's price for the current carrier/tariff.

        CSE goes through the live Calc API (services + declared value).
        Other carriers use the tariff engine with the supplied weight/dims.
        Idempotent — no DB writes.
        """
        order_draft = self.repository.get_order_draft_by_id(db, draft_id)
        if order_draft is None:
            raise NotFoundError("Order draft not found")
        if order_draft.user_id != user_id:
            raise ForbiddenError("Order draft does not belong to the current user")

        overrides = _RecalcOverrides.from_payload(payload)

        carrier_code = (order_draft.carrier_code_snapshot or "").lower()
        if carrier_code == "cse":
            result = self._run_cse_recalc(
                db,
                order_draft,
                delivery_type=payload.delivery_type,
                insurance=payload.insurance,
                declared_value=float(payload.declared_value or 0),
                overrides=overrides,
            )
        else:
            result = self._run_generic_recalc(db, order_draft, overrides=overrides)

        if result is None:
            return CseRecalcResponse(
                price=order_draft.price_snapshot,
                carrier_price=order_draft.carrier_price_snapshot or order_draft.price_snapshot,
                currency=order_draft.currency_snapshot,
                recalculated=False,
            )
        carrier_price, price, currency = result
        return CseRecalcResponse(
            price=price, carrier_price=carrier_price,
            currency=currency, recalculated=True,
        )

    def _run_cse_recalc(
        self,
        db: Session,
        order_draft: OrderDraft,
        *,
        delivery_type: str,
        insurance: bool,
        declared_value: float,
        overrides: "_RecalcOverrides | None" = None,
    ):
        """Shared helper for the preview endpoint + the persist step at
        checkout. Returns (carrier_price, price_with_markup, currency) on
        success or None on any failure / non-CSE carrier.
        """
        from decimal import Decimal

        if (order_draft.carrier_code_snapshot or "").lower() != "cse":
            return None

        from app.modules.quotes.models import RateQuote
        rq = db.get(RateQuote, order_draft.selected_rate_quote_id)
        if rq is None or not rq.urgency_guid:
            logger.warning(
                "CSE recalc: missing rate_quote or urgency_guid (draft=%s)",
                order_draft.id,
            )
            return None
        quote_session = db.get(QuoteSession, order_draft.quote_session_id)
        if quote_session is None:
            return None
        ov = overrides or _RecalcOverrides()

        try:
            from app.modules.carriers.api_credentials import CarrierAPICredentialsRepository
            creds_row = CarrierAPICredentialsRepository().get_by_carrier_code(db, "cse")
            if not creds_row or not creds_row.is_active:
                raise RuntimeError("CSE creds inactive")
            creds = {
                "api_url": creds_row.api_url or "",
                "api_token": creds_row.api_token or "",
                **(creds_row.extra_config or {}),
            }
        except Exception as exc:
            logger.warning("CSE recalc: creds unavailable: %s", exc)
            return None

        try:
            from app.modules.carriers.cse_geography import get_city_guid
            from_guid = get_city_guid(order_draft.from_city_snapshot, creds)
            to_guid = get_city_guid(order_draft.to_city_snapshot, creds)
        except Exception as exc:
            logger.warning("CSE recalc: geography lookup failed: %s", exc)
            return None
        if not from_guid or not to_guid:
            return None

        qty = int(ov.quantity if ov.quantity is not None else (quote_session.quantity or 1))
        weight_one = float(ov.weight_kg if ov.weight_kg is not None else quote_session.weight_kg)
        weight_kg = weight_one * qty
        vol = 0.0
        w = float(ov.width_cm if ov.width_cm is not None else (quote_session.width_cm or 0))
        h = float(ov.height_cm if ov.height_cm is not None else (quote_session.height_cm or 0))
        d = float(ov.depth_cm if ov.depth_cm is not None else (quote_session.depth_cm or 0))
        if w > 0 and h > 0 and d > 0:
            vol = (w * h * d / 5000.0) * qty

        _DELIVERY_MAP = {
            "door_to_door":           "ДоставкаДоДверей",
            "warehouse_to_door":      "СкладДверь",
            "door_to_warehouse":      "Самовывоз",
            "warehouse_to_warehouse": "СкладСклад",
        }
        cse_delivery = _DELIVERY_MAP.get(delivery_type, "")

        # Services are mutually exclusive per CSE error 05021.
        from app.modules.carriers.api_clients.cse import (
            CSEAPIClient, _CSE_SERVICE_GUIDS,
        )
        service_guids: list[str] = []
        if insurance:
            service_guids.append(_CSE_SERVICE_GUIDS["insurance"])
        elif declared_value > 0:
            service_guids.append(_CSE_SERVICE_GUIDS["declared_value"])

        try:
            tariff = CSEAPIClient().recalc_with_extras(
                from_guid, to_guid, weight_kg, 1, creds,
                urgency_guid=rq.urgency_guid,
                volume_weight=vol,
                delivery_of_cargo=cse_delivery,
                declared_value=declared_value,
                insurance_rate=declared_value if insurance else 0.0,
                additional_service_guids=service_guids or None,
            )
        except Exception as exc:
            logger.warning("CSE recalc: Calc call failed: %s", exc)
            return None

        if not tariff:
            return None

        from app.modules.commissions.markup import build_markup_calculator
        markup_calc = build_markup_calculator(db, ["cse"])
        carrier_price = Decimal(str(round(float(tariff["price"]), 2)))
        markup = markup_calc.markup_for("cse", carrier_price)
        price = (carrier_price + markup).quantize(Decimal("0.01"))
        currency = str(tariff.get("currency") or order_draft.currency_snapshot)
        return carrier_price, price, currency

    def _run_generic_recalc(
        self,
        db: Session,
        order_draft: OrderDraft,
        *,
        overrides: _RecalcOverrides | None = None,
    ):
        """Recalculate for non-CSE carriers via the tariff engine.

        Uses the carrier + tariff already selected on the draft (matches by
        carrier_code_snapshot and tariff_name_snapshot). Returns
        (carrier_price, price_with_markup, currency) or None on any failure.
        """
        from decimal import Decimal

        from app.modules.carriers.tariff_engine import calculate_quotes
        from app.modules.commissions.markup import build_markup_calculator

        quote_session = db.get(QuoteSession, order_draft.quote_session_id)
        if quote_session is None:
            return None
        ov = overrides or _RecalcOverrides()

        weight_kg = float(ov.weight_kg if ov.weight_kg is not None else quote_session.weight_kg)
        qty = int(ov.quantity if ov.quantity is not None else (quote_session.quantity or 1))
        width_cm = float(ov.width_cm if ov.width_cm is not None else (quote_session.width_cm or 0))
        height_cm = float(ov.height_cm if ov.height_cm is not None else (quote_session.height_cm or 0))
        depth_cm = float(ov.depth_cm if ov.depth_cm is not None else (quote_session.depth_cm or 0))

        if weight_kg <= 0:
            return None

        carrier_code = (order_draft.carrier_code_snapshot or "").lower()

        # Exline is priced live via its Calc API when its rates are not
        # mirrored in carrier_tariff_rates. Skipping the live call would
        # return an empty Exline result set and leave the customer looking
        # at a stale snapshot. For every other carrier the DB path (Azimuth
        # zone table + carrier_tariff_rates) is authoritative — no network.
        include_live = carrier_code == "exline"

        try:
            quotes = calculate_quotes(
                from_city=order_draft.from_city_snapshot,
                to_city=order_draft.to_city_snapshot,
                weight_kg=weight_kg,
                quantity=qty,
                width_cm=width_cm,
                height_cm=height_cm,
                depth_cm=depth_cm,
                db=db,
                include_live=include_live,
            )
        except Exception as exc:
            logger.warning(
                "generic recalc: tariff_engine call failed (draft=%s carrier=%s): %s",
                order_draft.id, carrier_code, exc,
            )
            return None

        tariff_name = (order_draft.tariff_name_snapshot or "").strip().lower()
        matched = None
        for q in quotes:
            if q.carrier_code.lower() != carrier_code:
                continue
            if q.tariff_name.strip().lower() == tariff_name:
                matched = q
                break
        # Fallback: same carrier, any tariff — better than a stale price.
        if matched is None:
            for q in quotes:
                if q.carrier_code.lower() == carrier_code:
                    matched = q
                    break
        if matched is None:
            return None

        markup_calc = build_markup_calculator(db, [carrier_code])
        carrier_price = Decimal(str(matched.price)).quantize(Decimal("0.01"))
        markup = markup_calc.markup_for(carrier_code, carrier_price)
        price = (carrier_price + markup).quantize(Decimal("0.01"))
        currency = matched.currency or order_draft.currency_snapshot
        return carrier_price, price, currency

    def _persist_recalc(
        self,
        db: Session,
        order_draft: OrderDraft,
        *,
        delivery_type: str,
        insurance: bool,
        declared_value: float,
    ) -> None:
        """Recalc for a persisted draft and write price_snapshot in place.

        Called at the end of update_shipment_details so any weight/dim edit
        the customer made reaches price_snapshot before checkout. Silent
        no-op if the engine cannot produce a price (missing tariffs, network
        failure, etc.) — the previous snapshot stays and the customer sees
        the same total they saw before.
        """
        from decimal import Decimal

        overrides = _RecalcOverrides.from_order_draft(order_draft)
        carrier_code = (order_draft.carrier_code_snapshot or "").lower()

        if carrier_code == "cse":
            result = self._run_cse_recalc(
                db, order_draft,
                delivery_type=delivery_type,
                insurance=insurance,
                declared_value=declared_value,
                overrides=overrides,
            )
        else:
            result = self._run_generic_recalc(db, order_draft, overrides=overrides)

        if result is None:
            logger.info(
                "persist recalc: no result — keeping snapshot (draft=%s carrier=%s)",
                order_draft.id, carrier_code,
            )
            return

        carrier_price, price, currency = result
        old_price = order_draft.price_snapshot
        order_draft.carrier_price_snapshot = Decimal(str(carrier_price))
        order_draft.price_snapshot = Decimal(str(price))
        order_draft.markup_amount_snapshot = (Decimal(str(price)) - Decimal(str(carrier_price))).quantize(Decimal("0.01"))
        order_draft.currency_snapshot = currency
        logger.info(
            "persist recalc: draft=%s carrier=%s old=%s new=%s",
            order_draft.id, carrier_code, old_price, price,
        )

    def _ensure_prefill_package(
        self,
        db: Session,
        *,
        order_draft: OrderDraft,
        quote_session: QuoteSession,
    ) -> None:
        if order_draft.packages:
            return

        description = self._quote_session_package_description(quote_session)

        self.repository.create_shipment_package(
            db,
            order_draft_id=order_draft.id,
            description=description,
            quantity=quote_session.quantity,
            weight_kg=quote_session.weight_kg,
            width_cm=quote_session.width_cm,
            height_cm=quote_session.height_cm,
            depth_cm=quote_session.depth_cm,
            declared_value=None,
            declared_value_currency=None,
        )

    def _quote_session_package_description(self, quote_session: QuoteSession) -> str:
        shipment_type = quote_session.shipment_type.strip().lower()
        if shipment_type == "document":
            return "Documents"
        if shipment_type == "parcel":
            return "Parcel"
        return quote_session.shipment_type.strip() or "Shipment"

    def _save_address_book(
        self,
        db: Session,
        *,
        user_id: int,
        party: ShipmentPartyInput,
    ) -> None:
        self.address_book_repo.create(
            db,
            user_id=user_id,
            label=None,
            full_name=party.full_name,
            phone=party.phone,
            email=party.email,
            company_name=party.company_name,
            tax_id=party.tax_id,
            country=party.country,
            city=party.city,
            address_line1=party.address_line1,
            address_line2=party.address_line2,
            postal_code=party.postal_code,
            is_default=False,
        )
        logger.debug("Address auto-saved for user_id=%s", user_id)

    def _create_party(
        self,
        db: Session,
        *,
        order_draft_id: int,
        role: str,
        payload: ShipmentPartyInput,
    ) -> None:
        self.repository.create_shipment_party(
            db,
            order_draft_id=order_draft_id,
            role=role,
            full_name=payload.full_name,
            phone=payload.phone,
            email=payload.email,
            company_name=payload.company_name,
            tax_id=payload.tax_id,
            country=payload.country,
            city=payload.city,
            address_line1=payload.address_line1,
            address_line2=payload.address_line2,
            postal_code=payload.postal_code,
            comment=payload.comment,
        )

    def _build_order_draft_response(
        self, order_draft: OrderDraft, tracking_number: str | None = None
    ) -> OrderDraftResponse:
        sender = self._find_party(order_draft.parties, "sender")
        recipient = self._find_party(order_draft.parties, "recipient")

        return OrderDraftResponse(
            draft_id=order_draft.id,
            user_id=order_draft.user_id,
            quote_session_id=order_draft.quote_session_id,
            selected_rate_quote_id=order_draft.selected_rate_quote_id,
            status=order_draft.status,  # type: ignore[arg-type]
            carrier_code_snapshot=order_draft.carrier_code_snapshot,
            carrier_name_snapshot=order_draft.carrier_name_snapshot,
            tariff_name_snapshot=order_draft.tariff_name_snapshot,
            price_snapshot=order_draft.price_snapshot,
            currency_snapshot=order_draft.currency_snapshot,
            eta_days_min_snapshot=order_draft.eta_days_min_snapshot,
            eta_days_max_snapshot=order_draft.eta_days_max_snapshot,
            from_country_snapshot=order_draft.from_country_snapshot,
            from_city_snapshot=order_draft.from_city_snapshot,
            to_country_snapshot=order_draft.to_country_snapshot,
            to_city_snapshot=order_draft.to_city_snapshot,
            shipment_type_snapshot=order_draft.shipment_type_snapshot,
            call_before_delivery=order_draft.call_before_delivery,
            insurance=order_draft.insurance,
            fragile=order_draft.fragile,
            delivery_type=order_draft.delivery_type,  # type: ignore[arg-type]
            sender_pvz_guid=order_draft.sender_pvz_guid,
            recipient_pvz_guid=order_draft.recipient_pvz_guid,
            created_at=order_draft.created_at,
            sender=self._map_party(sender) if sender else None,
            recipient=self._map_party(recipient) if recipient else None,
            packages=[self._map_package(item) for item in order_draft.packages],
            tracking_number=tracking_number,
        )

    def _find_party(
        self, parties: list[ShipmentParty], role: str
    ) -> ShipmentParty | None:
        for party in parties:
            if party.role == role:
                return party
        return None

    def _map_party(self, party: ShipmentParty) -> ShipmentPartyResponse:
        return ShipmentPartyResponse(
            id=party.id,
            role=party.role,  # type: ignore[arg-type]
            full_name=party.full_name,
            phone=party.phone,
            email=party.email,
            company_name=party.company_name,
            tax_id=party.tax_id,
            country=party.country,
            city=party.city,
            address_line1=party.address_line1,
            address_line2=party.address_line2,
            postal_code=party.postal_code,
            comment=party.comment,
        )

    def _map_package(self, item: ShipmentPackage) -> ShipmentPackageResponse:
        return ShipmentPackageResponse(
            id=item.id,
            description=item.description,
            quantity=item.quantity,
            weight_kg=item.weight_kg,
            width_cm=item.width_cm,
            height_cm=item.height_cm,
            depth_cm=item.depth_cm,
            declared_value=item.declared_value,
            declared_value_currency=item.declared_value_currency,
        )
