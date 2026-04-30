from __future__ import annotations

import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, update as sa_update
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.dependencies import require_admin
from app.modules.carriers.models import Carrier, CarrierService, CarrierTariffRate, CarrierZoneCity

router = APIRouter(prefix="/admin/carriers", tags=["admin:carriers"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CarrierCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    is_active: bool = True


class CarrierUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ServiceCreate(BaseModel):
    code: str
    name: str
    shipment_type: Optional[str] = None
    is_active: bool = True


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class RateRow(BaseModel):
    zone: int
    weight_from_kg: float
    weight_to_kg: Optional[float] = None
    base_price: float
    per_unit_price: Optional[float] = None
    per_unit_weight_kg: Optional[float] = None
    currency: str = "KZT"
    eta_days_min: Optional[int] = None
    eta_days_max: Optional[int] = None


class ZoneCityCreate(BaseModel):
    city_name: str
    zone: int
    city_type: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _carrier_dict(c: Carrier) -> dict:
    return {
        "id": c.id, "code": c.code, "name": c.name,
        "description": c.description, "is_active": c.is_active,
    }


def _service_dict(s: CarrierService) -> dict:
    return {
        "id": s.id, "code": s.code, "name": s.name,
        "shipment_type": s.shipment_type, "is_active": s.is_active,
    }


def _rate_dict(r: CarrierTariffRate) -> dict:
    return {
        "id": r.id, "zone": r.zone,
        "weight_from_kg": float(r.weight_from_kg),
        "weight_to_kg": float(r.weight_to_kg) if r.weight_to_kg is not None else None,
        "base_price": float(r.base_price),
        "per_unit_price": float(r.per_unit_price) if r.per_unit_price is not None else None,
        "per_unit_weight_kg": float(r.per_unit_weight_kg) if r.per_unit_weight_kg is not None else None,
        "currency": r.currency,
        "eta_days_min": r.eta_days_min,
        "eta_days_max": r.eta_days_max,
        "is_active": r.is_active,
    }


# ── Carriers CRUD ─────────────────────────────────────────────────────────────

@router.get("")
def list_carriers(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> list[dict]:
    carriers = db.scalars(select(Carrier).order_by(Carrier.name)).all()
    return [_carrier_dict(c) for c in carriers]


@router.post("", status_code=201)
def create_carrier(
    payload: CarrierCreate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    if db.scalar(select(Carrier).where(Carrier.code == payload.code)):
        raise HTTPException(409, f"Перевозчик с кодом '{payload.code}' уже существует")
    carrier = Carrier(**payload.model_dump())
    db.add(carrier)
    db.commit()
    db.refresh(carrier)
    return _carrier_dict(carrier)


@router.get("/{carrier_id}")
def get_carrier(
    carrier_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    carrier = db.scalar(
        select(Carrier)
        .options(selectinload(Carrier.services).selectinload(CarrierService.tariff_rates))
        .where(Carrier.id == carrier_id)
    )
    if not carrier:
        raise HTTPException(404, "Перевозчик не найден")
    result = _carrier_dict(carrier)
    result["services"] = [_service_dict(s) for s in carrier.services]
    return result


@router.patch("/{carrier_id}")
def update_carrier(
    carrier_id: int,
    payload: CarrierUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    carrier = db.get(Carrier, carrier_id)
    if not carrier:
        raise HTTPException(404, "Перевозчик не найден")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(carrier, k, v)
    db.commit()
    db.refresh(carrier)
    return _carrier_dict(carrier)


# ── Services ──────────────────────────────────────────────────────────────────

@router.get("/{carrier_id}/services")
def list_services(
    carrier_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> list[dict]:
    if not db.get(Carrier, carrier_id):
        raise HTTPException(404, "Перевозчик не найден")
    services = db.scalars(
        select(CarrierService)
        .where(CarrierService.carrier_id == carrier_id)
        .order_by(CarrierService.code)
    ).all()
    return [_service_dict(s) for s in services]


@router.post("/{carrier_id}/services", status_code=201)
def create_service(
    carrier_id: int,
    payload: ServiceCreate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    if not db.get(Carrier, carrier_id):
        raise HTTPException(404, "Перевозчик не найден")
    service = CarrierService(carrier_id=carrier_id, **payload.model_dump())
    db.add(service)
    db.commit()
    db.refresh(service)
    return _service_dict(service)


@router.patch("/{carrier_id}/services/{service_id}")
def update_service(
    carrier_id: int,
    service_id: int,
    payload: ServiceUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    service = db.get(CarrierService, service_id)
    if not service or service.carrier_id != carrier_id:
        raise HTTPException(404, "Тариф не найден")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(service, k, v)
    db.commit()
    db.refresh(service)
    return _service_dict(service)


# ── Tariff rates ──────────────────────────────────────────────────────────────

@router.get("/{carrier_id}/services/{service_id}/rates")
def list_rates(
    carrier_id: int,
    service_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> list[dict]:
    rates = db.scalars(
        select(CarrierTariffRate)
        .where(CarrierTariffRate.service_id == service_id)
        .order_by(CarrierTariffRate.zone, CarrierTariffRate.weight_from_kg)
    ).all()
    return [_rate_dict(r) for r in rates]


@router.post("/{carrier_id}/services/{service_id}/rates", status_code=201)
def add_rate(
    carrier_id: int,
    service_id: int,
    payload: RateRow,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    service = db.get(CarrierService, service_id)
    if not service or service.carrier_id != carrier_id:
        raise HTTPException(404, "Тариф не найден")
    rate = CarrierTariffRate(
        service_id=service_id,
        effective_from=date.today(),
        **payload.model_dump(),
    )
    db.add(rate)
    db.commit()
    db.refresh(rate)
    return _rate_dict(rate)


@router.delete("/{carrier_id}/services/{service_id}/rates/{rate_id}", status_code=204)
def delete_rate(
    carrier_id: int,
    service_id: int,
    rate_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> None:
    rate = db.get(CarrierTariffRate, rate_id)
    if not rate or rate.service_id != service_id:
        raise HTTPException(404, "Строка не найдена")
    db.delete(rate)
    db.commit()


@router.post("/{carrier_id}/services/{service_id}/rates/upload")
async def upload_tariff_grid(
    carrier_id: int,
    service_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    """
    Загрузить тарифную сетку из JSON-файла.
    Формат: список объектов с полями zone, weight_from_kg, weight_to_kg,
    base_price, per_unit_price, per_unit_weight_kg, currency, eta_days_min, eta_days_max.
    Заменяет все активные строки для данного тарифа.
    """
    service = db.get(CarrierService, service_id)
    if not service or service.carrier_id != carrier_id:
        raise HTTPException(404, "Тариф не найден")

    _MAX_UPLOAD_BYTES = 1 * 1024 * 1024  # 1 MB
    content = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Файл слишком большой (максимум 1 МБ)")
    try:
        rows: list[dict] = json.loads(content)
        if not isinstance(rows, list):
            raise ValueError("Expected a JSON array")
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(422, f"Неверный формат файла: {exc}") from exc

    # Deactivate old rates
    db.execute(
        sa_update(CarrierTariffRate)
        .where(CarrierTariffRate.service_id == service_id)
        .values(is_active=False)
    )

    inserted = 0
    for row in rows:
        try:
            validated = RateRow(**row)
        except Exception as exc:
            raise HTTPException(422, f"Ошибка в строке {inserted + 1}: {exc}") from exc
        rate = CarrierTariffRate(
            service_id=service_id,
            effective_from=date.today(),
            **validated.model_dump(),
        )
        db.add(rate)
        inserted += 1

    db.commit()
    return {"inserted": inserted, "service_id": service_id}


# ── Zone cities ───────────────────────────────────────────────────────────────

@router.get("/{carrier_id}/cities")
def list_zone_cities(
    carrier_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> list[dict]:
    cities = db.scalars(
        select(CarrierZoneCity)
        .where(CarrierZoneCity.carrier_id == carrier_id)
        .order_by(CarrierZoneCity.zone, CarrierZoneCity.city_name)
    ).all()
    return [{"id": c.id, "city_name": c.city_name, "zone": c.zone, "city_type": c.city_type} for c in cities]


@router.post("/{carrier_id}/cities", status_code=201)
def add_zone_city(
    carrier_id: int,
    payload: ZoneCityCreate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    if not db.get(Carrier, carrier_id):
        raise HTTPException(404, "Перевозчик не найден")
    city = CarrierZoneCity(
        carrier_id=carrier_id,
        city_name=payload.city_name,
        city_name_normalized=payload.city_name.lower().strip(),
        zone=payload.zone,
        city_type=payload.city_type,
    )
    db.add(city)
    db.commit()
    db.refresh(city)
    return {"id": city.id, "city_name": city.city_name, "zone": city.zone}
