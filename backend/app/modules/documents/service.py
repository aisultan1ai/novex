from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.storage import get_storage
from app.modules.documents.label_generator import generate_label_pdf
from app.modules.documents.models import Document, DocumentType
from app.modules.orders.repository import OrdersRepository

logger = logging.getLogger(__name__)


class DocumentsService:
    def __init__(self, orders_repo: OrdersRepository | None = None) -> None:
        self.orders_repo = orders_repo or OrdersRepository()

    def get_label_pdf(
        self,
        db: Session,
        *,
        user_id: int,
        order_draft_id: int,
    ) -> tuple[bytes, str]:
        order = self.orders_repo.get_order_draft_by_id(db, order_draft_id)
        if order is None:
            raise NotFoundError("Заказ не найден")
        if order.user_id != user_id:
            raise ForbiddenError("Нет доступа к этому заказу")

        filename = f"novex_label_{order_draft_id}.pdf"

        # Return cached version if already generated
        existing = db.scalar(
            select(Document).where(
                Document.order_id == order_draft_id,
                Document.document_type == DocumentType.LABEL,
            )
        )
        if existing:
            storage = get_storage()
            # file_url stores the internal object_name for retrieval
            cached_bytes = storage.get_file_bytes(existing.file_url)
            if cached_bytes:
                logger.info("Label served from storage cache: order_id=%s", order_draft_id)
                return cached_bytes, existing.file_name

        # Generate new PDF
        pdf_bytes = generate_label_pdf(order)

        # Upload to storage and persist metadata
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
                file_url=uploaded.object_name,  # Store path, not presigned URL
                file_name=filename,
                mime_type="application/pdf",
                created_by_user_id=user_id,
            )
            db.add(doc)
            db.commit()
            logger.info("Label generated and saved: order_id=%s", order_draft_id)
        except Exception as exc:
            logger.warning("Label storage/save failed, returning in-memory: %s", exc)

        return pdf_bytes, filename
