from __future__ import annotations

import secrets
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base


class CarrierWebhookConfig(Base):
    """Carrier integration config — covers both webhook-push and metadata for any carrier."""

    __tablename__ = "carrier_webhooks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    carrier_code: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("carriers.code", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # Webhook push (Model B) — optional for API-only carriers
    push_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    # Integration mode flags
    # dispatch_mode: auto | api | webhook | manual
    dispatch_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")
    # tracking_mode: webhook | polling | manual
    tracking_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="webhook")

    # Health tracking
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
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


# ── Pydantic schemas ──────────────────────────────────────────────────────────


class CarrierWebhookCreate(BaseModel):
    carrier_code: str
    push_url: str | None = None
    webhook_secret: str | None = None
    is_active: bool = True
    retry_count: int = 3
    timeout_seconds: int = 10
    dispatch_mode: str = "auto"
    tracking_mode: str = "webhook"


class CarrierWebhookUpdate(BaseModel):
    push_url: str | None = None
    webhook_secret: str | None = None
    is_active: bool | None = None
    retry_count: int | None = None
    timeout_seconds: int | None = None
    dispatch_mode: str | None = None
    tracking_mode: str | None = None


class CarrierWebhookResponse(BaseModel):
    id: int
    carrier_code: str
    push_url: str | None
    is_active: bool
    retry_count: int
    timeout_seconds: int
    dispatch_mode: str
    tracking_mode: str
    last_success_at: datetime | None
    last_error: str | None
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

    def get_or_create(self, db: Session, carrier_code: str) -> CarrierWebhookConfig:
        cfg = self.get_by_carrier_code(db, carrier_code)
        if cfg is None:
            cfg = CarrierWebhookConfig(carrier_code=carrier_code)
            db.add(cfg)
            db.flush()
        return cfg

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
        cfg = self.get_or_create(db, carrier_code)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(cfg, field, value)
        db.flush()
        return cfg

    def regenerate_secret(self, db: Session, carrier_code: str) -> str:
        cfg = self.get_or_create(db, carrier_code)
        new_secret = "nvx_live_" + secrets.token_hex(24)
        cfg.webhook_secret = new_secret
        db.flush()
        return new_secret

    def delete(self, db: Session, carrier_code: str) -> None:
        cfg = self.get_by_carrier_code(db, carrier_code)
        if cfg is not None:
            db.delete(cfg)
            db.flush()
