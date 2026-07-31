"""Автоматический ретрай API-отмены заказа.

Основной кейс — Exline «ожидает синхронизации» (error=54): create_invoice
только что прошёл, а cancel в первые минуты возвращает ошибку. За пару
итераций backoff'а (30s / 2m / 10m) синхронизация обычно завершается и
cancel проходит без вмешательства админа.

Идемпотентность: на каждой итерации Redis-лок гарантирует одну активную
копию по кластеру. Внутри service.auto_retry_api_cancel() каждая заявка
обрабатывается транзакционно; после MAX_RETRIES заявка остаётся pending
с next_retry_at=NULL — админ решает вручную.
"""

from __future__ import annotations

import logging
from collections import Counter

from sqlalchemy.orm import Session

from app.common.time_utils import utcnow
from app.core.redis import get_redis
from app.modules.cancellations.repository import CancellationRequestsRepository
from app.modules.cancellations.service import CancellationRequestsService

logger = logging.getLogger(__name__)

_LOCK_KEY = "lock:retry_cancellations"
_LOCK_TTL = 60  # sec — < job interval

_repo = CancellationRequestsRepository()
_service = CancellationRequestsService()


def run(db: Session) -> None:
    r = get_redis()
    if not r.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL):
        logger.debug("retry_cancellations: skipped — another replica holds the lock")
        return
    try:
        _run(db)
    finally:
        r.delete(_LOCK_KEY)


def _run(db: Session) -> None:
    now = utcnow()
    due = _repo.list_due_for_retry(db, now=now, limit=50)
    if not due:
        return

    stats: Counter[str] = Counter()
    for req in due:
        try:
            outcome = _service.auto_retry_api_cancel(db, request_id=req.id)
        except Exception:
            db.rollback()
            logger.exception(
                "retry_cancellations: unexpected error on request_id=%s", req.id
            )
            stats["error"] += 1
            continue
        stats[outcome] += 1

    logger.info(
        "retry_cancellations tick: due=%d cancelled=%d rescheduled=%d exhausted=%d stale=%d errors=%d",
        len(due),
        stats.get("cancelled", 0),
        stats.get("rescheduled", 0),
        stats.get("exhausted", 0),
        stats.get("stale", 0),
        stats.get("error", 0),
    )
