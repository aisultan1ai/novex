from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


# Lifecycle:
#   pending        — customer asked to cancel, awaiting carrier or admin
#   approved       — carrier or admin confirmed manually → order cancelled
#   api_cancelled  — carrier API accepted our cancel call → order cancelled
#   rejected       — carrier or admin refused → order stays alive
#
# Finalized states (approved / api_cancelled / rejected) are terminal.
# Only one 'pending' row per order is allowed (enforced by partial unique
# index defined in migration 044).
class CancellationRequest(Base):
    __tablename__ = "cancellation_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_draft_id: Mapped[int] = mapped_column(
        ForeignKey("order_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    # Snapshot — a carrier could theoretically be renamed while a request
    # is pending; we keep the code we saw at creation time so audit /
    # per-carrier filtering stays stable.
    carrier_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    # True when the create path tried the carrier API before falling back
    # to a manual request. Retries by admin flip this to True too.
    api_attempted: Mapped[bool] = mapped_column(
        default=False, server_default="false", nullable=False
    )
    api_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Free-form comment from the resolver (carrier or admin).
    carrier_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    resolved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    # Auto-retry для CSE/Exline (в основном Exline «ожидает синхронизации»).
    # next_retry_at=NULL означает «ретрай не запланирован». retry_count
    # инкрементируется на каждой попытке; после MAX_RETRIES worker перестаёт
    # трогать заявку — фолбэк на ручное действие админа.
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
