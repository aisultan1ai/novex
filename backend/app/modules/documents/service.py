from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.modules.documents.label_generator import generate_label_pdf
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

        pdf_bytes = generate_label_pdf(order)
        filename = f"novex_label_{order_draft_id}.pdf"
        logger.info("Label generated: order_id=%s", order_draft_id)
        return pdf_bytes, filename
