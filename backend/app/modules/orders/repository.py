from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.modules.orders.models import OrderDraft, ShipmentPackage, ShipmentParty
from app.modules.quotes.models import QuoteSession, RateQuote


class OrdersRepository:
    def get_quote_session_by_id(
        self,
        db: Session,
        quote_session_id: int,
    ) -> QuoteSession | None:
        stmt = (
            select(QuoteSession)
            .options(selectinload(QuoteSession.rate_quotes))
            .where(QuoteSession.id == quote_session_id)
        )
        return db.scalar(stmt)

    def get_selected_rate_quote_for_session(
        self,
        db: Session,
        quote_session_id: int,
    ) -> RateQuote | None:
        stmt = (
            select(RateQuote)
            .where(
                RateQuote.quote_session_id == quote_session_id,
                RateQuote.is_selected.is_(True),
            )
            .limit(1)
        )
        return db.scalar(stmt)

    def get_order_draft_by_id(
        self,
        db: Session,
        draft_id: int,
    ) -> OrderDraft | None:
        stmt = (
            select(OrderDraft)
            .options(
                selectinload(OrderDraft.parties),
                selectinload(OrderDraft.packages),
            )
            .where(OrderDraft.id == draft_id)
        )
        return db.scalar(stmt)

    def get_order_draft_by_user_and_quote_session(
        self,
        db: Session,
        *,
        user_id: int,
        quote_session_id: int,
    ) -> OrderDraft | None:
        stmt = (
            select(OrderDraft)
            .options(
                selectinload(OrderDraft.parties),
                selectinload(OrderDraft.packages),
            )
            .where(
                OrderDraft.user_id == user_id,
                OrderDraft.quote_session_id == quote_session_id,
            )
        )
        return db.scalar(stmt)

    def create_order_draft(
        self,
        db: Session,
        *,
        user_id: int,
        quote_session_id: int,
        selected_rate_quote_id: int,
        carrier_code_snapshot: str,
        carrier_name_snapshot: str,
        tariff_name_snapshot: str,
        price_snapshot: Decimal,
        currency_snapshot: str,
        eta_days_min_snapshot: int,
        eta_days_max_snapshot: int,
        status: str = "draft",
    ) -> OrderDraft:
        order_draft = OrderDraft(
            user_id=user_id,
            quote_session_id=quote_session_id,
            selected_rate_quote_id=selected_rate_quote_id,
            status=status,
            carrier_code_snapshot=carrier_code_snapshot,
            carrier_name_snapshot=carrier_name_snapshot,
            tariff_name_snapshot=tariff_name_snapshot,
            price_snapshot=price_snapshot,
            currency_snapshot=currency_snapshot,
            eta_days_min_snapshot=eta_days_min_snapshot,
            eta_days_max_snapshot=eta_days_max_snapshot,
        )
        db.add(order_draft)
        db.flush()
        return order_draft

    def update_order_draft_snapshot(
        self,
        db: Session,
        *,
        order_draft: OrderDraft,
        selected_rate_quote_id: int,
        carrier_code_snapshot: str,
        carrier_name_snapshot: str,
        tariff_name_snapshot: str,
        price_snapshot: Decimal,
        currency_snapshot: str,
        eta_days_min_snapshot: int,
        eta_days_max_snapshot: int,
    ) -> OrderDraft:
        order_draft.selected_rate_quote_id = selected_rate_quote_id
        order_draft.carrier_code_snapshot = carrier_code_snapshot
        order_draft.carrier_name_snapshot = carrier_name_snapshot
        order_draft.tariff_name_snapshot = tariff_name_snapshot
        order_draft.price_snapshot = price_snapshot
        order_draft.currency_snapshot = currency_snapshot
        order_draft.eta_days_min_snapshot = eta_days_min_snapshot
        order_draft.eta_days_max_snapshot = eta_days_max_snapshot
        db.add(order_draft)
        db.flush()
        return order_draft

    def update_order_draft_status(
        self,
        db: Session,
        *,
        order_draft: OrderDraft,
        status: str,
    ) -> OrderDraft:
        order_draft.status = status
        db.add(order_draft)
        db.flush()
        return order_draft

    def delete_shipment_parties(
        self,
        db: Session,
        *,
        order_draft_id: int,
    ) -> None:
        stmt = delete(ShipmentParty).where(ShipmentParty.order_draft_id == order_draft_id)
        db.execute(stmt)

    def delete_shipment_packages(
        self,
        db: Session,
        *,
        order_draft_id: int,
    ) -> None:
        stmt = delete(ShipmentPackage).where(ShipmentPackage.order_draft_id == order_draft_id)
        db.execute(stmt)

    def create_shipment_party(
        self,
        db: Session,
        *,
        order_draft_id: int,
        role: str,
        full_name: str,
        phone: str,
        email: str | None,
        company_name: str | None,
        country: str,
        city: str,
        address_line1: str,
        address_line2: str | None,
        postal_code: str | None,
        comment: str | None,
    ) -> ShipmentParty:
        party = ShipmentParty(
            order_draft_id=order_draft_id,
            role=role,
            full_name=full_name,
            phone=phone,
            email=email,
            company_name=company_name,
            country=country,
            city=city,
            address_line1=address_line1,
            address_line2=address_line2,
            postal_code=postal_code,
            comment=comment,
        )
        db.add(party)
        db.flush()
        return party

    def create_shipment_package(
        self,
        db: Session,
        *,
        order_draft_id: int,
        description: str,
        quantity: int,
        weight_kg: Decimal,
        width_cm: Decimal,
        height_cm: Decimal,
        depth_cm: Decimal,
        declared_value: Decimal | None,
        declared_value_currency: str | None,
    ) -> ShipmentPackage:
        shipment_package = ShipmentPackage(
            order_draft_id=order_draft_id,
            description=description,
            quantity=quantity,
            weight_kg=weight_kg,
            width_cm=width_cm,
            height_cm=height_cm,
            depth_cm=depth_cm,
            declared_value=declared_value,
            declared_value_currency=declared_value_currency,
        )
        db.add(shipment_package)
        db.flush()
        return shipment_package

    def list_shipment_parties(
        self,
        db: Session,
        *,
        order_draft_id: int,
    ) -> Sequence[ShipmentParty]:
        stmt = (
            select(ShipmentParty)
            .where(ShipmentParty.order_draft_id == order_draft_id)
            .order_by(ShipmentParty.id.asc())
        )
        return db.scalars(stmt).all()

    def list_shipment_packages(
        self,
        db: Session,
        *,
        order_draft_id: int,
    ) -> Sequence[ShipmentPackage]:
        stmt = (
            select(ShipmentPackage)
            .where(ShipmentPackage.order_draft_id == order_draft_id)
            .order_by(ShipmentPackage.id.asc())
        )
        return db.scalars(stmt).all()