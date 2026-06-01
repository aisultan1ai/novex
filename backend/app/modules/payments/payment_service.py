from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.status_machine import transition_order
from app.core.config import get_settings
from app.modules.dispatch.models import OrderStatusHistory
from app.modules.platform_settings.repository import PlatformSettingsRepository
from app.modules.dispatch.service import create_dispatch_job
from app.modules.notifications.service import NotificationsService
from app.modules.orders.models import OrderDraft
from app.modules.payments.providers.manual_bank_transfer import ManualBankTransferProvider
from app.modules.payments.transaction_models import (
    PaymentProof,
    PaymentStatusHistory,
    PaymentTransaction,
    ProofReviewStatus,
    TxMethod,
    TxProvider,
    TxStatus,
)

logger = logging.getLogger(__name__)
_notifications_svc = NotificationsService()


_settings_repo = PlatformSettingsRepository()


def _get_manual_provider(db: Session) -> ManualBankTransferProvider:
    s = get_settings()
    return ManualBankTransferProvider(
        recipient_name=_settings_repo.get(db, "bank_recipient_name", default=getattr(s, "bank_transfer_recipient_name", "ТОО Novex")),
        bank_name=_settings_repo.get(db, "bank_name", default=getattr(s, "bank_transfer_bank_name", "Halyk Bank")),
        iban=_settings_repo.get(db, "bank_iban", default=getattr(s, "bank_transfer_iban", "")),
        bin_number=_settings_repo.get(db, "bank_bin", default=getattr(s, "bank_transfer_bin", "")),
        knp=_settings_repo.get(db, "bank_knp", default=getattr(s, "bank_transfer_knp", "710")),
    )


class PaymentService:
    def initiate_bank_transfer(
        self,
        db: Session,
        *,
        order: OrderDraft,
        user_id: int,
    ) -> PaymentTransaction:
        existing = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.status.in_([
                    TxStatus.AWAITING_PAYMENT,
                    TxStatus.PAYMENT_UNDER_REVIEW,
                    TxStatus.PAID,
                ]),
            )
        )
        if existing:
            return existing

        provider = _get_manual_provider(db)
        result = provider.initiate_payment(
            order_id=order.id,
            amount=Decimal(str(order.price_snapshot)),
            currency=order.currency_snapshot,
            description=f"Доставка {order.from_city_snapshot} → {order.to_city_snapshot}",
        )

        tx = PaymentTransaction(
            order_id=order.id,
            provider=TxProvider.MANUAL_BANK_TRANSFER,
            method=TxMethod.BANK_TRANSFER,
            amount=float(order.price_snapshot),
            currency=order.currency_snapshot,
            status=TxStatus.AWAITING_PAYMENT,
            payment_reference=result.payment_reference,
        )
        db.add(tx)
        db.flush()

        db.add(
            PaymentStatusHistory(
                payment_id=tx.id,
                old_status="unpaid",
                new_status=TxStatus.AWAITING_PAYMENT,
                changed_by_user_id=user_id,
                comment="Bank transfer initiated",
            )
        )

        old_status = order.status
        transition_order(old_status, "awaiting_payment")
        order.status = "awaiting_payment"
        db.add(
            OrderStatusHistory(
                order_id=order.id,
                old_status=old_status,
                new_status="awaiting_payment",
                changed_by_user_id=user_id,
                source="customer",
                comment="Payment initiated by customer",
            )
        )

        db.commit()
        db.refresh(tx)
        return tx

    def submit_proof(
        self,
        db: Session,
        *,
        payment_id: int,
        order_id: int,
        user_id: int,
        file_url: str,
        file_name: str,
        file_mime_type: str,
        file_size: int,
        comment: str | None = None,
    ) -> PaymentProof:
        tx = db.get(PaymentTransaction, payment_id)
        if not tx or tx.order_id != order_id:
            raise ValueError("Payment transaction not found")
        if tx.status not in (TxStatus.AWAITING_PAYMENT, TxStatus.PAYMENT_REJECTED):
            raise ValueError(f"Cannot upload proof for payment in status '{tx.status}'")

        proof = PaymentProof(
            payment_id=tx.id,
            order_id=order_id,
            file_url=file_url,
            file_name=file_name,
            file_mime_type=file_mime_type,
            file_size=file_size,
            comment=comment,
            uploaded_by_user_id=user_id,
            review_status=ProofReviewStatus.PENDING,
        )
        db.add(proof)

        old_tx_status = tx.status
        tx.status = TxStatus.PAYMENT_UNDER_REVIEW
        db.add(
            PaymentStatusHistory(
                payment_id=tx.id,
                old_status=old_tx_status,
                new_status=TxStatus.PAYMENT_UNDER_REVIEW,
                changed_by_user_id=user_id,
                comment="Proof uploaded by customer",
            )
        )

        order = db.get(OrderDraft, order_id)
        if order and order.status == "awaiting_payment":
            old_order_status = order.status
            order.status = "payment_under_review"
            db.add(
                OrderStatusHistory(
                    order_id=order_id,
                    old_status=old_order_status,
                    new_status="payment_under_review",
                    changed_by_user_id=user_id,
                    source="customer",
                    comment="Payment proof submitted",
                )
            )

        if order:
            _notifications_svc.notify_order_status(
                db,
                user_id=user_id,
                order_id=order_id,
                status="payment_under_review",
            )

        db.commit()
        db.refresh(proof)
        return proof

    def admin_approve(
        self,
        db: Session,
        *,
        payment_id: int,
        admin_id: int,
    ) -> PaymentTransaction:
        tx = db.get(PaymentTransaction, payment_id)
        if not tx:
            raise ValueError("Payment transaction not found")
        if tx.status != TxStatus.PAYMENT_UNDER_REVIEW:
            raise ValueError(f"Cannot approve payment in status '{tx.status}'")

        # Approve the latest pending proof
        proof = db.scalar(
            select(PaymentProof).where(
                PaymentProof.payment_id == tx.id,
                PaymentProof.review_status == ProofReviewStatus.PENDING,
            ).order_by(PaymentProof.created_at.desc())
        )
        if proof:
            proof.review_status = ProofReviewStatus.APPROVED
            proof.reviewed_by_admin_id = admin_id
            proof.reviewed_at = datetime.utcnow()

        old_tx_status = tx.status
        tx.status = TxStatus.PAID
        tx.paid_at = datetime.utcnow()
        db.add(
            PaymentStatusHistory(
                payment_id=tx.id,
                old_status=old_tx_status,
                new_status=TxStatus.PAID,
                changed_by_user_id=admin_id,
                comment="Approved by admin",
            )
        )

        order = db.get(OrderDraft, tx.order_id)
        if order:
            old_order_status = order.status
            order.status = "paid"
            db.add(
                OrderStatusHistory(
                    order_id=order.id,
                    old_status=old_order_status,
                    new_status="paid",
                    changed_by_user_id=admin_id,
                    source="admin",
                    comment="Payment approved by admin",
                )
            )

        db.commit()  # persist "paid" status before dispatching
        db.refresh(tx)

        if order:
            create_dispatch_job(db, order=order, changed_by_user_id=admin_id)

            _notifications_svc.notify_order_status(
                db, user_id=order.user_id, order_id=order.id, status="paid"
            )

            db.commit()

        return tx

    def admin_reject(
        self,
        db: Session,
        *,
        payment_id: int,
        admin_id: int,
        reject_reason: str,
    ) -> PaymentTransaction:
        tx = db.get(PaymentTransaction, payment_id)
        if not tx:
            raise ValueError("Payment transaction not found")
        if tx.status != TxStatus.PAYMENT_UNDER_REVIEW:
            raise ValueError(f"Cannot reject payment in status '{tx.status}'")

        proof = db.scalar(
            select(PaymentProof).where(
                PaymentProof.payment_id == tx.id,
                PaymentProof.review_status == ProofReviewStatus.PENDING,
            ).order_by(PaymentProof.created_at.desc())
        )
        if proof:
            proof.review_status = ProofReviewStatus.REJECTED
            proof.reviewed_by_admin_id = admin_id
            proof.reviewed_at = datetime.utcnow()
            proof.reject_reason = reject_reason

        old_tx_status = tx.status
        tx.status = TxStatus.PAYMENT_REJECTED
        db.add(
            PaymentStatusHistory(
                payment_id=tx.id,
                old_status=old_tx_status,
                new_status=TxStatus.PAYMENT_REJECTED,
                changed_by_user_id=admin_id,
                comment=f"Rejected by admin: {reject_reason}",
            )
        )

        order = db.get(OrderDraft, tx.order_id)
        if order:
            old_order_status = order.status
            order.status = "awaiting_payment"
            db.add(
                OrderStatusHistory(
                    order_id=order.id,
                    old_status=old_order_status,
                    new_status="awaiting_payment",
                    changed_by_user_id=admin_id,
                    source="admin",
                    comment=f"Payment rejected: {reject_reason}",
                )
            )
            _notifications_svc.notify_order_status(
                db,
                user_id=order.user_id,
                order_id=order.id,
                status="payment_rejected",
                reject_reason=reject_reason,
            )

        db.commit()
        db.refresh(tx)
        return tx

    def get_payment_for_order(
        self, db: Session, *, order_id: int
    ) -> PaymentTransaction | None:
        return db.scalar(
            select(PaymentTransaction)
            .where(PaymentTransaction.order_id == order_id)
            .order_by(PaymentTransaction.created_at.desc())
        )

    def list_for_admin(
        self,
        db: Session,
        *,
        status: str | None = None,
        order_id: int | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[PaymentTransaction], int]:
        from sqlalchemy import func as sqlfunc
        q = select(PaymentTransaction).order_by(PaymentTransaction.created_at.desc())
        if status:
            q = q.where(PaymentTransaction.status == status)
        if order_id is not None:
            q = q.where(PaymentTransaction.order_id == order_id)
        total_q = select(sqlfunc.count()).select_from(q.subquery())
        total = db.scalar(total_q) or 0
        items = list(db.scalars(q.offset(offset).limit(limit)).all())
        return items, total
