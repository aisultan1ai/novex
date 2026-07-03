from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Commission(Base):
    __tablename__ = "commissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_draft_id: Mapped[int] = mapped_column(
        ForeignKey("order_drafts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    carrier_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # gross_amount = what the customer paid (price_snapshot).
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # carrier_payout = what the carrier is owed (gross_amount - commission_amount).
    # Nullable for rows written before migration 032 introduced this split.
    carrier_payout: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    commission_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    # commission_amount = Novex profit for this order (markup taken).
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KZT")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
