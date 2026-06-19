from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
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
        occurred_at: "datetime | None" = None,
    ) -> TrackingEvent:
        from datetime import datetime
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
