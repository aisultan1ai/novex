"""CancellationRequestsService — единая точка обработки заявок на отмену.

Флоу:
    Клиент нажимает «Отменить» → request_cancellation()
        • Azimuth → сразу создаём заявку (API отмены нет)
        • CSE / Exline в allow_api-статусе → пробуем API
            – успех → _finalize_cancellation() (заказ становится cancelled,
              комиссия сторнируется, платежи → refund_pending)
            – отказ (карrier refused / сеть) → создаём заявку (fallback)
        • CSE / Exline в неподдерживаемом статусе → создаём заявку

    Перевозчик или админ подтверждает заявку → approve_by_* → _finalize_cancellation
    Админ жмёт «Повторить API-отмену» → retry_api_cancel
    Перевозчик/админ отклоняет → reject (заказ остаётся жив)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import insert as _sa_insert
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.time_utils import utcnow
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.modules.cancellations.models import CancellationRequest
from app.modules.cancellations.repository import CancellationRequestsRepository
from app.modules.cancellations.schemas import CancellationRequestResponse
from app.modules.commissions.service import CommissionsService

logger = logging.getLogger(__name__)


# ── Business rules — держим рядом с сервисом, чтобы поменять их в одном месте.

# Статусы, в которых клиент вправе инициировать отмену.
_CANCELLABLE_STATUSES: set[str] = {
    "paid",
    "dispatch_queued",
    "dispatch_failed",
    "pending_manual",
    "pending_manual_dispatch",
    "sent_to_carrier",
}

# У кого есть API отмены — только эти пробуем. Azimuth не в списке.
_CARRIERS_WITH_CANCEL_API: set[str] = {"cse", "exline"}

# В каких статусах у CSE/Exline имеет смысл пробовать API. За пределами этого
# набора сразу создаём заявку (например, в pending_manual_dispatch у нас ещё
# нет invoice_id — звонить в API нечем).
_API_ALLOWED_STATUSES: set[str] = {
    "paid",
    "sent_to_carrier",
}

# Backoff-график для авторетрая API-отмены. Первый элемент — задержка после
# первичного отказа (retry_count=0 → 30s), дальше как ответ на неудачу
# каждой следующей попытки. len(_RETRY_BACKOFF) = максимум попыток.
_RETRY_BACKOFF: list[timedelta] = [
    timedelta(seconds=30),
    timedelta(minutes=2),
    timedelta(minutes=10),
]
MAX_RETRIES = len(_RETRY_BACKOFF)


@dataclass
class CancellationOutcome:
    """Что вернуть роутеру после request_cancellation().

    kind:
        - "cancelled" — заказ уже в статусе cancelled, заявку создавать не
          пришлось (успешный API-путь).
        - "requested" — создали pending-заявку, ждём подтверждения.
    """

    kind: str
    request: CancellationRequestResponse | None


class CancellationRequestsService:
    def __init__(self, repo: CancellationRequestsRepository | None = None) -> None:
        self.repo = repo or CancellationRequestsRepository()

    # ─────────────────────────────────────────────────────────────────────
    # Public — client-initiated
    # ─────────────────────────────────────────────────────────────────────

    def request_cancellation(
        self,
        db: Session,
        *,
        user_id: int,
        order_id: int,
        reason: str,
    ) -> CancellationOutcome:
        from app.modules.orders.models import OrderDraft

        reason = self._validate_reason(reason)
        order = db.get(OrderDraft, order_id)
        if order is None:
            raise NotFoundError("Заказ не найден")
        if order.user_id != user_id:
            raise ForbiddenError("Заказ не принадлежит текущему пользователю")
        if order.status not in _CANCELLABLE_STATUSES:
            raise ValidationError(
                f"Отмена невозможна для статуса «{order.status}». "
                "Если посылка уже в пути, обратитесь в поддержку."
            )

        if self.repo.get_pending_for_order(db, order.id) is not None:
            raise ConflictError(
                "Заявка на отмену этого заказа уже отправлена и ожидает решения."
            )

        carrier_code = order.carrier_code_snapshot

        # Azimuth — API отмены нет, сразу создаём заявку.
        if carrier_code not in _CARRIERS_WITH_CANCEL_API:
            return self._create_request_and_notify(
                db,
                order=order,
                user_id=user_id,
                reason=reason,
                api_attempted=False,
                api_error=None,
            )

        # CSE / Exline: пробуем API только в подходящих статусах.
        if order.status not in _API_ALLOWED_STATUSES:
            return self._create_request_and_notify(
                db,
                order=order,
                user_id=user_id,
                reason=reason,
                api_attempted=False,
                api_error=None,
            )

        ok, err = self._try_api_cancel(db, order)
        if ok:
            # API успешно отменил — сразу закрываем заказ без заявки.
            self._finalize_cancellation(
                db,
                order=order,
                request=None,
                reason=reason,
                actor_user_id=user_id,
                source="customer_cancel_via_api",
            )
            db.commit()
            self._post_commit_notify_customer(order.id, order.user_id)
            return CancellationOutcome(kind="cancelled", request=None)

        # API отказал / сеть упала — fallback на заявку.
        return self._create_request_and_notify(
            db,
            order=order,
            user_id=user_id,
            reason=reason,
            api_attempted=True,
            api_error=err,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Public — resolution paths
    # ─────────────────────────────────────────────────────────────────────

    def approve_by_carrier(
        self,
        db: Session,
        *,
        request_id: int,
        carrier_user_id: int,
        carrier_code: str,
        comment: str | None = None,
    ) -> CancellationRequestResponse:
        req = self._get_pending_or_400(db, request_id)
        if req.carrier_code != carrier_code:
            raise ForbiddenError("Заявка относится к другому перевозчику")
        return self._finalize_and_close(
            db,
            req=req,
            actor_user_id=carrier_user_id,
            comment=comment,
            status="approved",
            source="carrier_approved",
        )

    def approve_by_admin(
        self,
        db: Session,
        *,
        request_id: int,
        admin_id: int,
        comment: str | None = None,
    ) -> CancellationRequestResponse:
        req = self._get_pending_or_400(db, request_id)
        return self._finalize_and_close(
            db,
            req=req,
            actor_user_id=admin_id,
            comment=comment,
            status="approved",
            source="admin_approved",
        )

    def retry_api_cancel(
        self,
        db: Session,
        *,
        request_id: int,
        admin_id: int,
    ) -> CancellationRequestResponse:
        from app.modules.orders.models import OrderDraft

        req = self._get_pending_or_400(db, request_id)
        if req.carrier_code not in _CARRIERS_WITH_CANCEL_API:
            raise ValidationError(
                f"У перевозчика «{req.carrier_code}» нет API отмены — используйте «Подтвердить вручную»."
            )
        order = db.get(OrderDraft, req.order_draft_id)
        if order is None:
            raise NotFoundError("Заказ не найден")
        if order.status not in _API_ALLOWED_STATUSES:
            raise ValidationError(
                f"API-отмена недоступна в статусе «{order.status}»."
            )

        ok, err = self._try_api_cancel(db, order)
        req.api_attempted = True
        if not ok:
            # Оставляем pending, обновляем ошибку. Ручной ретрай админа
            # НЕ инкрементирует retry_count и НЕ ставит next_retry_at —
            # админ явно управляет; авторетрай (worker) идёт отдельным путём.
            req.api_error = err
            db.commit()
            logger.info(
                "Cancellation retry failed: request_id=%s carrier=%s error=%s",
                req.id, req.carrier_code, err,
            )
            return CancellationRequestResponse.model_validate(req)

        # API согласился — сбрасываем ретрай-график и финализируем.
        req.next_retry_at = None
        return self._finalize_and_close(
            db,
            req=req,
            actor_user_id=admin_id,
            comment=None,
            status="api_cancelled",
            source="admin_retry_api",
        )

    def auto_retry_api_cancel(
        self,
        db: Session,
        *,
        request_id: int,
    ) -> str:
        """Автоматический ретрай, вызывается воркером. Отличается от
        retry_api_cancel тем, что нет актора-админа и есть backoff:
        каждая неудача бампит retry_count и назначает next_retry_at по
        _RETRY_BACKOFF; после MAX_RETRIES worker перестаёт трогать заявку.

        Возвращает статус результата: 'cancelled' | 'rescheduled' |
        'exhausted' | 'stale' — только для логов воркера.
        """
        from app.modules.orders.models import OrderDraft

        req = self.repo.get(db, request_id)
        if req is None or req.status != "pending":
            return "stale"
        # Гонка: между xreadgroup и обработкой заявку мог закрыть админ.
        if req.next_retry_at is None or req.next_retry_at > utcnow():
            return "stale"
        if req.carrier_code not in _CARRIERS_WITH_CANCEL_API:
            req.next_retry_at = None
            db.commit()
            return "stale"

        order = db.get(OrderDraft, req.order_draft_id)
        if order is None or order.status not in _API_ALLOWED_STATUSES:
            # Заказ ушёл дальше — авторетрай теряет смысл, но заявку не
            # трогаем: её либо закроет админ, либо она станет «протухшей».
            req.next_retry_at = None
            db.commit()
            return "stale"

        req.api_attempted = True
        ok, err = self._try_api_cancel(db, order)
        if ok:
            req.next_retry_at = None
            self._finalize_and_close(
                db,
                req=req,
                actor_user_id=req.requested_by_user_id,
                comment=None,
                status="api_cancelled",
                source="auto_retry_api",
            )
            logger.info(
                "Cancellation auto-retry succeeded: request_id=%s attempts=%s",
                req.id, req.retry_count + 1,
            )
            return "cancelled"

        req.api_error = err
        req.retry_count = (req.retry_count or 0) + 1
        if req.retry_count >= MAX_RETRIES:
            req.next_retry_at = None
            db.commit()
            logger.info(
                "Cancellation auto-retry exhausted: request_id=%s error=%s",
                req.id, err,
            )
            return "exhausted"

        # Backoff для next_retry_at берём по индексу, равному числу уже
        # сделанных попыток (retry_count).
        req.next_retry_at = utcnow() + _RETRY_BACKOFF[req.retry_count]
        db.commit()
        logger.info(
            "Cancellation auto-retry rescheduled: request_id=%s attempts=%s next=%s",
            req.id, req.retry_count, req.next_retry_at,
        )
        return "rescheduled"

    def reject(
        self,
        db: Session,
        *,
        request_id: int,
        actor_user_id: int,
        actor_is_admin: bool,
        actor_carrier_code: str | None,
        comment: str,
    ) -> CancellationRequestResponse:
        comment = (comment or "").strip()
        if len(comment) < 3:
            raise ValidationError("Причина отклонения — минимум 3 символа")
        if len(comment) > 500:
            raise ValidationError("Причина отклонения не должна превышать 500 символов")

        req = self._get_pending_or_400(db, request_id)
        if not actor_is_admin and req.carrier_code != actor_carrier_code:
            raise ForbiddenError("Заявка относится к другому перевозчику")

        req.status = "rejected"
        req.carrier_response = comment
        req.resolved_by_user_id = actor_user_id
        req.resolved_at = utcnow()
        db.commit()
        logger.info(
            "Cancellation rejected: request_id=%s order_id=%s by_admin=%s actor=%s",
            req.id, req.order_draft_id, actor_is_admin, actor_user_id,
        )

        self._notify_customer_rejected(req)
        return CancellationRequestResponse.model_validate(req)

    # ─────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────

    def _get_pending_or_400(self, db: Session, request_id: int) -> CancellationRequest:
        req = self.repo.get(db, request_id)
        if req is None:
            raise NotFoundError("Заявка на отмену не найдена")
        if req.status != "pending":
            raise ConflictError(
                f"Заявка уже в статусе «{req.status}» — повторное действие невозможно."
            )
        return req

    def _validate_reason(self, reason: str) -> str:
        reason = (reason or "").strip()
        if len(reason) < 3:
            raise ValidationError("Причина отмены должна содержать минимум 3 символа")
        if len(reason) > 500:
            raise ValidationError("Причина отмены не должна превышать 500 символов")
        return reason

    def _create_request_and_notify(
        self,
        db: Session,
        *,
        order,
        user_id: int,
        reason: str,
        api_attempted: bool,
        api_error: str | None,
    ) -> CancellationOutcome:
        req = self.repo.create(
            db,
            order_draft_id=order.id,
            requested_by_user_id=user_id,
            carrier_code=order.carrier_code_snapshot,
            reason=reason,
            api_attempted=api_attempted,
            api_error=api_error,
            status="pending",
        )
        # Если пришли сюда после API-отказа у CSE/Exline — планируем
        # автоматический ретрай (Exline «ожидает синхронизации» обычно
        # проходит за пару минут; попробуем без вмешательства админа).
        if api_attempted and order.carrier_code_snapshot in _CARRIERS_WITH_CANCEL_API:
            req.next_retry_at = utcnow() + _RETRY_BACKOFF[0]
        db.commit()

        # Post-commit: уведомления не должны откатывать создание заявки.
        try:
            self._notify_on_creation(req_id=req.id, order_id=order.id)
        except Exception:
            logger.exception(
                "Cancellation notify-on-creation failed request_id=%s (non-fatal)",
                req.id,
            )

        logger.info(
            "Cancellation requested: request_id=%s order_id=%s carrier=%s "
            "api_attempted=%s api_error=%s",
            req.id, order.id, order.carrier_code_snapshot, api_attempted, api_error,
        )
        return CancellationOutcome(
            kind="requested",
            request=CancellationRequestResponse.model_validate(req),
        )

    def _try_api_cancel(self, db: Session, order) -> tuple[bool, str | None]:
        """Return (ok, error_message). ok=False means either the API refused
        or the network failed — caller decides between finalize and fallback."""
        from app.core.carrier_gateway_client import get_gateway_client
        from app.modules.carriers.api_credentials import (
            CarrierAPICredentialsRepository,
        )
        from app.modules.shipments.models import Shipment

        shipment = db.scalar(
            select(Shipment).where(Shipment.order_draft_id == order.id)
        )
        invoice_id = None
        if shipment:
            invoice_id = shipment.carrier_tracking_number or shipment.tracking_number
        if not invoice_id:
            return False, "invoice_id_missing"

        creds = CarrierAPICredentialsRepository().get_by_carrier_code(
            db, order.carrier_code_snapshot
        )
        if not creds or not creds.is_active:
            return False, "no_active_credentials"
        api_creds = {
            "api_url": creds.api_url,
            "api_token": creds.api_token,
            **(creds.extra_config or {}),
        }
        try:
            ok = get_gateway_client().cancel_invoice(
                order.carrier_code_snapshot, invoice_id, api_creds
            )
        except Exception as exc:
            logger.warning(
                "Carrier API cancel raised: order_id=%s carrier=%s error=%s",
                order.id, order.carrier_code_snapshot, exc,
            )
            return False, str(exc)[:1000]
        if not ok:
            return False, "carrier_refused"
        return True, None

    def _finalize_and_close(
        self,
        db: Session,
        *,
        req: CancellationRequest,
        actor_user_id: int,
        comment: str | None,
        status: str,  # "approved" | "api_cancelled"
        source: str,
    ) -> CancellationRequestResponse:
        from app.modules.orders.models import OrderDraft

        order = db.get(OrderDraft, req.order_draft_id)
        if order is None:
            raise NotFoundError("Заказ не найден")

        # Между созданием заявки и её обработкой заказ мог уйти в статус, из
        # которого cancel уже невозможен (delivered, returned и т.п.). Раньше
        # мы бросали 409 — операция падала у перевозчика/админа, а клиент даже
        # не узнавал, что его заявка застряла. Теперь заявку автоматически
        # закрываем как rejected и явно уведомляем клиента — заказ живёт
        # своей жизнью, пользователь не остаётся в подвешенном состоянии.
        if order.status not in _CANCELLABLE_STATUSES and order.status != "cancelled":
            auto_reason = (
                f"Заказ уже в статусе «{order.status}» — отмена больше невозможна."
            )
            req.status = "rejected"
            req.carrier_response = auto_reason
            req.resolved_by_user_id = actor_user_id
            req.resolved_at = utcnow()
            req.next_retry_at = None
            db.commit()
            self._notify_customer_rejected(req)
            logger.info(
                "Cancellation auto-rejected — order moved on: request_id=%s order_id=%s order_status=%s",
                req.id, order.id, order.status,
            )
            raise ConflictError(auto_reason)

        if order.status != "cancelled":
            self._finalize_cancellation(
                db,
                order=order,
                request=req,
                reason=req.reason,
                actor_user_id=actor_user_id,
                source=source,
            )
        # Если заказ уже cancelled (крайний край: параллельный поток закрыл
        # его), просто закрываем заявку — операция идемпотентна.

        req.status = status
        req.carrier_response = (comment or "").strip() or None
        req.resolved_by_user_id = actor_user_id
        req.resolved_at = utcnow()
        db.commit()

        self._post_commit_notify_customer(order.id, order.user_id)

        logger.info(
            "Cancellation finalized: request_id=%s order_id=%s status=%s actor=%s",
            req.id, req.order_draft_id, status, actor_user_id,
        )
        return CancellationRequestResponse.model_validate(req)

    def _finalize_cancellation(
        self,
        db: Session,
        *,
        order,
        request: CancellationRequest | None,
        reason: str,
        actor_user_id: int,
        source: str,
    ) -> None:
        """Переводит заказ в cancelled + история + tracking event + сторно
        комиссии + refund_pending на платежах + уведомление админам.

        НЕ коммитит — вызывающий обязан сделать db.commit().
        """
        from sqlalchemy import select as _select

        from app.common.status_machine import can_transition
        from app.modules.dispatch.models import (
            DispatchJob,
            DispatchJobStatus,
            OrderStatusHistory,
        )
        from app.modules.identity.models import Role, RoleCode, User
        from app.modules.notifications.models import Notification as _Notification
        from app.modules.payments.transaction_models import (
            PaymentStatusHistory,
            PaymentTransaction,
            TxStatus,
        )
        from app.modules.tracking.models import TrackingEvent

        old_status = order.status
        if not can_transition(old_status, "cancelled"):
            raise ValidationError(
                f"Переход из статуса «{old_status}» в «cancelled» не разрешён"
            )

        # 1) Гасим очередь диспатча — иначе воркер может выстрелить после отмены.
        if old_status in (
            "dispatch_queued",
            "dispatch_failed",
            "pending_manual",
            "pending_manual_dispatch",
        ):
            active_jobs = db.scalars(
                _select(DispatchJob).where(
                    DispatchJob.order_id == order.id,
                    DispatchJob.status.in_(
                        [DispatchJobStatus.QUEUED, DispatchJobStatus.FAILED]
                    ),
                )
            ).all()
            for job in active_jobs:
                job.status = DispatchJobStatus.CANCELLED

        # 2) Флип статуса + история + tracking event.
        order.status = "cancelled"
        db.add(OrderStatusHistory(
            order_id=order.id,
            old_status=old_status,
            new_status="cancelled",
            changed_by_user_id=actor_user_id,
            source=source,
            comment=reason,
        ))
        db.add(TrackingEvent(
            order_draft_id=order.id,
            status="cancelled",
            description=f"Заказ отменён: {reason}",
        ))

        # 3) Сторно комиссии — идемпотентно (не найдёт active → no-op).
        CommissionsService().reverse_for_order(
            db,
            order.id,
            reason=f"{source}: {reason}",
        )

        # 4) Платежи → refund_pending.
        paid_txs = db.scalars(
            _select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.status == TxStatus.PAID,
            )
        ).all()
        for tx in paid_txs:
            db.add(PaymentStatusHistory(
                payment_id=tx.id,
                old_status=(
                    tx.status.value if hasattr(tx.status, "value") else str(tx.status)
                ),
                new_status=TxStatus.REFUND_PENDING.value,
                changed_by_user_id=actor_user_id,
                comment=f"Отмена: {reason}",
            ))
            tx.status = TxStatus.REFUND_PENDING

        # 5) In-app для админов — batch INSERT, чтобы не N запросов.
        admin_ids = db.scalars(
            _select(User.id).join(User.role).where(
                Role.code == RoleCode.ADMIN, User.is_active.is_(True)
            )
        ).all()
        if admin_ids:
            title = (
                f"Заказ #{order.id} отменён"
                if request is None
                else f"Заявка на отмену #{request.id} подтверждена"
            )
            body = (
                f"Причина: {reason}. "
                + ("Требуется оформить возврат средств." if paid_txs
                   else "Возврат средств не требуется.")
            )
            db.execute(
                _sa_insert(_Notification),
                [
                    {
                        "user_id": aid,
                        "type": "order_cancelled",
                        "title": title,
                        "body": body,
                        "is_read": False,
                    }
                    for aid in admin_ids
                ],
            )

    # ─────────────────────────────────────────────────────────────────────
    # Notifications (in-app + email)
    # ─────────────────────────────────────────────────────────────────────

    def _notify_on_creation(self, *, req_id: int, order_id: int) -> None:
        """Открываем свою сессию — уведомления идут ПОСЛЕ commit-а заявки,
        и внешний scope мог быть уже закрыт. Ошибки не пробрасываем."""
        from app.core.db import SessionLocal
        from app.modules.cancellations.notifications import (
            notify_cancellation_created,
        )

        with SessionLocal() as db:
            req = self.repo.get(db, req_id)
            if req is None:
                return
            notify_cancellation_created(db, req=req, order_id=order_id)

            from app.modules.notifications.staff import notify_staff
            notify_staff(
                db, event="cancellation_request", order_id=order_id,
                payload={"reason": req.reason or ""},
            )

    def _post_commit_notify_customer(self, order_id: int, user_id: int) -> None:
        """Уведомление клиенту про переход в cancelled — тем же путём, что и
        обычная смена статуса заказа."""
        from app.core.db import SessionLocal
        from app.modules.notifications.service import NotificationsService

        try:
            with SessionLocal() as db:
                NotificationsService().notify_order_status(
                    db, user_id=user_id, order_id=order_id, status="cancelled"
                )
                db.commit()
        except Exception:
            logger.exception(
                "post_commit_notify_customer failed order_id=%s user_id=%s (non-fatal)",
                order_id, user_id,
            )

    def _notify_customer_rejected(self, req: CancellationRequest) -> None:
        from app.core.db import SessionLocal
        from app.modules.cancellations.notifications import (
            notify_cancellation_rejected,
        )

        try:
            with SessionLocal() as db:
                notify_cancellation_rejected(db, req=req)
        except Exception:
            logger.exception(
                "notify_customer_rejected failed request_id=%s (non-fatal)", req.id
            )
