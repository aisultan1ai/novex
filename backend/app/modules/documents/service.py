from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.redis import get_redis
from app.core.storage import get_storage
from app.modules.documents.label_generator import generate_label_pdf
from app.modules.documents.models import Document, DocumentType
from app.modules.orders.repository import OrdersRepository

logger = logging.getLogger(__name__)

_LABEL_CACHE_TTL = 60 * 60 * 24  # 24h — matches typical presigned URL validity window


class DocumentsService:
    def __init__(self, orders_repo: OrdersRepository | None = None) -> None:
        self.orders_repo = orders_repo or OrdersRepository()

    def get_label(
        self,
        db: Session,
        *,
        user_id: int,
        order_draft_id: int,
    ) -> tuple[str, str]:
        """Returns (object_name, filename). Auth is checked before any storage access."""
        order = self.orders_repo.get_order_draft_by_id(db, order_draft_id)
        if order is None:
            raise NotFoundError("Заказ не найден")
        if order.user_id != user_id:
            raise ForbiddenError("Нет доступа к этому заказу")

        filename = f"novex_label_{order_draft_id}.pdf"
        cache_key = f"pdf:label:{order_draft_id}"

        r = get_redis()
        cached_object_name = r.get(cache_key)
        if cached_object_name:
            logger.info("Label served from Redis cache: order_id=%s", order_draft_id)
            return cached_object_name, filename

        existing = db.scalar(
            select(Document).where(
                Document.order_id == order_draft_id,
                Document.document_type == DocumentType.LABEL,
            )
        )
        if existing:
            r.set(cache_key, existing.file_url, ex=_LABEL_CACHE_TTL)
            logger.info("Label served from DB/storage cache: order_id=%s", order_draft_id)
            return existing.file_url, existing.file_name

        pdf_bytes = generate_label_pdf(order)

        storage = get_storage()
        try:
            uploaded = storage.upload_file(
                file_data=pdf_bytes,
                original_name=filename,
                mime_type="application/pdf",
                folder=f"labels/{order_draft_id}",
            )
            doc = Document(
                order_id=order_draft_id,
                document_type=DocumentType.LABEL,
                file_url=uploaded.object_name,
                file_name=filename,
                mime_type="application/pdf",
                created_by_user_id=user_id,
            )
            db.add(doc)
            db.commit()
            r.set(cache_key, uploaded.object_name, ex=_LABEL_CACHE_TTL)
            logger.info("Label generated and saved: order_id=%s", order_draft_id)
            return uploaded.object_name, filename
        except Exception as exc:
            logger.warning("Label storage/save failed: %s", exc)
            raise
