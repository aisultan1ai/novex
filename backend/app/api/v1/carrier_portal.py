from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import require_carrier
from app.modules.carriers.models import Carrier
from app.modules.carriers.webhook_config import CarrierWebhookConfig, CarrierWebhookRepository
from app.modules.identity.models import CarrierProfile, User

router = APIRouter(prefix="/carrier", tags=["carrier-portal"])

_webhook_repo = CarrierWebhookRepository()


def _mask_secret(secret: str | None) -> str | None:
    if not secret:
        return None
    prefix = "nvx_live_"
    raw = secret[len(prefix):] if secret.startswith(prefix) else secret
    if len(raw) <= 8:
        return prefix + "*" * len(raw)
    return prefix + "*" * (len(raw) - 4) + raw[-4:]


def _get_carrier_profile(user: User, db: Session) -> CarrierProfile:
    profile = db.scalar(select(CarrierProfile).where(CarrierProfile.user_id == user.id))
    if not profile:
        raise HTTPException(404, "Профиль перевозчика не найден")
    return profile


@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_carrier),
) -> dict:
    cp = _get_carrier_profile(current_user, db)
    carrier = db.get(Carrier, cp.carrier_id)
    if not carrier:
        raise HTTPException(404, "Перевозчик не найден")

    webhook = db.scalar(
        select(CarrierWebhookConfig).where(
            CarrierWebhookConfig.carrier_code == carrier.code
        )
    )

    return {
        "carrier": {
            "id": carrier.id,
            "code": carrier.code,
            "name": carrier.name,
            "description": carrier.description,
            "is_active": carrier.is_active,
        },
        "integration": {
            "push_url": webhook.push_url if webhook else None,
            "webhook_secret_masked": _mask_secret(webhook.webhook_secret if webhook else None),
            "is_active": webhook.is_active if webhook else False,
            "retry_count": webhook.retry_count if webhook else 3,
            "timeout_seconds": webhook.timeout_seconds if webhook else 10,
        },
    }


@router.get("/integration-config")
def get_integration_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_carrier),
) -> dict:
    """Returns full integration configuration for both push and pull methods."""
    cp = _get_carrier_profile(current_user, db)
    carrier = db.get(Carrier, cp.carrier_id)
    if not carrier:
        raise HTTPException(404, "Перевозчик не найден")

    webhook = db.scalar(
        select(CarrierWebhookConfig).where(
            CarrierWebhookConfig.carrier_code == carrier.code
        )
    )

    return {
        "carrier_code": carrier.code,
        "methods": {
            "outbound": {
                "description": "Novex отправляет заказы на ваш API (push)",
                "novex_calls_your_url": webhook.push_url if webhook else None,
                "method": "POST",
                "hmac_header": "X-Novex-Signature",
                "hmac_algorithm": "HMAC-SHA256",
                "hmac_description": "signature = HMAC-SHA256(secret, timestamp + raw_body)",
                "secret_key_masked": _mask_secret(webhook.webhook_secret if webhook else None),
                "active": bool(webhook and webhook.push_url),
                "example_payload": {
                    "novex_order_id": 12345,
                    "order_reference": "NOVEX-012345",
                    "tariff_code": "standard",
                    "sender": {"full_name": "...", "phone": "+77001234567", "city": "Almaty", "address": "..."},
                    "recipient": {"full_name": "...", "phone": "+77007654321", "city": "Astana", "address": "..."},
                    "packages": [{"weight_kg": 1.5, "width_cm": 20, "height_cm": 15, "depth_cm": 10, "quantity": 1}],
                    "declared_value": 3500.0,
                    "currency": "KZT",
                },
                "expected_response": {"tracking_number": "YOUR_TRACK_NUMBER"},
            },
            "inbound": {
                "description": "Вы отправляете трекинг-события на наш webhook (push)",
                "your_calls_our_url": f"/api/v1/carriers/{carrier.code}/tracking-webhook",
                "method": "POST",
                "hmac_header": "X-Carrier-Signature",
                "hmac_algorithm": "HMAC-SHA256",
                "hmac_description": "signature = HMAC-SHA256(secret, raw_body). Include X-Novex-Timestamp header.",
                "secret_key_masked": _mask_secret(webhook.webhook_secret if webhook else None),
                "example_payload": {
                    "novex_order_id": 12345,
                    "event_id": "unique-event-id-per-event",
                    "status": "in_transit",
                    "location": "Almaty sorting center",
                    "description": "Package arrived at sorting center",
                },
                "supported_statuses": [
                    "picked_up", "in_transit", "arrived",
                    "delivered", "returned", "return_in_progress",
                ],
            },
        },
    }


@router.post("/integration-config/regenerate-secret")
def regenerate_secret(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_carrier),
) -> dict:
    """Regenerate webhook secret. Returns the new secret once (store it safely)."""
    cp = _get_carrier_profile(current_user, db)
    carrier = db.get(Carrier, cp.carrier_id)
    if not carrier:
        raise HTTPException(404, "Перевозчик не найден")

    webhook = db.scalar(
        select(CarrierWebhookConfig).where(
            CarrierWebhookConfig.carrier_code == carrier.code
        )
    )
    if not webhook:
        raise HTTPException(404, "Конфигурация webhook не найдена")

    new_secret = "nvx_live_" + secrets.token_hex(24)
    webhook.webhook_secret = new_secret
    db.commit()

    return {
        "webhook_secret": new_secret,
        "warning": "Store this secret securely — it will not be shown again in full.",
    }
