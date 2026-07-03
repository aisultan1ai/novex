from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_draft_id: Mapped[int] = mapped_column(
        ForeignKey("order_drafts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    tracking_number: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    # Carrier's own order identifier — the value we submit to statusreq / Tracking
    # to query carrier status. For Exline this is the client-side orderno
    # (NOVEX-000042); for CSE the SaveWaybillOffice order number.
    carrier_tracking_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    # Physical barcode / awb printed on the package. Distinct from
    # carrier_tracking_number for carriers that separate internal orderno from
    # scannable code (Exline: KAZ000088138). None if the carrier does not issue one.
    # Indexed to support admin search by scanning a package.
    carrier_barcode: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_polled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        index=True,
    )
