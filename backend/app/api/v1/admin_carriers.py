from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import time
import uuid
from datetime import date

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.db import get_db
from app.core.dependencies import require_admin, require_admin_or_operator
from app.modules.carriers.integration_log import IntegrationLogRepository
from app.modules.carriers.models import (
    Carrier,
    CarrierService,
    CarrierTariffRate,
    CarrierZoneCity,
)
from app.modules.carriers.webhook_config import (
    CarrierWebhookRepository,
    CarrierWebhookUpdate,
)
from app.modules.identity.models import CarrierProfile, User
from app.modules.identity.service import CreateCarrierAccountRequest, IdentityService

_webhook_repo = CarrierWebhookRepository()
_integration_log = IntegrationLogRepository()

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/carriers", tags=["admin:carriers"])
_identity_service = IdentityService()


# ── Pydantic schemas ──────────────────────────────────────────────────────────


class CarrierCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    is_active: bool = True
    notification_email: EmailStr | None = None


class CarrierUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    # None on the wire means "не изменять". To clear the address, send an
    # empty string; we translate that to NULL below in update_carrier.
    notification_email: str | None = None


class ServiceCreate(BaseModel):
    code: str
    name: str
    shipment_type: str | None = None
    is_active: bool = True


class ServiceUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class RateRow(BaseModel):
    zone: int
    weight_from_kg: float
    weight_to_kg: float | None = None
    base_price: float
    per_unit_price: float | None = None
    per_unit_weight_kg: float | None = None
    currency: str = "KZT"
    eta_days_min: int | None = None
    eta_days_max: int | None = None


class RateRowPatch(BaseModel):
    zone: int | None = None
    weight_from_kg: float | None = None
    weight_to_kg: float | None = None
    base_price: float | None = None
    per_unit_price: float | None = None
    per_unit_weight_kg: float | None = None
    currency: str | None = None
    eta_days_min: int | None = None
    eta_days_max: int | None = None


class ZoneCityCreate(BaseModel):
    city_name: str
    zone: int
    city_type: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────


def _carrier_dict(c: Carrier) -> dict:
    return {
        "id": c.id,
        "code": c.code,
        "name": c.name,
        "description": c.description,
        "is_active": c.is_active,
        "notification_email": c.notification_email,
    }


def _service_dict(s: CarrierService) -> dict:
    return {
        "id": s.id,
        "code": s.code,
        "name": s.name,
        "shipment_type": s.shipment_type,
        "is_active": s.is_active,
    }


def _rate_dict(r: CarrierTariffRate) -> dict:
    return {
        "id": r.id,
        "zone": r.zone,
        "weight_from_kg": float(r.weight_from_kg),
        "weight_to_kg": float(r.weight_to_kg) if r.weight_to_kg is not None else None,
        "base_price": float(r.base_price),
        "per_unit_price": float(r.per_unit_price)
        if r.per_unit_price is not None
        else None,
        "per_unit_weight_kg": float(r.per_unit_weight_kg)
        if r.per_unit_weight_kg is not None
        else None,
        "currency": r.currency,
        "eta_days_min": r.eta_days_min,
        "eta_days_max": r.eta_days_max,
        "is_active": r.is_active,
    }


# ── Carriers CRUD ─────────────────────────────────────────────────────────────


@router.get("")
def list_carriers(
    db: Session = Depends(get_db),
    _=Depends(require_admin_or_operator),
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
    logger.info("Carrier created: id=%d code=%s", carrier.id, carrier.code)
    return _carrier_dict(carrier)


@router.get("/{carrier_id}")
def get_carrier(
    carrier_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin_or_operator),
) -> dict:
    carrier = db.scalar(
        select(Carrier)
        .options(
            selectinload(Carrier.services).selectinload(CarrierService.tariff_rates)
        )
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
    updates = payload.model_dump(exclude_none=True)
    # Empty string on notification_email means «очистить»; normalize before
    # writing so we don't store " " that later masquerades as a valid email.
    if "notification_email" in updates:
        stripped = updates["notification_email"].strip()
        if stripped == "":
            updates["notification_email"] = None
        else:
            # Validate on set — reuse pydantic EmailStr so behavior matches CREATE.
            from pydantic import TypeAdapter
            from pydantic import ValidationError as _PyValidationError

            try:
                TypeAdapter(EmailStr).validate_python(stripped)
            except _PyValidationError as exc:
                raise HTTPException(422, f"Неверный email: {exc.errors()[0]['msg']}") from exc
            updates["notification_email"] = stripped
    for k, v in updates.items():
        setattr(carrier, k, v)
    db.commit()
    db.refresh(carrier)
    return _carrier_dict(carrier)


# ── Services ──────────────────────────────────────────────────────────────────


@router.get("/{carrier_id}/services")
def list_services(
    carrier_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin_or_operator),
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
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(require_admin_or_operator),
) -> dict:
    base = (
        select(CarrierTariffRate)
        .where(CarrierTariffRate.service_id == service_id)
        .order_by(CarrierTariffRate.zone, CarrierTariffRate.weight_from_kg)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rates = db.scalars(base.offset((page - 1) * size).limit(size)).all()
    pages = math.ceil(total / size) if total > 0 else 1
    return {
        "items": [_rate_dict(r) for r in rates],
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


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


@router.patch("/{carrier_id}/services/{service_id}/rates/{rate_id}")
def update_rate(
    carrier_id: int,
    service_id: int,
    rate_id: int,
    payload: RateRowPatch,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    rate = db.get(CarrierTariffRate, rate_id)
    if not rate or rate.service_id != service_id:
        raise HTTPException(404, "Строка не найдена")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(rate, field, value)
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
    base_price, per_unit_price, per_unit_weight_kg,
    currency, eta_days_min, eta_days_max.
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
    logger.info(
        "Tariff grid uploaded: carrier_id=%d service_id=%d rows=%d",
        carrier_id,
        service_id,
        inserted,
    )
    return {"inserted": inserted, "service_id": service_id}


# ── Zone cities ───────────────────────────────────────────────────────────────


@router.get("/{carrier_id}/cities")
def list_zone_cities(
    carrier_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(require_admin_or_operator),
) -> dict:
    base = (
        select(CarrierZoneCity)
        .where(CarrierZoneCity.carrier_id == carrier_id)
        .order_by(CarrierZoneCity.zone, CarrierZoneCity.city_name)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    cities = db.scalars(base.offset((page - 1) * size).limit(size)).all()
    pages = math.ceil(total / size) if total > 0 else 1
    items = [
        {"id": c.id, "city_name": c.city_name, "zone": c.zone, "city_type": c.city_type}
        for c in cities
    ]
    return {"items": items, "total": total, "page": page, "size": size, "pages": pages}


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


# ── Carrier portal account ─────────────────────────────────────────────────────


@router.get("/{carrier_id}/accounts")
def list_carrier_accounts(
    carrier_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin_or_operator),
) -> list[dict]:
    """Список пользователей-сотрудников этого перевозчика (по carrier_profiles)."""
    if not db.get(Carrier, carrier_id):
        raise HTTPException(404, "Перевозчик не найден")
    rows = db.execute(
        select(User)
        .join(CarrierProfile, CarrierProfile.user_id == User.id)
        .where(CarrierProfile.carrier_id == carrier_id)
        .order_by(User.created_at.desc())
    ).scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u in rows
    ]


@router.post("/{carrier_id}/account", status_code=201)
def create_carrier_account(
    carrier_id: int,
    payload: CreateCarrierAccountRequest,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    carrier = db.get(Carrier, carrier_id)
    if not carrier:
        raise HTTPException(404, "Перевозчик не найден")
    settings = get_settings()
    profile = _identity_service.create_carrier_account(
        db,
        carrier_id=carrier_id,
        carrier_name=carrier.name,
        payload=payload,
        frontend_url=settings.frontend_url,
    )
    logger.info(
        "Carrier account created: carrier_id=%d email=%s", carrier_id, payload.email
    )
    return {
        "user_id": profile.user_id,
        "email": profile.email,
        "carrier_id": carrier_id,
    }


# ── Integration settings ───────────────────────────────────────────────────────


def _mask_secret(secret: str | None) -> str | None:
    if not secret:
        return None
    prefix = "nvx_live_"
    raw = secret[len(prefix):] if secret.startswith(prefix) else secret
    if len(raw) <= 8:
        return prefix + "*" * len(raw)
    return prefix + "*" * (len(raw) - 4) + raw[-4:]


class IntegrationUpdate(BaseModel):
    push_url: str | None = None
    is_active: bool | None = None
    retry_count: int | None = None
    timeout_seconds: int | None = None
    dispatch_mode: str | None = None
    tracking_mode: str | None = None


def _cfg_to_dict(cfg) -> dict:
    return {
        "carrier_code": cfg.carrier_code,
        "push_url": cfg.push_url,
        "webhook_secret_masked": _mask_secret(cfg.webhook_secret),
        "is_active": cfg.is_active,
        "retry_count": cfg.retry_count,
        "timeout_seconds": cfg.timeout_seconds,
        "dispatch_mode": cfg.dispatch_mode,
        "tracking_mode": cfg.tracking_mode,
        "last_success_at": cfg.last_success_at.isoformat() if cfg.last_success_at else None,
        "last_error": cfg.last_error,
        "updated_at": cfg.updated_at.isoformat(),
    }


@router.get("/{carrier_id}/integration", summary="Настройки интеграции перевозчика")
def get_integration(
    carrier_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    carrier = db.get(Carrier, carrier_id)
    if not carrier:
        raise HTTPException(404, "Перевозчик не найден")
    cfg = _webhook_repo.get_by_carrier_code(db, carrier.code)
    if not cfg:
        return {
            "carrier_code": carrier.code,
            "push_url": None,
            "webhook_secret_masked": None,
            "is_active": False,
            "retry_count": 3,
            "timeout_seconds": 10,
            "dispatch_mode": "auto",
            "tracking_mode": "webhook",
            "last_success_at": None,
            "last_error": None,
            "updated_at": None,
        }
    return _cfg_to_dict(cfg)


@router.put("/{carrier_id}/integration", summary="Обновить настройки интеграции")
def update_integration(
    carrier_id: int,
    payload: IntegrationUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    carrier = db.get(Carrier, carrier_id)
    if not carrier:
        raise HTTPException(404, "Перевозчик не найден")
    cfg = _webhook_repo.update(db, carrier.code, CarrierWebhookUpdate(**payload.model_dump()))
    db.commit()
    return _cfg_to_dict(cfg)


@router.post("/{carrier_id}/integration/regenerate-secret", summary="Сгенерировать новый webhook secret")
def regenerate_integration_secret(
    carrier_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    carrier = db.get(Carrier, carrier_id)
    if not carrier:
        raise HTTPException(404, "Перевозчик не найден")
    new_secret = _webhook_repo.regenerate_secret(db, carrier.code)
    db.commit()
    return {
        "webhook_secret": new_secret,
        "warning": "Store this secret securely — it will not be shown again in full.",
    }


@router.post("/{carrier_id}/integration/test-webhook", summary="Отправить тестовый заказ на push_url")
def test_integration_webhook(
    carrier_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    carrier = db.get(Carrier, carrier_id)
    if not carrier:
        raise HTTPException(404, "Перевозчик не найден")
    cfg = _webhook_repo.get_by_carrier_code(db, carrier.code)
    if not cfg or not cfg.push_url:
        raise HTTPException(400, "push_url не настроен")

    test_payload = {
        "novex_order_id": 0,
        "order_reference": "NOVEX-TEST-000000",
        "tariff_code": "test",
        "test": True,
        "sender": {"full_name": "Тест Отправитель", "phone": "+70000000000", "city": "Almaty", "address": "Test St 1"},
        "recipient": {
            "full_name": "Тест Получатель", "phone": "+70000000001",
            "city": "Astana", "address": "Test Ave 2",
        },
        "packages": [{"weight_kg": 1.0, "width_cm": 20, "height_cm": 15, "depth_cm": 10, "quantity": 1}],
        "declared_value": 1000.0,
        "currency": "KZT",
        "additional_services": {"call_before_delivery": False, "insurance": False, "fragile": False},
    }
    json_body = json.dumps(test_payload, ensure_ascii=False, sort_keys=True)
    timestamp = str(int(time.time()))
    event_id = str(uuid.uuid4())

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "X-Novex-Platform": "novex-logistics",
        "X-Novex-Timestamp": timestamp,
        "X-Novex-Event-Id": event_id,
    }
    if cfg.webhook_secret:
        sig_input = (timestamp + json_body).encode()
        headers["X-Novex-Signature"] = hmac.new(
            cfg.webhook_secret.encode(), sig_input, hashlib.sha256
        ).hexdigest()

    t0 = time.monotonic()
    try:
        resp = httpx.post(cfg.push_url, content=json_body.encode(), headers=headers, timeout=cfg.timeout_seconds)
        duration_ms = int((time.monotonic() - t0) * 1000)
        ok = resp.is_success
        response_text = resp.text[:1000]
        _integration_log.create(
            db, carrier_code=carrier.code, direction="outbound", event_type="test_webhook",
            payload=json_body, response=response_text, http_status=resp.status_code,
            duration_ms=duration_ms, status="success" if ok else "error",
            error_message=None if ok else f"HTTP {resp.status_code}: {response_text}",
        )
        db.commit()
        return {
            "ok": ok,
            "http_status": resp.status_code,
            "duration_ms": duration_ms,
            "response": response_text,
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        _integration_log.create(
            db, carrier_code=carrier.code, direction="outbound", event_type="test_webhook",
            payload=json_body, duration_ms=duration_ms, status="error", error_message=str(exc),
        )
        db.commit()
        return {"ok": False, "duration_ms": duration_ms, "error": str(exc)}


@router.get("/{carrier_id}/integration/logs", summary="Журнал интеграционных событий")
def get_integration_logs(
    carrier_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    carrier = db.get(Carrier, carrier_id)
    if not carrier:
        raise HTTPException(404, "Перевозчик не найден")
    logs = _integration_log.list_recent(db, carrier.code, limit=limit)
    return {
        "items": [
            {
                "id": log.id,
                "direction": log.direction,
                "event_type": log.event_type,
                "order_id": log.order_id,
                "http_status": log.http_status,
                "duration_ms": log.duration_ms,
                "status": log.status,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "total": len(logs),
    }
