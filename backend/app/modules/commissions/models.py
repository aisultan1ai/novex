from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


# Statuses form a simple ledger:
#   active   — normal commission row from a paid order
#   reversed — original row that has been offset by a reversal
#   reversal — negative-amount offset row pointing at the original
class Commission(Base):
    __tablename__ = "commissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_draft_id: Mapped[int] = mapped_column(
        ForeignKey("order_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    carrier_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # gross_amount = what the customer paid (price_snapshot).
    # Negative on reversal rows.
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # carrier_payout = what the carrier is owed (gross_amount - commission_amount).
    # Nullable for rows written before migration 032 introduced this split.
    carrier_payout: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    commission_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    # commission_amount = Novex profit for this order (markup taken).
    # Negative on reversal rows.
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KZT")

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active", index=True
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    reverses_commission_id: Mapped[int | None] = mapped_column(
        ForeignKey("commissions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reversal_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
