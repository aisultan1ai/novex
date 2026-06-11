from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base


class CarrierIntegrationLog(Base):
    __tablename__ = "carrier_integration_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    carrier_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="outbound (Novex→Carrier) or inbound (Carrier→Novex)",
    )
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="dispatch | tracking_webhook | test_connection | test_webhook",
    )
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="success",
        comment="success | error",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False, index=True
    )


class IntegrationLogRepository:
    def create(
        self,
        db: Session,
        *,
        carrier_code: str,
        direction: str,
        event_type: str,
        order_id: int | None = None,
        payload: str | None = None,
        response: str | None = None,
        http_status: int | None = None,
        duration_ms: int | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> CarrierIntegrationLog:
        log = CarrierIntegrationLog(
            carrier_code=carrier_code,
            direction=direction,
            event_type=event_type,
            order_id=order_id,
            payload=payload,
            response=response,
            http_status=http_status,
            duration_ms=duration_ms,
            status=status,
            error_message=error_message,
        )
        db.add(log)
        db.flush()
        return log

    def list_recent(
        self,
        db: Session,
        carrier_code: str,
        limit: int = 50,
    ) -> list[CarrierIntegrationLog]:
        from sqlalchemy import select
        return list(
            db.scalars(
                select(CarrierIntegrationLog)
                .where(CarrierIntegrationLog.carrier_code == carrier_code)
                .order_by(CarrierIntegrationLog.created_at.desc())
                .limit(limit)
            ).all()
        )
