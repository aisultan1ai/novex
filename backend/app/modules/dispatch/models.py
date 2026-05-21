from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DispatchJobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DispatchJob(Base):
    __tablename__ = "dispatch_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("order_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    carrier_code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[DispatchJobStatus] = mapped_column(
        SqlEnum(DispatchJobStatus, name="dispatch_job_status_enum"),
        nullable=False,
        default=DispatchJobStatus.QUEUED,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True, index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("order_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_status: Mapped[str] = mapped_column(String(50), nullable=False)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="system_worker")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
