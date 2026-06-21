from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TxProvider(StrEnum):
    MANUAL_BANK_TRANSFER = "manual_bank_transfer"
    KASPI = "kaspi"
    HALYK_EPAY = "halyk_epay"
    FREEDOMPAY = "freedompay"
    CLOUDPAYMENTS = "cloudpayments"
    OTHER = "other"


class TxMethod(StrEnum):
    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    QR = "qr"
    PAYMENT_LINK = "payment_link"


class TxStatus(StrEnum):
    UNPAID = "unpaid"
    AWAITING_PAYMENT = "awaiting_payment"
    PAYMENT_UNDER_REVIEW = "payment_under_review"
    PAID = "paid"
    PAYMENT_REJECTED = "payment_rejected"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ProofReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProviderWebhookStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("order_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[TxProvider] = mapped_column(
        SqlEnum(TxProvider, name="tx_provider_enum"),
        nullable=False,
    )
    method: Mapped[TxMethod] = mapped_column(
        SqlEnum(TxMethod, name="tx_method_enum"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KZT")
    status: Mapped[TxStatus] = mapped_column(
        SqlEnum(TxStatus, name="tx_status_enum"),
        nullable=False,
        default=TxStatus.AWAITING_PAYMENT,
        index=True,
    )
    external_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    payment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PaymentProof(Base):
    __tablename__ = "payment_proofs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payment_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("order_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    reviewed_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    review_status: Mapped[ProofReviewStatus] = mapped_column(
        SqlEnum(ProofReviewStatus, name="proof_review_status_enum"),
        nullable=False,
        default=ProofReviewStatus.PENDING,
        index=True,
    )
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class PaymentStatusHistory(Base):
    __tablename__ = "payment_status_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payment_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_status: Mapped[str] = mapped_column(String(50), nullable=False)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )


class ProviderWebhookEvent(Base):
    __tablename__ = "provider_webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "external_event_id", name="uq_provider_webhook_event"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[str] = mapped_column(Text, nullable=False)
    headers: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="received")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
