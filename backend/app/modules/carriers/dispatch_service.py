from __future__ import annotations

import hashlib
import hmac
import json
import logging

import httpx
from sqlalchemy.orm import Session

from app.modules.carriers.webhook_config import CarrierWebhookRepository
from app.modules.notifications.service import NotificationsService
from app.modules.orders.models import OrderDraft

logger = logging.getLogger(__name__)

_webhook_repo = CarrierWebhookRepository()
_notifications_svc = NotificationsService()


def _hmac_sign(payload: dict, secret: str) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class CarrierDispatchService:

    def dispatch(self, db: Session, order: OrderDraft) -> str | None:
        cfg = _webhook_repo.get_by_carrier_code(db, order.carrier_code_snapshot)
        if cfg is None or not cfg.is_active:
            self._mark_pending_manual(db, order)
            return None

        payload = self._build_payload(order)

        for attempt in range(1, cfg.retry_count + 1):
            try:
                json_body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                headers = {
                    "Content-Type": "application/json",
                    "X-Novex-Platform": "novex-logistics",
                }
                if cfg.webhook_secret:
                    headers["X-Novex-Signature"] = _hmac_sign(payload, cfg.webhook_secret)

                resp = httpx.post(
                    cfg.push_url,
                    content=json_body.encode(),
                    headers=headers,
                    timeout=cfg.timeout_seconds,
                )
                resp.raise_for_status()
                return resp.json()["tracking_number"]
            except Exception as exc:
                logger.warning(
                    "dispatch attempt %d/%d failed for order %s: %s",
                    attempt, cfg.retry_count, order.id, exc,
                )
                if attempt == cfg.retry_count:
                    self._mark_dispatch_failed(db, order, str(exc))
                    return None

        return None

    def _build_payload(self, order: OrderDraft) -> dict:
        sender = next((p for p in order.parties if p.role == "sender"), None)
        recipient = next((p for p in order.parties if p.role == "recipient"), None)
        return {
            "novex_order_id": order.id,
            "tariff_code": order.tariff_name_snapshot,
            "sender": {
                "full_name": sender.full_name if sender else "",
                "phone": sender.phone if sender else "",
                "city": sender.city if sender else "",
                "address": sender.address_line1 if sender else "",
            },
            "recipient": {
                "full_name": recipient.full_name if recipient else "",
                "phone": recipient.phone if recipient else "",
                "city": recipient.city if recipient else "",
                "address": recipient.address_line1 if recipient else "",
            },
            "packages": [
                {
                    "weight_kg": float(p.weight_kg),
                    "width_cm": float(p.width_cm),
                    "height_cm": float(p.height_cm),
                    "depth_cm": float(p.depth_cm),
                    "quantity": p.quantity,
                }
                for p in order.packages
            ],
            "declared_value": float(order.price_snapshot),
            "currency": order.currency_snapshot,
            "additional_services": {
                "call_before_delivery": order.call_before_delivery,
                "insurance": order.insurance,
                "fragile": order.fragile,
            },
        }

    def _mark_dispatch_failed(self, db: Session, order: OrderDraft, error_msg: str) -> None:
        order.status = "dispatch_failed"
        order.dispatch_error = error_msg
        _notifications_svc.notify_order_status(
            db,
            user_id=order.user_id,
            order_id=order.id,
            status="dispatch_failed",
        )

    def _mark_pending_manual(self, db: Session, order: OrderDraft) -> None:
        order.status = "pending_manual"
        _notifications_svc.notify_order_status(
            db,
            user_id=order.user_id,
            order_id=order.id,
            status="pending_manual",
        )
