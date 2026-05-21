from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DocumentType(StrEnum):
    LABEL = "label"
    INVOICE = "invoice"
    RECEIPT = "receipt"
    ACT = "act"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("order_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        SqlEnum(DocumentType, name="document_type_enum"),
        nullable=False,
        index=True,
    )
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
