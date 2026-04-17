from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.orders.models import OrderDraft, ShipmentPackage, ShipmentParty
from app.modules.orders.repository import OrdersRepository
from app.modules.orders.schemas import (
    CreateDraftFromQuoteRequest,
    OrderDraftResponse,
    ShipmentPackageResponse,
    ShipmentPartyInput,
    ShipmentPartyResponse,
    UpdateShipmentDetailsRequest,
)
from app.modules.quotes.models import QuoteSession


class OrdersService:
    def __init__(self, repository: OrdersRepository | None = None) -> None:
        self.repository = repository or OrdersRepository()

    def create_draft_from_quote(
        self,
        db: Session,
        *,
        user_id: int,
        payload: CreateDraftFromQuoteRequest,
    ) -> OrderDraftResponse:
        quote_session = self.repository.get_quote_session_by_id(db, payload.quote_session_id)
        if quote_session is None:
            raise ValueError("Quote session not found")

        selected_rate_quote = self.repository.get_selected_rate_quote_for_session(
            db,
            payload.quote_session_id,
        )
        if selected_rate_quote is None:
            raise ValueError("No selected rate quote for the given quote session")

        existing_draft = self.repository.get_order_draft_by_user_and_quote_session(
            db,
            user_id=user_id,
            quote_session_id=payload.quote_session_id,
        )

        if existing_draft is not None:
            self.repository.update_order_draft_snapshot(
                db,
                order_draft=existing_draft,
                selected_rate_quote_id=selected_rate_quote.id,
                carrier_code_snapshot=selected_rate_quote.carrier_code,
                carrier_name_snapshot=selected_rate_quote.carrier_name,
                tariff_name_snapshot=selected_rate_quote.tariff_name,
                price_snapshot=selected_rate_quote.price,
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

            refreshed_draft = self.repository.get_order_draft_by_id(db, existing_draft.id)
            if refreshed_draft is None:
                raise ValueError("Failed to load updated order draft")

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

        draft = self.repository.get_order_draft_by_id(db, created_draft.id)
        if draft is None:
            raise ValueError("Failed to load created order draft")

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
            raise ValueError("Order draft not found")

        if order_draft.user_id != user_id:
            raise ValueError("Order draft does not belong to the current user")

        return self._build_order_draft_response(order_draft)

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
            raise ValueError("Order draft not found")

        if order_draft.user_id != user_id:
            raise ValueError("Order draft does not belong to the current user")

        self.repository.delete_shipment_parties(db, order_draft_id=draft_id)
        self.repository.delete_shipment_packages(db, order_draft_id=draft_id)

        self._create_party(
            db,
            order_draft_id=draft_id,
            role="sender",
            payload=payload.sender,
        )
        self._create_party(
            db,
            order_draft_id=draft_id,
            role="recipient",
            payload=payload.recipient,
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

        self.repository.update_order_draft_status(
            db,
            order_draft=order_draft,
            status="shipment_details_completed",
        )

        db.commit()

        refreshed_draft = self.repository.get_order_draft_by_id(db, draft_id)
        if refreshed_draft is None:
            raise ValueError("Failed to load updated order draft")

        return self._build_order_draft_response(refreshed_draft)

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
        self,
        order_draft: OrderDraft,
    ) -> OrderDraftResponse:
        sender = self._find_party(order_draft.parties, "sender")
        recipient = self._find_party(order_draft.parties, "recipient")

        return OrderDraftResponse(
            draft_id=order_draft.id,
            user_id=order_draft.user_id,
            quote_session_id=order_draft.quote_session_id,
            selected_rate_quote_id=order_draft.selected_rate_quote_id,
            status=order_draft.status,
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
            sender=self._map_party(sender) if sender else None,
            recipient=self._map_party(recipient) if recipient else None,
            packages=[self._map_package(item) for item in order_draft.packages],
        )

    def _find_party(
        self,
        parties: list[ShipmentParty],
        role: str,
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