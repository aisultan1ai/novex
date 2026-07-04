from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.redis import get_redis
from app.modules.documents.models import Document, DocumentType
from app.modules.orders.repository import OrdersRepository
from app.modules.shipments.repository import ShipmentsRepository

logger = logging.getLogger(__name__)

_LABEL_CACHE_TTL = 60 * 60 * 24  # 24h — matches typical presigned URL validity window


class LabelNotReadyError(NotFoundError):
    """Raised when a customer requests a waybill that the carrier hasn't returned yet."""


class DocumentsService:
    def __init__(self, orders_repo: OrdersRepository | None = None) -> None:
        self.orders_repo = orders_repo or OrdersRepository()
        self._shipments_repo = ShipmentsRepository()

    def get_label(
        self,
        db: Session,
        *,
        user_id: int,
        order_draft_id: int,
    ) -> tuple[str, str]:
        """Returns (object_name, filename). Auth is checked before any storage access.

        Only serves waybills produced by the carrier (uploaded by dispatch worker
        or admin `refresh-waybill`). We never generate a Novex-branded fallback
        PDF — if the carrier hasn't returned a waybill yet, we tell the customer
        to wait rather than issue a placeholder document.
        """
        order = self.orders_repo.get_order_draft_by_id(db, order_draft_id)
        if order is None:
            raise NotFoundError("Заказ не найден")
        if order.user_id != user_id:
            raise ForbiddenError("Нет доступа к этому заказу")

        cache_key = f"pdf:label:{order_draft_id}"

        r = get_redis()
        cached_object_name = r.get(cache_key)  # type: ignore[union-attr]
        if cached_object_name:
            logger.info("Label served from Redis cache: order_id=%s", order_draft_id)
            existing = db.scalar(
                select(Document)
                .where(
                    Document.order_id == order_draft_id,
                    Document.document_type == DocumentType.LABEL,
                )
                .order_by(Document.id.desc())
            )
            filename = existing.file_name if existing else f"waybill_{order_draft_id}.pdf"
            return cached_object_name, filename  # type: ignore[return-value]

        existing = db.scalar(
            select(Document)
            .where(
                Document.order_id == order_draft_id,
                Document.document_type == DocumentType.LABEL,
            )
            .order_by(Document.id.desc())
        )
        if existing:
            r.set(cache_key, existing.file_url, ex=_LABEL_CACHE_TTL)
            logger.info("Label served from DB/storage cache: order_id=%s", order_draft_id)
            return existing.file_url, existing.file_name

        # No carrier waybill yet — do NOT generate a Novex fallback. Tell the
        # customer the waybill is being prepared by the carrier.
        logger.info(
            "Label not yet available from carrier: order_id=%s", order_draft_id
        )
        raise LabelNotReadyError(
            "Накладная ещё формируется у перевозчика. "
            "Попробуйте немного позже — обычно она становится доступна в течение 5-10 минут после отправки."
        )
