from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.status_machine import InvalidTransitionError, transition_order
from app.modules.carriers.integration_log import IntegrationLogRepository
from app.modules.carriers.webhook_config import CarrierWebhookRepository
from app.modules.dispatch.models import DispatchJob, DispatchJobStatus, OrderStatusHistory
from app.modules.orders.models import OrderDraft
from app.modules.shipments.repository import ShipmentsRepository
from app.modules.shipments.service import ShipmentsService

logger = logging.getLogger(__name__)

_webhook_repo = CarrierWebhookRepository()
_shipments_svc = ShipmentsService()
_shipments_repo = ShipmentsRepository()
_integration_log = IntegrationLogRepository()

RETRY_DELAYS_SECONDS = [60, 300, 900]


def create_dispatch_job(
    db: Session,
    *,
    order: OrderDraft,
    changed_by_user_id: int | None = None,
) -> DispatchJob:
    old_status = order.status
    try:
        transition_order(old_status, "dispatch_queued")
    except InvalidTransitionError as exc:
        raise ValueError(str(exc)) from exc

    job = DispatchJob(
        order_id=order.id,
        carrier_code=order.carrier_code_snapshot,
        status=DispatchJobStatus.QUEUED,
        attempts=0,
        max_attempts=3,
    )
    db.add(job)
    order.status = "dispatch_queued"

    db.add(
        OrderStatusHistory(
            order_id=order.id,
            old_status=old_status,
            new_status="dispatch_queued",
            changed_by_user_id=changed_by_user_id,
            source="payment_webhook",
            comment="Payment confirmed, dispatch job created",
        )
    )
    return job


def record_order_status(
    db: Session,
    *,
    order: OrderDraft,
    new_status: str,
    source: str,
    changed_by_user_id: int | None = None,
    comment: str | None = None,
) -> None:
    old_status = order.status
    try:
        transition_order(old_status, new_status)
    except InvalidTransitionError as exc:
        raise ValueError(str(exc)) from exc

    db.add(
        OrderStatusHistory(
            order_id=order.id,
            old_status=old_status,
            new_status=new_status,
            changed_by_user_id=changed_by_user_id,
            source=source,
            comment=comment,
        )
    )
    order.status = new_status


class DispatchWorker:
    def run_once(self, db: Session) -> int:
        jobs = db.scalars(
            select(DispatchJob).where(
                DispatchJob.status == DispatchJobStatus.QUEUED,
                (DispatchJob.next_retry_at.is_(None))
                | (DispatchJob.next_retry_at <= datetime.utcnow()),
            ).limit(10)
        ).all()

        processed = 0
        for job in jobs:
            self._process_job(db, job)
            processed += 1
        return processed

    def _process_job(self, db: Session, job: DispatchJob) -> None:
        job.status = DispatchJobStatus.PROCESSING
        job.attempts += 1
        db.flush()

        order = db.get(OrderDraft, job.order_id)
        if not order:
            logger.error("dispatch_worker: order %s not found for job %s", job.order_id, job.id)
            job.status = DispatchJobStatus.FAILED
            job.last_error = "Order not found"
            db.commit()
            return

        try:
            tracking_number = self._dispatch_to_carrier(db, order)

            _shipments_svc.create_for_order(
                db,
                order_draft_id=order.id,
                carrier_code=order.carrier_code_snapshot,
            )
            shipment = _shipments_repo.get_by_order_id(db, order.id)
            if shipment and tracking_number:
                shipment.carrier_tracking_number = tracking_number
                shipment.status = "dispatched"

            old_status = order.status
            order.status = "sent_to_carrier"
            db.add(
                OrderStatusHistory(
                    order_id=order.id,
                    old_status=old_status,
                    new_status="sent_to_carrier",
                    source="system_worker",
                    comment=f"Dispatched via job {job.id}",
                )
            )

            job.status = DispatchJobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            logger.info("dispatch_worker: job %s completed, order %s sent_to_carrier", job.id, order.id)

        except Exception as exc:
            logger.warning(
                "dispatch_worker: job %s attempt %d/%d failed: %s",
                job.id,
                job.attempts,
                job.max_attempts,
                exc,
            )
            job.last_error = str(exc)

            if job.attempts < job.max_attempts:
                delay = RETRY_DELAYS_SECONDS[min(job.attempts - 1, len(RETRY_DELAYS_SECONDS) - 1)]
                job.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
                job.status = DispatchJobStatus.QUEUED
            else:
                job.status = DispatchJobStatus.FAILED
                old_status = order.status
                order.status = "dispatch_failed"
                order.dispatch_error = str(exc)
                db.add(
                    OrderStatusHistory(
                        order_id=order.id,
                        old_status=old_status,
                        new_status="dispatch_failed",
                        source="system_worker",
                        comment=f"Max attempts reached: {exc}",
                    )
                )

        db.commit()

    def _dispatch_to_carrier(self, db: Session, order: OrderDraft) -> str | None:
        from app.modules.carriers.api_clients.registry import get_client
        from app.modules.carriers.api_credentials import CarrierAPICredentialsRepository

        carrier_code = order.carrier_code_snapshot

        # ── Priority 1: direct carrier API ──────────────────────────────────
        client = get_client(carrier_code)
        creds = CarrierAPICredentialsRepository().get_by_carrier_code(db, carrier_code)

        if client and creds and creds.is_active:
            logger.info("dispatch_worker: using API client for carrier %s, order %s", carrier_code, order.id)
            order_data = _build_api_order_data(order)
            api_creds = {"api_url": creds.api_url, "api_token": creds.api_token, **(creds.extra_config or {})}
            t0 = time.monotonic()
            try:
                result = client.create_invoice(order_data, api_creds)
                duration_ms = int((time.monotonic() - t0) * 1000)
                cfg = _webhook_repo.get_by_carrier_code(db, carrier_code)
                if cfg:
                    cfg.last_success_at = datetime.utcnow()
                    cfg.last_error = None
                _integration_log.create(
                    db, carrier_code=carrier_code, direction="outbound",
                    event_type="dispatch", order_id=order.id,
                    payload=json.dumps(order_data),
                    response=json.dumps({"waybill_number": result.waybill_number}),
                    duration_ms=duration_ms, status="success",
                )
            except Exception as exc:
                duration_ms = int((time.monotonic() - t0) * 1000)
                cfg = _webhook_repo.get_by_carrier_code(db, carrier_code)
                if cfg:
                    cfg.last_error = str(exc)
                _integration_log.create(
                    db, carrier_code=carrier_code, direction="outbound",
                    event_type="dispatch", order_id=order.id,
                    payload=json.dumps(order_data),
                    duration_ms=duration_ms, status="error", error_message=str(exc),
                )
                raise

            if result.waybill_pdf_bytes:
                _save_waybill_document(db, order, result.waybill_number, result.waybill_pdf_bytes)
            return result.waybill_number

        # ── Priority 2: webhook push (Generic Webhook Dispatcher) ───────────
        cfg = _webhook_repo.get_by_carrier_code(db, carrier_code)
        if not cfg or not cfg.is_active or not cfg.push_url:
            raise RuntimeError(
                f"Carrier '{carrier_code}' has no active API credentials or webhook config"
            )

        payload = _build_dispatch_payload(order)
        json_body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
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
            resp = httpx.post(
                cfg.push_url,
                content=json_body.encode(),
                headers=headers,
                timeout=cfg.timeout_seconds,
            )
            resp.raise_for_status()
            duration_ms = int((time.monotonic() - t0) * 1000)
            cfg.last_success_at = datetime.utcnow()
            cfg.last_error = None
            _integration_log.create(
                db, carrier_code=carrier_code, direction="outbound",
                event_type="dispatch", order_id=order.id,
                payload=json_body,
                response=resp.text[:2000],
                http_status=resp.status_code,
                duration_ms=duration_ms, status="success",
            )
            return resp.json().get("tracking_number")
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            http_status = getattr(getattr(exc, "response", None), "status_code", None)
            cfg.last_error = str(exc)
            _integration_log.create(
                db, carrier_code=carrier_code, direction="outbound",
                event_type="dispatch", order_id=order.id,
                payload=json_body,
                http_status=http_status,
                duration_ms=duration_ms, status="error", error_message=str(exc),
            )
            raise


def _build_api_order_data(order: OrderDraft) -> dict:
    """Нормализованные данные заказа для передачи в CarrierAPIClient."""
    sender = next((p for p in order.parties if p.role == "sender"), None)
    recipient = next((p for p in order.parties if p.role == "recipient"), None)
    return {
        "order_id": order.id,
        "order_reference": f"NOVEX-{order.id:06d}",
        "sender": {
            "full_name": sender.full_name if sender else "",
            "phone": sender.phone if sender else "",
            "city": sender.city if sender else order.from_city_snapshot,
            "address": sender.address_line1 if sender else "",
        },
        "recipient": {
            "full_name": recipient.full_name if recipient else "",
            "company": recipient.company_name if recipient else "",
            "phone": recipient.phone if recipient else "",
            "city": recipient.city if recipient else order.to_city_snapshot,
            "address": recipient.address_line1 if recipient else "",
        },
        "packages": [
            {
                "weight_kg": float(p.weight_kg),
                "quantity": p.quantity,
                "description": p.description or "",
            }
            for p in order.packages
        ],
        "declared_value": float(order.price_snapshot),
        "currency": order.currency_snapshot,
        "fragile": order.fragile,
    }


def _save_waybill_document(
    db: "Session",
    order: OrderDraft,
    waybill_number: str,
    pdf_bytes: bytes,
) -> None:
    """Сохранить PDF-накладную перевозчика в хранилище и БД."""
    try:
        from app.core.storage import get_storage
        from app.modules.documents.models import Document, DocumentType

        storage = get_storage()
        filename = f"waybill_{waybill_number}.pdf"
        uploaded = storage.upload_file(
            file_data=pdf_bytes,
            original_name=filename,
            mime_type="application/pdf",
            folder=f"waybills/{order.id}",
        )
        doc = Document(
            order_id=order.id,
            document_type=DocumentType.LABEL,
            file_url=uploaded.object_name,
            file_name=filename,
            mime_type="application/pdf",
        )
        db.add(doc)
        db.flush()
        logger.info("Waybill PDF saved: order_id=%s waybill=%s", order.id, waybill_number)
    except Exception as exc:
        logger.warning("Failed to save waybill PDF (non-fatal): %s", exc)


def _build_dispatch_payload(order: OrderDraft) -> dict:
    sender = next((p for p in order.parties if p.role == "sender"), None)
    recipient = next((p for p in order.parties if p.role == "recipient"), None)
    return {
        "novex_order_id": order.id,
        "order_reference": f"NOVEX-{order.id:06d}",
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
