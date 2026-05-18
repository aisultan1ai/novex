from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import require_carrier
from app.modules.carriers.models import Carrier
from app.modules.carriers.webhook_config import CarrierWebhookConfig
from app.modules.identity.models import CarrierProfile, User

router = APIRouter(prefix="/carrier", tags=["carrier-portal"])


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
            "webhook_secret": webhook.webhook_secret if webhook else None,
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
                "secret_key": webhook.webhook_secret if webhook else None,
                "active": bool(webhook and webhook.push_url),
            },
            "inbound": {
                "description": "Вы отправляете трекинг-события на наш webhook (push)",
                "your_calls_our_url": (
                    f"/api/v1/carriers/{carrier.code}/tracking-webhook"
                ),
                "method": "POST",
                "hmac_header": "X-Carrier-Signature",
                "hmac_algorithm": "HMAC-SHA256",
                "secret_key": webhook.webhook_secret if webhook else None,
            },
        },
    }
