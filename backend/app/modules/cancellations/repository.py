from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.cancellations.models import CancellationRequest


class CancellationRequestsRepository:
    def create(
        self,
        db: Session,
        *,
        order_draft_id: int,
        requested_by_user_id: int,
        carrier_code: str,
        reason: str,
        api_attempted: bool = False,
        api_error: str | None = None,
        status: str = "pending",
    ) -> CancellationRequest:
        req = CancellationRequest(
            order_draft_id=order_draft_id,
            requested_by_user_id=requested_by_user_id,
            carrier_code=carrier_code,
            reason=reason,
            api_attempted=api_attempted,
            api_error=api_error,
            status=status,
        )
        db.add(req)
        db.flush()
        return req

    def get(self, db: Session, request_id: int) -> CancellationRequest | None:
        return db.get(CancellationRequest, request_id)

    def get_pending_for_order(
        self, db: Session, order_draft_id: int
    ) -> CancellationRequest | None:
        return db.scalar(
            select(CancellationRequest).where(
                CancellationRequest.order_draft_id == order_draft_id,
                CancellationRequest.status == "pending",
            )
        )

    def get_latest_for_order(
        self, db: Session, order_draft_id: int
    ) -> CancellationRequest | None:
        return db.scalar(
            select(CancellationRequest)
            .where(CancellationRequest.order_draft_id == order_draft_id)
            .order_by(CancellationRequest.created_at.desc())
            .limit(1)
        )

    def list_paginated(
        self,
        db: Session,
        *,
        offset: int,
        limit: int,
        status: str | None = None,
        carrier_code: str | None = None,
    ) -> tuple[Sequence[CancellationRequest], int]:
        base = select(CancellationRequest)
        if status:
            base = base.where(CancellationRequest.status == status)
        if carrier_code:
            base = base.where(CancellationRequest.carrier_code == carrier_code)

        total = (
            db.scalar(select(func.count()).select_from(base.subquery())) or 0
        )
        rows = db.scalars(
            base.order_by(CancellationRequest.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return rows, total

    def list_due_for_retry(
        self, db: Session, *, now: datetime, limit: int = 50
    ) -> Sequence[CancellationRequest]:
        """Заявки, у которых пришло время автоматической попытки API-отмены."""
        return db.scalars(
            select(CancellationRequest)
            .where(
                CancellationRequest.status == "pending",
                CancellationRequest.next_retry_at.is_not(None),
                CancellationRequest.next_retry_at <= now,
            )
            .order_by(CancellationRequest.next_retry_at)
            .limit(limit)
        ).all()

    def order_ids_with_pending(
        self, db: Session, order_ids: Sequence[int]
    ) -> set[int]:
        """One-shot lookup for list views: which order IDs currently have a
        pending cancellation request. Cheaper than N per-row queries."""
        if not order_ids:
            return set()
        rows = db.scalars(
            select(CancellationRequest.order_draft_id).where(
                CancellationRequest.order_draft_id.in_(order_ids),
                CancellationRequest.status == "pending",
            )
        ).all()
        return set(rows)
