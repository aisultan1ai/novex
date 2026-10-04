from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.common.time_utils import utcnow as _utcnow
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.modules.address_book.repository import AddressBookRepository
from app.modules.orders.models import OrderDraft, ShipmentPackage, ShipmentParty
from app.modules.orders.repository import OrdersRepository
from app.modules.orders.schemas import (
    CreateDraftFromQuoteRequest,
    CseRecalcRequest,
    CseRecalcResponse,
    OrderDraftListResponse,
    OrderDraftResponse,
    ReschedulePickupRequest,
    ReschedulePickupResponse,
    ShipmentPackageResponse,
    ShipmentPartyInput,
    ShipmentPartyResponse,
    UpdateShipmentDetailsRequest,
)
from app.modules.quotes.models import QuoteSession
from app.modules.shipments.models import Shipment

logger = logging.getLogger(__name__)


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
                # Freeze urgency_guid so dispatch survives RateQuote cleanup.
                urgency_guid_snapshot=selected_rate_quote.urgency_guid,
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
            urgency_guid_snapshot=selected_rate_quote.urgency_guid,
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

        from app.modules.cancellations.repository import (
            CancellationRequestsRepository,
        )

        shipment = db.scalar(_select(Shipment).where(Shipment.order_draft_id == draft_id))
        # На detail-view отдаём последнюю заявку любого статуса — pending для
        # блока «ожидание», rejected — чтобы клиент увидел причину отказа.
        cr = CancellationRequestsRepository().get_latest_for_order(db, draft_id)
        return self._build_order_draft_response(
            order_draft,
            tracking_number=shipment.tracking_number if shipment else None,
            cancellation_request=cr,
        )

    def list_order_drafts(
        self,
        db: Session,
        *,
        user_id: int,
        page_params: PageParams,
        statuses: list[str] | None = None,
    ) -> OrderDraftListResponse:
        import math

        items, total = self.repository.list_drafts_by_user(
            db,
            user_id=user_id,
            offset=page_params.offset,
            limit=page_params.size,
            statuses=statuses,
        )
        logger.debug(
            "Listed order drafts: user_id=%s page=%s size=%s total=%s",
            user_id,
            page_params.page,
            page_params.size,
            total,
        )
        from sqlalchemy import select as _select

        from app.modules.cancellations.models import CancellationRequest
        from app.modules.cancellations.repository import (
            CancellationRequestsRepository,
        )

        draft_ids = [d.id for d in items]
        shipments = (
            db.scalars(_select(Shipment).where(Shipment.order_draft_id.in_(draft_ids))).all()
            if draft_ids else []
        )
        tracking_map = {s.order_draft_id: s.tracking_number for s in shipments}

        # В листе показываем только pending — этого достаточно для бейджа
        # «Запрошена отмена». Полную историю берём только на detail-view.
        pending_ids = CancellationRequestsRepository().order_ids_with_pending(
            db, draft_ids
        )
        pending_rows = (
            db.scalars(
                _select(CancellationRequest).where(
                    CancellationRequest.order_draft_id.in_(pending_ids),
                    CancellationRequest.status == "pending",
                )
            ).all()
            if pending_ids else []
        )
        pending_map = {r.order_draft_id: r for r in pending_rows}
        return OrderDraftListResponse(
            items=[
                self._build_order_draft_response(
                    d,
                    tracking_number=tracking_map.get(d.id),
                    cancellation_request=pending_map.get(d.id),
                )
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
    ):
        """Клиентская отмена заказа — тонкая обёртка над
        CancellationRequestsService.request_cancellation.

        Возможные исходы (см. CancelOrderResponse.outcome):
          • "cancelled" — заказ прямо сейчас в статусе cancelled. Так бывает,
            когда у перевозчика есть API отмены (CSE/Exline) и запрос прошёл.
          • "requested" — создали заявку, ждём подтверждения перевозчика или
            админа. Актуально для Azimuth (у него нет API) и для CSE/Exline,
            когда API отказал (например, «ожидает синхронизации» у Exline).

        Все дальнейшие шаги (сторно комиссии, refund_pending, уведомления)
        живут внутри CancellationRequestsService.
        """
        from app.modules.cancellations.service import CancellationRequestsService
        from app.modules.orders.schemas import (
            CancellationRequestSnippet,
            CancelOrderResponse,
        )

        outcome = CancellationRequestsService().request_cancellation(
            db, user_id=user_id, order_id=order_id, reason=reason,
        )

        # Заново читаем заказ и последнюю заявку — статус мог измениться
        # (cancelled) либо появился pending, который нужно отдать клиенту в
        # карточке заказа.
        from sqlalchemy import select as _select

        from app.modules.cancellations.repository import (
            CancellationRequestsRepository,
        )

        refreshed = self.repository.get_order_draft_by_id(db, order_id)
        if refreshed is None:
            raise NotFoundError("Failed to reload order")
        shipment = db.scalar(
            _select(Shipment).where(Shipment.order_draft_id == order_id)
        )
        latest_req = CancellationRequestsRepository().get_latest_for_order(db, order_id)
        order_response = self._build_order_draft_response(
            refreshed,
            tracking_number=shipment.tracking_number if shipment else None,
            cancellation_request=latest_req,
        )

        snippet = None
        if outcome.request is not None:
            snippet = CancellationRequestSnippet.model_validate(
                outcome.request.model_dump()
            )

        logger.info(
            "cancel_order → %s: order_id=%s user_id=%s status=%s",
            outcome.kind, order_id, user_id, refreshed.status,
        )
        return CancelOrderResponse(
            outcome=outcome.kind,
            order=order_response,
            request=snippet,
        )

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
        if payload.pd_consent and order_draft.pd_consent_at is None:
            from app.common.time_utils import utcnow as _utcnow
            order_draft.pd_consent_at = _utcnow()
        order_draft.fragile = payload.fragile

        order_draft.delivery_type = payload.delivery_type
        order_draft.sender_pvz_guid = payload.sender_pvz_guid
        order_draft.recipient_pvz_guid = payload.recipient_pvz_guid

        # Courier pickup opt-in. The schema validator already normalised the
        # dependent fields (wipes them when requested=False, backfills
        # contact_person/phone from sender when blank).
        order_draft.pickup_requested = payload.pickup_requested
        order_draft.pickup_date = payload.pickup_date
        order_draft.pickup_time_slot = payload.pickup_time_slot
        order_draft.pickup_contact_person = payload.pickup_contact_person
        order_draft.pickup_contact_phone = payload.pickup_contact_phone
        # Editing shipment details clears any previous pickup error so a
        # retried dispatch can succeed. Do NOT wipe pickup_scheduled_azimuth_id —
        # that stays as the idempotency lock for orders already handed off.
        order_draft.pickup_error = None

        if payload.sender.save_to_address_book:
            self._save_address_book(db, user_id=user_id, party=payload.sender)
        if payload.recipient.save_to_address_book:
            self._save_address_book(db, user_id=user_id, party=payload.recipient)

        # Persist recalc: weight/dim edits in the shipment form must be
        # reflected in price_snapshot before proceed_to_checkout.
        # Use SUM of declared values across all packages so this matches
        # proceed_to_checkout's `declared_total` calculation — otherwise a
        # multi-package order would get two different prices at the two
        # gates.
        db.flush()
        db.refresh(order_draft)
        declared_total = sum(
            float(pkg.declared_value or 0) for pkg in payload.packages
        )
        self._persist_recalc(
            db, order_draft,
            delivery_type=payload.delivery_type,
            insurance=payload.insurance,
            declared_value=declared_total,
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

    # Statuses at which the customer can still change the pickup date/time.
    # Later stages ("picked_up" and onward) mean the courier is already
    # holding the parcel — no point trying to cancel the waybill.
    _PICKUP_RESCHEDULE_ALLOWED_STATUSES: frozenset[str] = frozenset({
        "dispatch_queued",
        "sent_to_carrier",
        "dispatch_failed",
    })

    def reschedule_pickup(
        self,
        db: Session,
        *,
        user_id: int,
        draft_id: int,
        payload: ReschedulePickupRequest,
    ) -> ReschedulePickupResponse:
        """Change the courier pickup date/time for a paid order.

        Steps:
          1. Load order + ownership check.
          2. Guard: status ∈ _PICKUP_RESCHEDULE_ALLOWED_STATUSES.
          3. Guard: new pickup_date >= today.
          4. If a carrier waybill already exists (sent_to_carrier), ask the
             carrier gateway to cancel it. Failure to cancel is NOT fatal
             for the customer's request — we still update the local pickup
             fields and re-queue dispatch; admin will reconcile.
          5. Clear shipment.carrier_tracking_number so the idempotency guard
             in dispatch_worker forces a fresh create_invoice next tick.
          6. Update pickup_date / pickup_time_slot / pickup_error=None.
          7. Transition order to dispatch_queued (if not already) and create
             a new DispatchJob. Publish to the Redis stream so the worker
             picks it up immediately.

        Non-goals: does NOT block on the new create_invoice succeeding.
        Dispatch is async, worker will notify via existing pipeline.
        """
        from datetime import date as _date

        order_draft = self.repository.get_order_draft_by_id(db, draft_id)
        if order_draft is None:
            raise NotFoundError("Order draft not found")
        if order_draft.user_id != user_id:
            raise ForbiddenError("Order draft does not belong to the current user")

        if order_draft.status not in self._PICKUP_RESCHEDULE_ALLOWED_STATUSES:
            raise ValidationError(
                f"Нельзя перенести забор в статусе '{order_draft.status}' — "
                "курьер уже приехал или заказ ещё не оплачен"
            )
        if payload.pickup_date < _date.today():
            raise ValidationError("Дата забора не может быть в прошлом")

        # Update local pickup fields first so the new dispatch attempt uses them.
        order_draft.pickup_requested = True
        order_draft.pickup_date = payload.pickup_date
        order_draft.pickup_time_slot = payload.pickup_time_slot
        order_draft.pickup_error = None

        # Cancel the existing carrier waybill (if any). Failure is logged but
        # non-fatal — we still re-queue dispatch and let admin reconcile the
        # abandoned waybill if the carrier ever billed for it.
        from sqlalchemy import select as _select

        shipment = db.scalar(
            _select(Shipment).where(Shipment.order_draft_id == draft_id)
        )
        old_waybill = shipment.carrier_tracking_number if shipment else None
        if shipment and shipment.carrier_tracking_number:
            try:
                from app.core.carrier_gateway_client import get_gateway_client
                from app.modules.carriers.creds_cache import (
                    get_creds as _get_carrier_creds,
                )

                creds = _get_carrier_creds(db, order_draft.carrier_code_snapshot)
                get_gateway_client().cancel_invoice(
                    order_draft.carrier_code_snapshot,
                    shipment.carrier_tracking_number,
                    creds,
                )
                logger.info(
                    "reschedule_pickup: cancelled old waybill %s for order %s",
                    shipment.carrier_tracking_number, draft_id,
                )
            except Exception:
                logger.exception(
                    "reschedule_pickup: failed to cancel waybill %s for order %s "
                    "(non-fatal — proceeding with re-dispatch)",
                    shipment.carrier_tracking_number, draft_id,
                )
                # The old waybill is still live at the carrier — a courier may
                # come twice. Flag it for the admin/operator to cancel by hand.
                previous = order_draft.orphan_waybill_number
                order_draft.orphan_waybill_number = (
                    f"{previous}, {shipment.carrier_tracking_number}"
                    if previous else shipment.carrier_tracking_number
                )
            # Wipe the tracking number so dispatch_worker's idempotency
            # guard does NOT skip create_invoice this time.
            shipment.carrier_tracking_number = None
            shipment.carrier_barcode = None
            shipment.status = "pending"

        # Re-queue dispatch. If we're already in dispatch_queued (worker not
        # yet picked it up), skip the transition but still enqueue a new job
        # so the pickup_date change is retried.
        from app.modules.dispatch.service import create_dispatch_job

        if order_draft.status == "dispatch_queued":
            # A previous DispatchJob may still be in QUEUED/PROCESSING with
            # the old pickup_date. It'll re-read order.pickup_date when it
            # fires, so bumping status is unnecessary — just enqueue a new
            # job to make sure a worker picks it up promptly.
            outcome = "already_scheduled_new"
        else:
            outcome = "rescheduled"

        # create_dispatch_job() handles the status transition through the
        # state machine (sent_to_carrier → dispatch_queued, paid →
        # dispatch_queued, or dispatch_failed → dispatch_queued — all allowed).
        # If we're already in dispatch_queued the current status.machine
        # rejects the same-status transition, so we skip create_dispatch_job
        # in that branch and let the existing job re-read pickup_date.
        if outcome == "rescheduled":
            dispatch_job = create_dispatch_job(
                db, order=order_draft, changed_by_user_id=user_id,
                source="customer_reschedule",
            )
        else:
            dispatch_job = None

        db.flush()

        # Publish stream event AFTER db.flush() — but our caller (endpoint)
        # does the commit. We publish inside a try/except so a Redis outage
        # doesn't break the endpoint response; polling will still catch the
        # job. Skip publishing when we didn't enqueue a new job.
        if dispatch_job is not None:
            try:
                from app.core.streams import STREAM_DISPATCH
                from app.core.streams import publish as stream_publish
                stream_publish(STREAM_DISPATCH, {
                    "dispatch_job_id": str(dispatch_job.id),
                    "order_id": str(order_draft.id),
                })
            except Exception:
                logger.exception(
                    "reschedule_pickup: failed to publish dispatch event for order %s "
                    "(polling will pick it up)", draft_id,
                )

        db.refresh(order_draft)
        return ReschedulePickupResponse(
            outcome=outcome,
            order=self._build_order_draft_response(
                order_draft,
                tracking_number=shipment.tracking_number if shipment else None,
            ),
        )

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
        self,
        order_draft: OrderDraft,
        tracking_number: str | None = None,
        cancellation_request=None,
    ) -> OrderDraftResponse:
        from app.modules.orders.schemas import CancellationRequestSnippet

        sender = self._find_party(order_draft.parties, "sender")
        recipient = self._find_party(order_draft.parties, "recipient")

        snippet = None
        if cancellation_request is not None:
            snippet = CancellationRequestSnippet.model_validate(cancellation_request)

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
            pickup_requested=order_draft.pickup_requested,
            pickup_date=order_draft.pickup_date,
            pickup_time_slot=order_draft.pickup_time_slot,
            pickup_contact_person=order_draft.pickup_contact_person,
            pickup_contact_phone=order_draft.pickup_contact_phone,
            pickup_scheduled=order_draft.pickup_scheduled_azimuth_id is not None,
            pickup_error=order_draft.pickup_error,
            created_at=order_draft.created_at,
            sender=self._map_party(sender) if sender else None,
            recipient=self._map_party(recipient) if recipient else None,
            packages=[self._map_package(item) for item in order_draft.packages],
            tracking_number=tracking_number,
            cancellation_request=snippet,
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
