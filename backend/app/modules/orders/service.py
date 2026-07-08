from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.common.pagination import PageParams
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
        """Second Calc for a CSE draft including add-on services.

        Idempotent, no DB writes. Returns fully-loaded customer-facing price
        for the currently selected urgency. On any resolution failure or if
        the carrier is not CSE, echoes the draft's current price_snapshot so
        the FE can call this endpoint unconditionally without branching.
        """
        order_draft = self.repository.get_order_draft_by_id(db, draft_id)
        if order_draft is None:
            raise NotFoundError("Order draft not found")
        if order_draft.user_id != user_id:
            raise ForbiddenError("Order draft does not belong to the current user")

        result = self._run_cse_recalc(
            db,
            order_draft,
            delivery_type=payload.delivery_type,
            insurance=payload.insurance,
            declared_value=float(payload.declared_value or 0),
        )
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

        weight_kg = float(quote_session.weight_kg) * int(quote_session.quantity or 1)
        vol = 0.0
        w = float(quote_session.width_cm or 0)
        h = float(quote_session.height_cm or 0)
        d = float(quote_session.depth_cm or 0)
        if w > 0 and h > 0 and d > 0:
            vol = (w * h * d / 5000.0) * int(quote_session.quantity or 1)

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
