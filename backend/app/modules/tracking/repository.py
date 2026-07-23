from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.modules.tracking.models import TrackingEvent


class TrackingRepository:
    def add_event(
        self,
        db: Session,
        *,
        order_draft_id: int,
        status: str,
        description: str | None = None,
        location: str | None = None,
        carrier_status: str | None = None,
        occurred_at: datetime | None = None,
    ) -> TrackingEvent:
        event = TrackingEvent(
            order_draft_id=order_draft_id,
            status=status,
            description=description,
            location=location,
            carrier_status=carrier_status,
            **({"occurred_at": occurred_at} if occurred_at is not None else {}),
        )
        db.add(event)
        db.flush()
        return event

    def existing_keys(
        self,
        db: Session,
        *,
        order_draft_id: int,
        keys: list[tuple[str | None, datetime]],
    ) -> set[tuple[str | None, datetime]]:
        """Return the subset of (carrier_status, occurred_at) pairs that are
        already stored for this order. One SELECT for the whole batch."""
        if not keys:
            return set()
        rows = db.execute(
            select(TrackingEvent.carrier_status, TrackingEvent.occurred_at)
            .where(
                TrackingEvent.order_draft_id == order_draft_id,
                tuple_(TrackingEvent.carrier_status, TrackingEvent.occurred_at).in_(keys),
            )
        ).all()
        return {(r[0], r[1]) for r in rows}

    def bulk_insert_events(
        self,
        db: Session,
        *,
        rows: list[dict],
    ) -> None:
        """Insert many events in one round-trip. Uses ON CONFLICT DO NOTHING
        against the (order_draft_id, carrier_status, occurred_at) unique
        constraint so concurrent pollers cannot cause races.
        """
        if not rows:
            return
        db.execute(
            pg_insert(TrackingEvent)
            .values(rows)
            .on_conflict_do_nothing(
                constraint="uq_tracking_events_order_carrier_status_occurred_at",
            )
        )
        db.flush()

    def list_events(
        self,
        db: Session,
        *,
        order_draft_id: int,
    ) -> Sequence[TrackingEvent]:
        return db.scalars(
            select(TrackingEvent)
            .where(TrackingEvent.order_draft_id == order_draft_id)
            .order_by(TrackingEvent.occurred_at.asc())
        ).all()
