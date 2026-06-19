from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base
from app.core.encryption import EncryptedText


class CarrierAPICredentials(Base):
    __tablename__ = "carrier_api_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    carrier_code: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("carriers.code", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    api_url: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    api_token: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    extra_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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


class CarrierAPICredentialsCreate(BaseModel):
    carrier_code: str
    api_url: str
    api_token: str
    is_active: bool = True
    extra_config: dict[str, Any] | None = None


class CarrierAPICredentialsUpdate(BaseModel):
    api_url: str | None = None
    api_token: str | None = None
    is_active: bool | None = None
    extra_config: dict[str, Any] | None = None


class CarrierAPICredentialsResponse(BaseModel):
    id: int
    carrier_code: str
    api_url: str
    api_token_masked: str
    is_active: bool
    extra_config: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_masked(cls, obj: CarrierAPICredentials) -> "CarrierAPICredentialsResponse":
        token = obj.api_token or ""
        masked = token[:6] + "•" * max(0, len(token) - 10) + token[-4:] if len(token) > 10 else "••••"
        return cls(
            id=obj.id,
            carrier_code=obj.carrier_code,
            api_url=obj.api_url,
            api_token_masked=masked,
            is_active=obj.is_active,
            extra_config=obj.extra_config,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


# ── Repository ────────────────────────────────────────────────────────────────


class CarrierAPICredentialsRepository:
    def get_by_carrier_code(
        self, db: Session, carrier_code: str
    ) -> CarrierAPICredentials | None:
        from sqlalchemy import select
        return db.scalar(
            select(CarrierAPICredentials).where(
                CarrierAPICredentials.carrier_code == carrier_code
            )
        )

    def list_all(self, db: Session) -> list[CarrierAPICredentials]:
        from sqlalchemy import select
        return list(db.scalars(select(CarrierAPICredentials)).all())

    def upsert(
        self, db: Session, payload: CarrierAPICredentialsCreate
    ) -> CarrierAPICredentials:
        existing = self.get_by_carrier_code(db, payload.carrier_code)
        if existing:
            existing.api_url = payload.api_url
            existing.api_token = payload.api_token
            existing.is_active = payload.is_active
            if payload.extra_config is not None:
                existing.extra_config = payload.extra_config
            db.flush()
            return existing
        creds = CarrierAPICredentials(**payload.model_dump())
        db.add(creds)
        db.flush()
        return creds

    def update(
        self, db: Session, carrier_code: str, payload: CarrierAPICredentialsUpdate
    ) -> CarrierAPICredentials:
        creds = self.get_by_carrier_code(db, carrier_code)
        if creds is None:
            raise ValueError(f"CarrierAPICredentials not found: {carrier_code}")
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(creds, field, value)
        db.flush()
        return creds

    def delete(self, db: Session, carrier_code: str) -> None:
        creds = self.get_by_carrier_code(db, carrier_code)
        if creds is not None:
            db.delete(creds)
            db.flush()
