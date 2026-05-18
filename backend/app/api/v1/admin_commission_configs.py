from __future__ import annotations

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import require_admin
from app.modules.carriers.models import CarrierCommissionConfig

router = APIRouter(
    prefix="/admin/commission-configs", tags=["admin:commission-configs"]
)

CommissionType = Literal["percentage", "fixed", "combined"]


class CommissionConfigUpsert(BaseModel):
    commission_type: CommissionType = "percentage"
    commission_rate: Decimal | None = Field(default=None, ge=0, le=1)
    fixed_amount: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="KZT", min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_fields(self) -> CommissionConfigUpsert:
        if (
            self.commission_type in ("percentage", "combined")
            and self.commission_rate is None
        ):
            raise ValueError(
                "commission_rate обязателен для типов 'percentage' и 'combined'"
            )
        if self.commission_type in ("fixed", "combined") and self.fixed_amount is None:
            raise ValueError("fixed_amount обязателен для типов 'fixed' и 'combined'")
        return self


class CommissionConfigResponse(BaseModel):
    id: int
    carrier_code: str
    commission_type: str
    commission_rate: Decimal | None
    fixed_amount: Decimal | None
    currency: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[CommissionConfigResponse])
def list_configs(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> list[CommissionConfigResponse]:
    rows = db.scalars(select(CarrierCommissionConfig)).all()
    return [CommissionConfigResponse.model_validate(r) for r in rows]


@router.get("/{carrier_code}", response_model=CommissionConfigResponse)
def get_config(
    carrier_code: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> CommissionConfigResponse:
    row = db.scalar(
        select(CarrierCommissionConfig).where(
            CarrierCommissionConfig.carrier_code == carrier_code
        )
    )
    if row is None:
        raise HTTPException(404, "Конфигурация комиссии не найдена")
    return CommissionConfigResponse.model_validate(row)


@router.put("/{carrier_code}", response_model=CommissionConfigResponse)
def upsert_config(
    carrier_code: str,
    payload: CommissionConfigUpsert,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> CommissionConfigResponse:
    row = db.scalar(
        select(CarrierCommissionConfig).where(
            CarrierCommissionConfig.carrier_code == carrier_code
        )
    )
    if row is None:
        row = CarrierCommissionConfig(carrier_code=carrier_code)
        db.add(row)

    row.commission_type = payload.commission_type
    row.commission_rate = payload.commission_rate
    row.fixed_amount = payload.fixed_amount
    row.currency = payload.currency.upper()
    db.commit()
    db.refresh(row)
    return CommissionConfigResponse.model_validate(row)


@router.delete("/{carrier_code}", status_code=204)
def delete_config(
    carrier_code: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> None:
    row = db.scalar(
        select(CarrierCommissionConfig).where(
            CarrierCommissionConfig.carrier_code == carrier_code
        )
    )
    if row is None:
        raise HTTPException(404, "Конфигурация комиссии не найдена")
    db.delete(row)
    db.commit()
