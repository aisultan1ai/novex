from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)

import httpx
from sqlalchemy import select, update as sa_update
from sqlalchemy.orm import Session

from app.common.status_machine import InvalidTransitionError, transition_order
from app.core.carrier_gateway_client import get_gateway_client
from app.modules.carriers.api_credentials import CarrierAPICredentialsRepository
from app.modules.carriers.integration_log import IntegrationLogRepository
from app.modules.carriers.pii_mask import mask_pii
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
    source: str = "system",
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
            source=source,
            comment="Payment confirmed, dispatch job created",
        )
    )
    db.flush()  # populate job.id so caller can publish to stream after commit
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
    def process_job(self, db: Session, job: DispatchJob) -> None:
        """Public entry point for stream consumer and admin retry."""
        self._process_job(db, job)

    def run_once(self, db: Session) -> int:
        jobs = db.scalars(
            select(DispatchJob)
            .where(
                DispatchJob.status == DispatchJobStatus.QUEUED,
                (DispatchJob.next_retry_at.is_(None))
                | (DispatchJob.next_retry_at <= _utcnow()),
            )
            .with_for_update(skip_locked=True)
            .limit(10)
        ).all()

        processed = 0
        for job in jobs:
            self._process_job(db, job)
            processed += 1
        return processed

    def _process_job(self, db: Session, job: DispatchJob) -> None:
        # Atomically transition QUEUED → PROCESSING. Only one concurrent caller
        # wins this UPDATE; the other sees scalar() == None and bails out.
        # This closes the race between the stream consumer and the scheduler.
        claimed = db.execute(
            sa_update(DispatchJob)
            .where(DispatchJob.id == job.id, DispatchJob.status == DispatchJobStatus.QUEUED)
            .values(status=DispatchJobStatus.PROCESSING, attempts=DispatchJob.attempts + 1)
            .returning(DispatchJob.id)
        ).scalar()
        db.flush()
        if claimed is None:
            logger.info("dispatch_worker: job %s already claimed by another worker, skipping", job.id)
            return
        db.refresh(job)

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

            record_order_status(
                db,
                order=order,
                new_status="sent_to_carrier",
                source="system_worker",
                comment=f"Dispatched via job {job.id}",
            )

            job.status = DispatchJobStatus.COMPLETED
            job.completed_at = _utcnow()
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
                job.next_retry_at = _utcnow() + timedelta(seconds=delay)
                job.status = DispatchJobStatus.QUEUED
            else:
                job.status = DispatchJobStatus.FAILED
                order.dispatch_error = str(exc)
                record_order_status(
                    db,
                    order=order,
                    new_status="dispatch_failed",
                    source="system_worker",
                    comment=f"Max attempts reached: {exc}",
                )

        db.commit()

    def retry_for_order(
        self,
        db: Session,
        order: OrderDraft,
        *,
        admin_id: int | None = None,
    ) -> str | None:
        """Публичный метод для ручного повтора диспетчеризации администратором.
        Находит или создаёт DispatchJob, переводит заказ в dispatch_queued,
        запускает _process_job с полной записью истории.
        """
        existing_job = db.scalar(
            select(DispatchJob).where(
                DispatchJob.order_id == order.id,
            ).order_by(DispatchJob.created_at.desc())
        )

        if existing_job and existing_job.status in (
            DispatchJobStatus.FAILED, DispatchJobStatus.QUEUED
        ):
            job = existing_job
            job.status = DispatchJobStatus.QUEUED
            job.next_retry_at = None
            job.last_error = None
        else:
            job = DispatchJob(
                order_id=order.id,
                carrier_code=order.carrier_code_snapshot,
                status=DispatchJobStatus.QUEUED,
                attempts=0,
                max_attempts=3,
            )
            db.add(job)

        if order.status != "dispatch_queued":
            from app.common.status_machine import can_transition as _can_transition
            if not _can_transition(order.status, "dispatch_queued"):
                raise ValueError(
                    f"Cannot retry dispatch: invalid transition from '{order.status}' to 'dispatch_queued'"
                )
            old_status = order.status
            order.status = "dispatch_queued"
            db.add(OrderStatusHistory(
                order_id=order.id,
                old_status=old_status,
                new_status="dispatch_queued",
                changed_by_user_id=admin_id,
                source="admin",
                comment="Manual retry dispatch",
            ))

        db.flush()
        self._process_job(db, job)

        db.refresh(job)
        if job.status == DispatchJobStatus.COMPLETED:
            shipment = _shipments_repo.get_by_order_id(db, order.id)
            return shipment.carrier_tracking_number if shipment else None
        return None

    def _dispatch_to_carrier(self, db: Session, order: OrderDraft) -> str | None:
        carrier_code = order.carrier_code_snapshot

        # ── Priority 1: carrier API via carrier-gateway ──────────────────────
        creds = CarrierAPICredentialsRepository().get_by_carrier_code(db, carrier_code)

        if creds and creds.is_active:
            logger.info("dispatch_worker: calling carrier-gateway for carrier=%s order=%s", carrier_code, order.id)
            order_data = _build_api_order_data(order)
            api_creds = {
                "api_url": creds.api_url,
                "api_token": creds.api_token,
                **(creds.extra_config or {}),
            }
            t0 = time.monotonic()
            try:
                result = get_gateway_client().create_invoice(carrier_code, order_data, api_creds)
                duration_ms = int((time.monotonic() - t0) * 1000)
                cfg = _webhook_repo.get_by_carrier_code(db, carrier_code)
                if cfg:
                    cfg.last_success_at = _utcnow()
                    cfg.last_error = None
                _integration_log.create(
                    db, carrier_code=carrier_code, direction="outbound",
                    event_type="dispatch", order_id=order.id,
                    payload=json.dumps(mask_pii(order_data)),
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
                    payload=json.dumps(mask_pii(order_data)),
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
            cfg.last_success_at = _utcnow()
            cfg.last_error = None
            masked_body = json.dumps(mask_pii(payload), ensure_ascii=False, sort_keys=True)
            _integration_log.create(
                db, carrier_code=carrier_code, direction="outbound",
                event_type="dispatch", order_id=order.id,
                payload=masked_body,
                response=resp.text[:2000],
                http_status=resp.status_code,
                duration_ms=duration_ms, status="success",
            )
            return resp.json().get("tracking_number")
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            http_status = getattr(getattr(exc, "response", None), "status_code", None)
            cfg.last_error = str(exc)
            masked_body = json.dumps(mask_pii(payload), ensure_ascii=False, sort_keys=True)
            _integration_log.create(
                db, carrier_code=carrier_code, direction="outbound",
                event_type="dispatch", order_id=order.id,
                payload=masked_body,
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
                "declared_value": float(p.declared_value) if p.declared_value else None,
            }
            for p in order.packages
        ],
        "declared_value": (
            sum(float(p.declared_value or 0) for p in order.packages)
            or float(order.price_snapshot or 0)
        ),
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
