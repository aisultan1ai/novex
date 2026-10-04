from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from app.common.status_machine import InvalidTransitionError, transition_order
from app.common.time_utils import utcnow as _utcnow
from app.core.carrier_gateway_client import get_gateway_client
from app.modules.carriers.api_credentials import CarrierAPICredentialsRepository
from app.modules.carriers.integration_log import IntegrationLogRepository
from app.modules.carriers.pii_mask import mask_pii
from app.modules.carriers.webhook_config import CarrierWebhookRepository
from app.modules.dispatch.models import (
    DispatchJob,
    DispatchJobStatus,
    OrderStatusHistory,
)
from app.modules.notifications.service import NotificationsService
from app.modules.orders.models import OrderDraft
from app.modules.shipments.repository import ShipmentsRepository
from app.modules.shipments.service import ShipmentsService

logger = logging.getLogger(__name__)

_webhook_repo = CarrierWebhookRepository()
_shipments_svc = ShipmentsService()
_shipments_repo = ShipmentsRepository()
_integration_log = IntegrationLogRepository()
_notifications_svc = NotificationsService()

def _retry_delays_seconds() -> list[int]:
    """Get retry backoff schedule. Overridable via DISPATCH_RETRY_DELAYS_SECONDS.

    Called at retry time (not module import) so tests / hot-config reloads
    pick up new values without a process restart. Guarantees a non-empty
    list so the min() below never gets `-1` indexing on an empty list.
    """
    from app.core.config import get_settings
    delays = get_settings().dispatch_retry_delays_seconds
    return delays if delays else [60, 300, 900]

def _notify_staff_dispatch_failed(db: Session, order_id: int, error: str) -> None:
    from app.modules.notifications.staff import notify_staff
    notify_staff(db, event="dispatch_failed", order_id=order_id, payload={"error": error[:500]})


@dataclass
class _DispatchOutcome:
    """Values captured from a successful dispatch, to persist on the Shipment."""
    tracking_number: str | None       # carrier's order ID (statusreq/Tracking lookup key)
    barcode: str | None               # physical barcode printed on package (may equal tracking_number)


_PERMANENT_ERROR_KEYWORDS = (
    "авторизаци",  # CSE/Exline auth failure messages
    "логин или пароль",
    "unauthorized",
    "forbidden",
    "authentication",
    "invalid credentials",
    "access denied",
)


def _is_permanent_error(exc: Exception) -> bool:
    """Return True for errors that will not resolve on retry (auth, config)."""
    import httpx
    try:
        from cryptography.fernet import InvalidToken
        if isinstance(exc, InvalidToken):
            return True
    except ImportError:
        pass
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (401, 403)
    msg = str(exc).lower()
    return any(kw in msg for kw in _PERMANENT_ERROR_KEYWORDS)


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
        """Dispatch one job to the carrier.

        Two phases with different failure rules (audit 2026-10-04, T2):

        * Before the carrier call — retryable. The claim (QUEUED → PROCESSING)
          is committed up front so a worker crash mid-call leaves the job in
          PROCESSING (visible, manual review) instead of silently rolling back
          to QUEUED and creating a second waybill on the next tick. The order
          row is then locked and must still be ``dispatch_queued``; a
          cancellation that arrives during the call waits for our commit and
          sees ``sent_to_carrier`` (→ regular cancel-via-API path).
        * After the carrier accepted the order — NOT retryable. Any failure
          from here on is recorded with the waybill number for manual review;
          retrying would create a duplicate waybill (Azimuth cannot cancel).
        """
        # Atomically transition QUEUED → PROCESSING. Only one concurrent caller
        # wins this UPDATE; the other sees scalar() == None and bails out.
        claimed = db.execute(
            sa_update(DispatchJob)
            .where(DispatchJob.id == job.id, DispatchJob.status == DispatchJobStatus.QUEUED)
            .values(status=DispatchJobStatus.PROCESSING, attempts=DispatchJob.attempts + 1)
            .returning(DispatchJob.id)
        ).scalar()
        if claimed is None:
            db.rollback()
            logger.info("dispatch_worker: job %s already claimed by another worker, skipping", job.id)
            return
        db.commit()
        job_id = job.id
        db.refresh(job)

        # Lock the order for the whole carrier call (see docstring).
        order = db.get(OrderDraft, job.order_id, with_for_update=True, populate_existing=True)
        if not order:
            logger.error("dispatch_worker: order %s not found for job %s", job.order_id, job.id)
            job.status = DispatchJobStatus.FAILED
            job.last_error = "Order not found"
            db.commit()
            return

        if order.status != "dispatch_queued":
            # Cancelled / already dispatched / moved by an admin while the job
            # sat in the queue. Calling the carrier now would create a waybill
            # nobody wants.
            logger.warning(
                "dispatch_worker: job %s skipped — order %s is in status %r, not dispatch_queued",
                job.id, order.id, order.status,
            )
            job.status = DispatchJobStatus.CANCELLED
            job.last_error = f"Skipped: order status is '{order.status}', expected 'dispatch_queued'"
            job.completed_at = _utcnow()
            db.commit()
            return

        # ── Phase 1: get a waybill from the carrier (retryable) ──────────────
        try:
            # Idempotency guard: a previous attempt already stored the
            # carrier's waybill — never call create_invoice twice.
            existing_shipment = _shipments_repo.get_by_order_id(db, order.id)
            if existing_shipment and existing_shipment.carrier_tracking_number:
                logger.info(
                    "dispatch_worker: order %s already dispatched (carrier_tracking=%s), "
                    "skipping carrier call and completing job",
                    order.id, existing_shipment.carrier_tracking_number,
                )
                outcome = _DispatchOutcome(
                    tracking_number=existing_shipment.carrier_tracking_number,
                    barcode=existing_shipment.carrier_barcode,
                )
            else:
                outcome = self._dispatch_to_carrier(db, order)
        except Exception as exc:
            self._handle_retryable_failure(db, job_id, exc)
            return

        # ── Phase 2: persist the result (NOT retryable) ──────────────────────
        try:
            self._complete_dispatch(db, job, order, outcome)
        except Exception as exc:
            self._handle_post_dispatch_failure(db, job_id, outcome, exc)
            return

    def _complete_dispatch(
        self,
        db: Session,
        job: DispatchJob,
        order: OrderDraft,
        outcome: _DispatchOutcome,
    ) -> None:
        _shipments_svc.create_for_order(
            db,
            order_draft_id=order.id,
            carrier_code=order.carrier_code_snapshot,
        )
        shipment = _shipments_repo.get_by_order_id(db, order.id)
        if shipment and outcome.tracking_number:
            shipment.carrier_tracking_number = outcome.tracking_number
            # Persist physical barcode separately — Exline returns a
            # scannable code distinct from orderno. When carrier does not
            # issue a distinct barcode (CSE), we fall back to the order
            # number so admin search still resolves.
            shipment.carrier_barcode = outcome.barcode or outcome.tracking_number
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
        db.commit()
        logger.info("dispatch_worker: job %s completed, order %s sent_to_carrier", job.id, order.id)

        # Side effects below run after the commit: the waybill and the status
        # are durable, so a failure here can no longer cause a re-dispatch.

        # Customer notification: use our own public tracking number
        # (shipment.tracking_number, e.g. EXLINE-H7WO0SP9VM7X). That's
        # what the customer sees in the order card and what /tracking
        # accepts as input on our site. It differs from:
        #   - outcome.tracking_number  = orderno for carrier statusreq
        #                                (e.g. NOVEX-000023) — internal
        #   - outcome.barcode          = physical package barcode
        #                                (e.g. KAZ000090191) — internal
        try:
            shipment = _shipments_repo.get_by_order_id(db, order.id)
            _notifications_svc.notify_order_status(
                db,
                user_id=order.user_id,
                order_id=order.id,
                status="sent_to_carrier",
                tracking_number=shipment.tracking_number if shipment else None,
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                "dispatch_worker: notify_order_status failed for order %s (non-fatal)",
                order.id,
            )

        # ── Azimuth /order-courier (optional second step) ──────────────
        # Independent of the main dispatch: a pickup failure does NOT roll
        # back the invoice — Azimuth has no undo for a created waybill.
        # _schedule_azimuth_pickup records pickup_error so an admin can
        # trigger a pickup-only retry via a dedicated endpoint.
        if (
            order.carrier_code_snapshot
            and order.carrier_code_snapshot.lower() == "azimuth"
            and order.pickup_requested
            and not order.pickup_scheduled_azimuth_id
        ):
            try:
                self._schedule_azimuth_pickup(db, order)
                db.commit()
            except Exception:
                db.rollback()
                logger.exception(
                    "dispatch_worker: Azimuth pickup scheduling failed for order %s (non-fatal)",
                    order.id,
                )

    def _handle_retryable_failure(self, db: Session, job_id: int, exc: Exception) -> None:
        """The carrier did not return a waybill — safe to retry."""
        exc_msg = str(exc) or repr(exc) or f"{type(exc).__name__}: (no message)"
        # Discard partial writes (and release the order row lock) before the
        # error bookkeeping below.
        db.rollback()

        job = db.get(DispatchJob, job_id)
        if job is None:
            logger.error("dispatch_worker: job %s vanished after rollback", job_id)
            return
        logger.warning(
            "dispatch_worker: job %s attempt %d/%d failed [%s]: %s",
            job.id, job.attempts, job.max_attempts, type(exc).__name__, exc_msg,
        )
        order = db.get(OrderDraft, job.order_id)
        job.last_error = exc_msg

        permanent = _is_permanent_error(exc)
        if not permanent and job.attempts < job.max_attempts:
            delays = _retry_delays_seconds()
            delay = delays[min(job.attempts - 1, len(delays) - 1)]
            job.next_retry_at = _utcnow() + timedelta(seconds=delay)
            job.status = DispatchJobStatus.QUEUED
        else:
            if permanent:
                logger.error("dispatch_worker: job %s permanent error (no retry): %s", job.id, exc)
            job.status = DispatchJobStatus.FAILED
            # Surface it on the order too — otherwise a permanent error (bad
            # carrier credentials) left the order in dispatch_queued forever.
            if order is not None and order.status == "dispatch_queued":
                order.dispatch_error = exc_msg
                record_order_status(
                    db,
                    order=order,
                    new_status="dispatch_failed",
                    source="system_worker",
                    comment=f"Max attempts reached: {exc_msg}",
                )
        db.commit()
        if job.status == DispatchJobStatus.FAILED:
            _notify_staff_dispatch_failed(db, job.order_id, exc_msg)

    def _handle_post_dispatch_failure(
        self,
        db: Session,
        job_id: int,
        outcome: _DispatchOutcome,
        exc: Exception,
    ) -> None:
        """The carrier already created a waybill but we failed to record it.

        Never retry automatically. Store the waybill number on the shipment
        (so the idempotency guard short-circuits any manual retry) and flag
        the order for manual review.
        """
        waybill = outcome.tracking_number or "?"
        msg = (
            f"Накладная {waybill} создана у перевозчика, но заказ не удалось "
            f"обновить: {exc}. Требуется ручная проверка — повторная отправка "
            f"не создаст новую накладную."
        )
        logger.error("dispatch_worker: job %s post-dispatch failure: %s", job_id, msg, exc_info=exc)
        db.rollback()

        job = db.get(DispatchJob, job_id)
        if job is None:
            logger.error("dispatch_worker: job %s vanished after rollback (waybill=%s)", job_id, waybill)
            return
        job.status = DispatchJobStatus.FAILED
        job.last_error = msg
        db.commit()  # the job row alone must survive even if the rest fails

        try:
            order = db.get(OrderDraft, job.order_id)
            if order is not None:
                _shipments_svc.create_for_order(
                    db, order_draft_id=order.id, carrier_code=order.carrier_code_snapshot,
                )
                shipment = _shipments_repo.get_by_order_id(db, order.id)
                if shipment and outcome.tracking_number:
                    shipment.carrier_tracking_number = outcome.tracking_number
                    shipment.carrier_barcode = outcome.barcode or outcome.tracking_number
                order.dispatch_error = msg
                if order.status == "dispatch_queued":
                    record_order_status(
                        db,
                        order=order,
                        new_status="dispatch_failed",
                        source="system_worker",
                        comment=msg,
                    )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                "dispatch_worker: could not persist waybill %s for job %s — see job.last_error",
                waybill, job_id,
            )
        _notify_staff_dispatch_failed(db, job.order_id, msg)

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
            job.attempts = 0  # reset so retry gets full max_attempts budget
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

    def _schedule_azimuth_pickup(self, db: Session, order: OrderDraft) -> None:
        """Fire Azimuth's /order-courier for an already-dispatched order.

        Idempotent: refuses to re-schedule when pickup_scheduled_azimuth_id
        is set (Azimuth has no dedup on their side, so we hold the lock).
        A failure here does not raise — it records the error on the order
        for an admin retry.
        """
        from app.modules.carriers.api_clients.azimuth import AzimuthAPIClient
        from app.modules.carriers.azimuth_regions import AzimuthRegionsRepository

        creds_row = CarrierAPICredentialsRepository().get_by_carrier_code(db, "azimuth")
        if not creds_row or not creds_row.is_active:
            order.pickup_error = "Нет активных Azimuth-креденшелсов"
            return
        creds = {
            "api_url": creds_row.api_url,
            "api_token": creds_row.api_token,
            **(creds_row.extra_config or {}),
        }

        sender = next((p for p in order.parties if p.role == "sender"), None)
        recipient = next((p for p in order.parties if p.role == "recipient"), None)
        if not sender:
            order.pickup_error = "Нет данных отправителя для вызова курьера"
            return

        # Resolve the exact `region` string Azimuth expects — the docs example
        # is "title, path" (e.g. "Алматы, Казахстан, город Алматы"). We store
        # {title, path} from /regions and glue them here.
        regions_repo = AzimuthRegionsRepository()
        sender_reg = regions_repo.find(db, sender.city, direction="origin")
        # Payer defaults to sender (typical case: same person pays). Fall back
        # to origin-side lookup for the payer's city too so the field is not
        # silently empty.
        payer_source = sender  # simple default; extend when payer_* fields exist
        payer_reg = regions_repo.find(db, payer_source.city, direction="origin")

        def _region_str(row, fallback_city: str) -> str:
            if row is None:
                return fallback_city
            return f"{row.title}, {row.path}" if row.path else row.title

        # Map our tariff → Azimuth service_type (same mapping as create_invoice).
        tariff_lower = (order.tariff_name_snapshot or "").lower()
        shipment_lower = (order.shipment_type_snapshot or "").lower()
        service_type: int | None = None
        if "экспресс-пакет" in tariff_lower or "express-package" in tariff_lower:
            service_type = 3
        elif "экспресс" in tariff_lower or "express" in tariff_lower:
            service_type = 2
        elif "стандарт" in tariff_lower or "standard" in tariff_lower:
            service_type = 1
        elif "эконом" in tariff_lower or "economy" in tariff_lower:
            service_type = 1
        elif shipment_lower == "document":
            service_type = 3
        service_type = service_type or int(creds.get("service_type", 2))

        total_qty = sum(int(p.quantity) for p in order.packages) or 1

        pickup_time = (order.pickup_time_slot or "").strip()
        pickup_date = order.pickup_date.isoformat() if order.pickup_date else ""

        payload = {
            "sender_name": sender.full_name,
            "sender_tin": sender.tax_id or "",
            "sender_region": _region_str(sender_reg, sender.city),
            "sender_address": sender.address_line1,
            "sender_phone": sender.phone,
            "payer_name": payer_source.full_name,
            "payer_tin": payer_source.tax_id or "",
            "payer_region": _region_str(payer_reg, payer_source.city),
            "payer_address": payer_source.address_line1,
            "payer_phone": payer_source.phone,
            "service_type": service_type,
            "payer_type": int(creds.get("payer", 1)),
            "quantity": total_qty,
            "pickup_date": pickup_date,
            "pickup_time": pickup_time,
            "contact_person": order.pickup_contact_person or sender.full_name,
            "contact_person_phone": order.pickup_contact_phone or sender.phone,
            "payment": int(creds.get("payment_type", 2)),
            "notes": (recipient.comment if recipient else None) or "",
        }

        t0 = time.time()
        try:
            resp = AzimuthAPIClient().schedule_pickup(payload, creds)
        except Exception as exc:
            order.pickup_error = str(exc)[:1000]
            _integration_log.create(
                db, carrier_code="azimuth", direction="outbound",
                event_type="order_courier", order_id=order.id,
                payload=json.dumps(mask_pii(payload), ensure_ascii=False),
                duration_ms=int((time.time() - t0) * 1000),
                status="error", error_message=str(exc),
            )
            logger.warning(
                "Azimuth pickup failed for order=%s (invoice OK, admin can retry pickup): %s",
                order.id, exc,
            )
            return

        # Success — store an idempotency lock so a re-run of the dispatch job
        # cannot schedule a second pickup. Azimuth does not return their own
        # id in the docs, so we use a synthesised marker (timestamp) when the
        # body has no obvious id field.
        azimuth_id = ""
        if isinstance(resp, dict):
            inner = resp.get("data") if isinstance(resp.get("data"), dict) else resp
            azimuth_id = str(
                inner.get("id")
                or inner.get("courier_order_id")
                or inner.get("uuid")
                or ""
            )
        if not azimuth_id:
            # Azimuth did not return an id — synthesise a globally unique
            # marker so a double-click retry within the same second cannot
            # produce a colliding lock (prev impl used int(t0) which was 1-s
            # granular).
            azimuth_id = f"pickup-{order.id}-{uuid.uuid4().hex}"
        order.pickup_scheduled_azimuth_id = azimuth_id
        order.pickup_error = None
        _integration_log.create(
            db, carrier_code="azimuth", direction="outbound",
            event_type="order_courier", order_id=order.id,
            payload=json.dumps(mask_pii(payload), ensure_ascii=False),
            response=json.dumps(resp, ensure_ascii=False)[:2000],
            duration_ms=int((time.time() - t0) * 1000),
            status="success",
        )
        logger.info(
            "Azimuth pickup scheduled for order=%s azimuth_id=%s date=%s time=%s",
            order.id, azimuth_id, pickup_date, pickup_time,
        )

    def _dispatch_to_carrier(self, db: Session, order: OrderDraft) -> _DispatchOutcome:
        carrier_code = order.carrier_code_snapshot

        # ── Priority 1: carrier API via carrier-gateway ──────────────────────
        creds = CarrierAPICredentialsRepository().get_by_carrier_code(db, carrier_code)

        if creds and creds.is_active:
            logger.info("dispatch_worker: calling carrier-gateway for carrier=%s order=%s", carrier_code, order.id)
            api_creds = {
                "api_url": creds.api_url,
                "api_token": creds.api_token,
                **(creds.extra_config or {}),
            }
            # Authoritative source is the snapshot on the order itself
            # (populated at quote-select time in migration 042); fall back to
            # the linked RateQuote for orders created before the snapshot was
            # introduced. Reading the snapshot first also lets dispatch run
            # after the RateQuote row has been housekept.
            urgency_guid: str | None = order.urgency_guid_snapshot
            if not urgency_guid and order.selected_rate_quote_id:
                from app.modules.quotes.models import RateQuote as _RateQuote
                rq = db.get(_RateQuote, order.selected_rate_quote_id)
                if rq:
                    urgency_guid = rq.urgency_guid
            order_data = _build_api_order_data(order, creds=api_creds, urgency_guid=urgency_guid)
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
                    response=json.dumps({
                        "waybill_number": result.waybill_number,
                        "carrier_invoice_id": result.carrier_invoice_id,
                    }),
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
            return _DispatchOutcome(
                tracking_number=result.waybill_number,
                barcode=result.carrier_invoice_id,
            )

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
            # Generic webhook path: separate barcode field if the carrier sends one.
            body = resp.json() if resp.text else {}
            return _DispatchOutcome(
                tracking_number=body.get("tracking_number"),
                barcode=body.get("barcode") or body.get("carrier_invoice_id"),
            )
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


def _build_api_order_data(order: OrderDraft, creds: dict | None = None, urgency_guid: str | None = None) -> dict:
    """Нормализованные данные заказа для передачи в CarrierAPIClient."""
    sender = next((p for p in order.parties if p.role == "sender"), None)
    recipient = next((p for p in order.parties if p.role == "recipient"), None)

    sender_city = sender.city if sender else order.from_city_snapshot
    recipient_city = recipient.city if recipient else order.to_city_snapshot

    # For CSE, resolve Geography GUIDs from city names (non-fatal if unavailable)
    sender_geo_guid: str | None = None
    recipient_geo_guid: str | None = None
    if order.carrier_code_snapshot and order.carrier_code_snapshot.lower() == "cse" and creds:
        try:
            from app.modules.carriers.cse_geography import get_city_guid
            sender_geo_guid = get_city_guid(sender_city, creds)
            recipient_geo_guid = get_city_guid(recipient_city, creds)
        except Exception as exc:
            logger.debug("CSE geography GUID lookup failed (non-fatal): %s", exc)

    # CSE TakeDate + optional COD. Prior to this we let CSE default TakeDate
    # to `today 09:00`, which meant every dispatch reserved a courier visit
    # regardless of what the customer picked. Now the customer's chosen
    # pickup_date + pickup_time_slot flow through as a proper ISO datetime.
    #
    # pickup_time_slot is free-form ("10:00-14:00" | "утро" | ""). We parse
    # the first HH:MM out of it for TakeDate; the client can fall back to
    # 09:00 when the slot doesn't have a numeric prefix.
    cse_take_date: str | None = None
    if order.carrier_code_snapshot and order.carrier_code_snapshot.lower() == "cse" and order.pickup_date:
        import re as _re

        slot = (order.pickup_time_slot or "").strip()
        m = _re.match(r"(\d{1,2}):(\d{2})", slot)
        if m:
            hh = int(m.group(1))
            mm = int(m.group(2))
            time_part = f"{hh:02d}:{mm:02d}:00"
        else:
            time_part = "09:00:00"
        cse_take_date = f"{order.pickup_date.isoformat()}T{time_part}"

    cse_cod: dict | None = None
    if order.carrier_code_snapshot and order.carrier_code_snapshot.lower() == "cse":
        # Enable COD only when the customer opted in explicitly via a positive
        # amount on order.cod_amount. Other carriers ignore this field; CSE
        # picks it up in create_waybill (TypeOfPayer=1 + WayOfPayment mapping).
        amount = float(getattr(order, "cod_amount", 0) or 0)
        if amount > 0:
            cse_cod = {
                "amount": amount,
                "currency": getattr(order, "cod_currency", None) or "KZT",
                "payment_method": getattr(order, "cod_payment_method", None) or "cash",
            }

    return {
        "order_id": order.id,
        "order_reference": f"NOVEX-{order.id:06d}",
        "tariff_name": order.tariff_name_snapshot or "",
        "shipment_type": order.shipment_type_snapshot or "",
        "sender": {
            "full_name": sender.full_name if sender else "",
            "company": sender.company_name if sender else "",
            "phone": sender.phone if sender else "",
            "email": (sender.email if sender else "") or "",
            "city": sender_city,
            "address": sender.address_line1 if sender else "",
            "comment": (sender.comment if sender else "") or "",
            "tax_id": (sender.tax_id if sender else "") or "",
            **({"geography_guid": sender_geo_guid} if sender_geo_guid else {}),
            **({"pvz_guid": order.sender_pvz_guid} if order.sender_pvz_guid else {}),
        },
        "recipient": {
            "full_name": recipient.full_name if recipient else "",
            "company": recipient.company_name if recipient else "",
            "phone": recipient.phone if recipient else "",
            "email": (recipient.email if recipient else "") or "",
            "city": recipient_city,
            "address": recipient.address_line1 if recipient else "",
            "comment": (recipient.comment if recipient else "") or "",
            "tax_id": (recipient.tax_id if recipient else "") or "",
            **({"geography_guid": recipient_geo_guid} if recipient_geo_guid else {}),
            **({"urgency_guid": urgency_guid} if urgency_guid else {}),
            **({"pvz_guid": order.recipient_pvz_guid} if order.recipient_pvz_guid else {}),
        },
        "delivery_type": order.delivery_type,
        "packages": [
            {
                "weight_kg": float(p.weight_kg),
                "quantity": p.quantity,
                "description": p.description or "",
                "declared_value": float(p.declared_value) if p.declared_value else None,
                "width_cm": float(p.width_cm),
                "height_cm": float(p.height_cm),
                "depth_cm": float(p.depth_cm),
            }
            for p in order.packages
        ],
        # Declared value = sum of package.declared_value only. Never fall back to
        # price_snapshot (that's shipping cost, not goods value — carriers reject or
        # mis-tariff insurance if we mix them).
        "declared_value": sum(float(p.declared_value or 0) for p in order.packages),
        "currency": order.currency_snapshot,
        "fragile": order.fragile,
        "call_before_delivery": order.call_before_delivery,
        "insurance": order.insurance,
        # CSE-only extras — other clients ignore unknown keys.
        **({"take_date": cse_take_date} if cse_take_date else {}),
        **({"cod": cse_cod} if cse_cod else {}),
    }


def _save_waybill_document(
    db: Session,
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

        # Invalidate any stale Novex-generated label the user may have downloaded
        # before dispatch — the next GET /orders/{id}/label will serve the carrier's PDF.
        try:
            from app.core.redis import get_redis
            get_redis().delete(f"pdf:label:{order.id}")
        except Exception:
            pass
    except Exception as exc:
        logger.exception(
            "Failed to save waybill PDF (non-fatal) for order_id=%s waybill=%s: %s",
            order.id, waybill_number, exc,
        )


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
            "tax_id": (sender.tax_id if sender else "") or "",
        },
        "recipient": {
            "full_name": recipient.full_name if recipient else "",
            "phone": recipient.phone if recipient else "",
            "city": recipient.city if recipient else "",
            "address": recipient.address_line1 if recipient else "",
            "tax_id": (recipient.tax_id if recipient else "") or "",
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
        # Declared value = sum of package.declared_value only. Never fall back
        # to price_snapshot (that's shipping cost, not goods value — carriers
        # reject or mis-tariff insurance if we mix them). Mirrors the rule in
        # _build_api_order_data.
        "declared_value": sum(float(p.declared_value or 0) for p in order.packages),
        "currency": order.currency_snapshot,
        "additional_services": {
            "call_before_delivery": order.call_before_delivery,
            "insurance": order.insurance,
            "fragile": order.fragile,
        },
    }
