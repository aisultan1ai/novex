from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base


class CarrierWebhookConfig(Base):
    __tablename__ = "carrier_webhooks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    carrier_code: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("carriers.code", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    push_url: Mapped[str] = mapped_column(Text, nullable=False)
    webhook_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ── Pydantic schemas ──────────────────────────────────────────────────────────


class CarrierWebhookCreate(BaseModel):
    carrier_code: str
    push_url: str
    webhook_secret: str | None = None
    retry_count: int = 3
    timeout_seconds: int = 10


class CarrierWebhookUpdate(BaseModel):
    push_url: str | None = None
    webhook_secret: str | None = None
    is_active: bool | None = None
    retry_count: int | None = None
    timeout_seconds: int | None = None


class CarrierWebhookResponse(BaseModel):
    id: int
    carrier_code: str
    push_url: str
    is_active: bool
    retry_count: int
    timeout_seconds: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Repository ────────────────────────────────────────────────────────────────


class CarrierWebhookRepository:
    def get_by_carrier_code(
        self, db: Session, carrier_code: str
    ) -> CarrierWebhookConfig | None:
        from sqlalchemy import select

        return db.scalar(
            select(CarrierWebhookConfig).where(
                CarrierWebhookConfig.carrier_code == carrier_code
            )
        )

    def list_all(self, db: Session) -> list[CarrierWebhookConfig]:
        from sqlalchemy import select

        return list(db.scalars(select(CarrierWebhookConfig)).all())

    def create(
        self, db: Session, payload: CarrierWebhookCreate
    ) -> CarrierWebhookConfig:
        cfg = CarrierWebhookConfig(**payload.model_dump())
        db.add(cfg)
        db.flush()
        return cfg

    def update(
        self, db: Session, carrier_code: str, payload: CarrierWebhookUpdate
    ) -> CarrierWebhookConfig:
        cfg = self.get_by_carrier_code(db, carrier_code)
        if cfg is None:
            raise ValueError(f"CarrierWebhookConfig not found: {carrier_code}")
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(cfg, field, value)
        db.flush()
        return cfg

    def delete(self, db: Session, carrier_code: str) -> None:
        cfg = self.get_by_carrier_code(db, carrier_code)
        if cfg is not None:
            db.delete(cfg)
            db.flush()
