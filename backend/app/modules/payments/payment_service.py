from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.status_machine import can_transition, transition_order
from app.core.exceptions import NotFoundError, ValidationError
from app.core.streams import STREAM_DISPATCH
from app.core.streams import publish as stream_publish
from app.modules.commissions.service import CommissionsService
from app.modules.dispatch.models import OrderStatusHistory
from app.modules.dispatch.service import create_dispatch_job
from app.modules.notifications.service import NotificationsService
from app.modules.orders.models import OrderDraft
from app.modules.payments.providers.manual_bank_transfer import (
    ManualBankTransferProvider,
)
from app.modules.payments.transaction_models import (
    PaymentProof,
    PaymentStatusHistory,
    PaymentTransaction,
    ProofReviewStatus,
    TxMethod,
    TxProvider,
    TxStatus,
)
from app.modules.platform_settings.repository import PlatformSettingsRepository
from app.modules.shipments.service import ShipmentsService

logger = logging.getLogger(__name__)
_notifications_svc = NotificationsService()
_shipments_svc = ShipmentsService()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


_settings_repo = PlatformSettingsRepository()
_commissions_svc = CommissionsService()


def _get_manual_provider(db: Session) -> ManualBankTransferProvider:
    recipient_name = _settings_repo.get(db, "bank_recipient_name", default="")
    bank_name = _settings_repo.get(db, "bank_name", default="")
    iban = _settings_repo.get(db, "bank_iban", default="")
    if not recipient_name or not bank_name or not iban:
        raise ValidationError(
            "Банковские реквизиты не настроены. "
            "Администратор должен заполнить bank_recipient_name, bank_name и bank_iban в настройках платформы."
        )
    return ManualBankTransferProvider(
        recipient_name=recipient_name,
        bank_name=bank_name,
        iban=iban,
        bin_number=_settings_repo.get(db, "bank_bin", default=""),
        knp=_settings_repo.get(db, "bank_knp", default="710"),
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
            select(PaymentTransaction)
            .where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.status.in_([
                    TxStatus.AWAITING_PAYMENT,
                    TxStatus.PAYMENT_UNDER_REVIEW,
                    TxStatus.PAID,
                ]),
            )
            .with_for_update()
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
            amount=Decimal(str(order.price_snapshot)),
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

    def assert_payment_accepts_proof(
        self,
        db: Session,
        *,
        payment_id: int,
        order_id: int,
    ) -> PaymentTransaction:
        tx = db.get(PaymentTransaction, payment_id)
        if not tx or tx.order_id != order_id:
            raise NotFoundError("Payment transaction not found")
        if tx.status not in (TxStatus.AWAITING_PAYMENT, TxStatus.PAYMENT_REJECTED):
            raise ValidationError(
                f"Cannot upload proof for payment in status '{tx.status}'"
            )
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
            raise NotFoundError("Payment transaction not found")
        if tx.status not in (TxStatus.AWAITING_PAYMENT, TxStatus.PAYMENT_REJECTED):
            raise ValidationError(f"Cannot upload proof for payment in status '{tx.status}'")

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
        if order and order.status in ("awaiting_payment", "payment_rejected"):
            old_order_status = order.status
            transition_order(old_order_status, "payment_under_review")
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
            raise NotFoundError("Payment transaction not found")
        if tx.status != TxStatus.PAYMENT_UNDER_REVIEW:
            raise ValidationError(f"Cannot approve payment in status '{tx.status}'")

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
            proof.reviewed_at = _utcnow()

        old_tx_status = tx.status
        tx.status = TxStatus.PAID
        tx.paid_at = _utcnow()
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
        dispatch_job = None
        if order:
            old_order_status = order.status
            transition_order(old_order_status, "paid")
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
            _commissions_svc.record_commission(
                db,
                order_draft_id=order.id,
                carrier_code=order.carrier_code_snapshot,
                gross_amount=tx.amount,
                currency=tx.currency,
                # Reuse the markup captured at quote time so the customer sees
                # exactly what they were quoted, even if admin edits the rate
                # after quoting but before payment.
                precomputed_markup=order.markup_amount_snapshot,
                carrier_payout=order.carrier_price_snapshot,
            )
            # Create internal shipment record immediately so customer sees tracking number
            _shipments_svc.create_for_order(
                db,
                order_draft_id=order.id,
                carrier_code=order.carrier_code_snapshot,
            )
            dispatch_job = create_dispatch_job(db, order=order, changed_by_user_id=admin_id)
            _notifications_svc.notify_order_status(
                db, user_id=order.user_id, order_id=order.id, status="paid"
            )

        db.commit()
        db.refresh(tx)

        if order and dispatch_job:
            try:
                stream_publish(STREAM_DISPATCH, {
                    "dispatch_job_id": str(dispatch_job.id),
                    "order_id": str(order.id),
                })
            except Exception:
                logger.exception("Failed to publish dispatch event to stream (fallback polling will handle it)")

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
            raise NotFoundError("Payment transaction not found")
        if tx.status != TxStatus.PAYMENT_UNDER_REVIEW:
            raise ValidationError(f"Cannot reject payment in status '{tx.status}'")

        proof = db.scalar(
            select(PaymentProof).where(
                PaymentProof.payment_id == tx.id,
                PaymentProof.review_status == ProofReviewStatus.PENDING,
            ).order_by(PaymentProof.created_at.desc())
        )
        if proof:
            proof.review_status = ProofReviewStatus.REJECTED
            proof.reviewed_by_admin_id = admin_id
            proof.reviewed_at = _utcnow()
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
            transition_order(old_order_status, "payment_rejected")
            order.status = "payment_rejected"
            db.add(
                OrderStatusHistory(
                    order_id=order.id,
                    old_status=old_order_status,
                    new_status="payment_rejected",
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

    def get_bank_details(self, db: Session) -> dict:
        return _get_manual_provider(db).get_bank_details()

    def get_payment_for_order(
        self, db: Session, *, order_id: int
    ) -> PaymentTransaction | None:
        return db.scalar(
            select(PaymentTransaction)
            .where(PaymentTransaction.order_id == order_id)
            .order_by(PaymentTransaction.created_at.desc())
        )

    def system_confirm_payment(
        self,
        db: Session,
        *,
        payment_id: int,
        source: str = "system",
    ) -> PaymentTransaction:
        """Автоматическое подтверждение оплаты от платёжного провайдера (Kaspi и др.).
        Обходит шаг загрузки чека — для провайдеров, которые подтверждают оплату напрямую.
        """
        tx = db.get(PaymentTransaction, payment_id)
        if not tx:
            raise NotFoundError("Payment transaction not found")
        if tx.status not in (TxStatus.AWAITING_PAYMENT, TxStatus.PAYMENT_UNDER_REVIEW):
            raise ValidationError(
                f"Cannot auto-confirm payment in status '{tx.status}'"
            )

        old_tx_status = tx.status
        tx.status = TxStatus.PAID
        tx.paid_at = _utcnow()
        db.add(PaymentStatusHistory(
            payment_id=tx.id,
            old_status=old_tx_status,
            new_status=TxStatus.PAID,
            comment=f"Auto-confirmed by {source}",
        ))

        order = db.get(OrderDraft, tx.order_id)
        if order:
            old_order_status = order.status
            transition_order(old_order_status, "paid")
            order.status = "paid"
            db.add(OrderStatusHistory(
                order_id=order.id,
                old_status=old_order_status,
                new_status="paid",
                source=source,
                comment=f"Payment auto-confirmed by {source}",
            ))

        db.commit()
        db.refresh(tx)

        if order:
            _commissions_svc.record_commission(
                db,
                order_draft_id=order.id,
                carrier_code=order.carrier_code_snapshot,
                gross_amount=tx.amount,
                currency=tx.currency,
                # Reuse the markup captured at quote time so the customer sees
                # exactly what they were quoted, even if admin edits the rate
                # after quoting but before payment.
                precomputed_markup=order.markup_amount_snapshot,
                carrier_payout=order.carrier_price_snapshot,
            )
            _shipments_svc.create_for_order(
                db,
                order_draft_id=order.id,
                carrier_code=order.carrier_code_snapshot,
            )
            dispatch_job = create_dispatch_job(db, order=order)
            _notifications_svc.notify_order_status(
                db, user_id=order.user_id, order_id=order.id, status="paid"
            )
            db.commit()
            try:
                stream_publish(STREAM_DISPATCH, {
                    "dispatch_job_id": str(dispatch_job.id),
                    "order_id": str(order.id),
                })
            except Exception:
                logger.exception("Failed to publish dispatch event to stream (fallback polling will handle it)")

        return tx

    def admin_refund(
        self,
        db: Session,
        *,
        payment_id: int,
        admin_id: int,
        reason: str,
    ) -> PaymentTransaction:
        tx = db.get(PaymentTransaction, payment_id)
        if not tx:
            raise ValueError("Платёж не найден")
        if tx.status != TxStatus.PAID:
            raise ValueError(
                f"Возврат возможен только для оплаченных заказов. "
                f"Текущий статус: '{tx.status}'"
            )

        # For Kaspi: log that operator must process refund manually via Kaspi Business portal
        if tx.provider == TxProvider.KASPI:
            logger.warning(
                "Kaspi refund recorded in system but must be processed manually "
                "via Kaspi Business portal: payment_id=%s external_payment_id=%s amount=%s",
                tx.id,
                tx.external_payment_id,
                tx.amount,
            )

        old_tx_status = tx.status
        tx.status = TxStatus.REFUNDED
        db.add(
            PaymentStatusHistory(
                payment_id=tx.id,
                old_status=old_tx_status,
                new_status=TxStatus.REFUNDED,
                changed_by_user_id=admin_id,
                comment=f"Возврат оформлен администратором. Причина: {reason}",
            )
        )

        order = db.get(OrderDraft, tx.order_id)
        if order:
            _commissions_svc.void_for_order(db, order.id)

            old_order_status = order.status
            if not can_transition(old_order_status, "cancelled"):
                logger.warning(
                    "admin_refund: forcing order %s to cancelled from '%s' (state machine override)",
                    order.id,
                    old_order_status,
                )
            else:
                transition_order(old_order_status, "cancelled")
            order.status = "cancelled"
            db.add(
                OrderStatusHistory(
                    order_id=order.id,
                    old_status=old_order_status,
                    new_status="cancelled",
                    changed_by_user_id=admin_id,
                    source="admin",
                    comment=f"Заказ отменён в связи с возвратом средств. Причина: {reason}",
                )
            )
            _notifications_svc.notify_order_status(
                db,
                user_id=order.user_id,
                order_id=order.id,
                status="refunded",
            )

        db.commit()
        db.refresh(tx)
        return tx

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
