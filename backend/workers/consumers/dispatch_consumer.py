from __future__ import annotations

import logging
import socket
from threading import Event

from app.core.redis import get_redis
from app.core.request_context import bind_request_id
from app.core.streams import GROUP_DISPATCH, REQUEST_ID_FIELD, STREAM_DISPATCH

logger = logging.getLogger(__name__)

_CONSUMER_NAME = f"dispatch-{socket.gethostname()}"


def run(stop_event: Event) -> None:
    r = get_redis()
    logger.info("Dispatch consumer started (group=%s consumer=%s)", GROUP_DISPATCH, _CONSUMER_NAME)
    _recover_pending(r)

    while not stop_event.is_set():
        try:
            entries = r.xreadgroup(
                GROUP_DISPATCH,
                _CONSUMER_NAME,
                {STREAM_DISPATCH: ">"},
                count=5,
                block=5000,
            )
        except Exception:
            logger.exception("Dispatch consumer: xreadgroup error, retrying in 2s")
            stop_event.wait(2)
            continue

        if not entries:
            continue

        for _, messages in entries:  # type: ignore[union-attr]
            for msg_id, data in messages:
                with bind_request_id(data.get(REQUEST_ID_FIELD)):
                    try:
                        _process(data)
                        r.xack(STREAM_DISPATCH, GROUP_DISPATCH, msg_id)
                    except Exception:
                        logger.exception("Dispatch consumer: msg %s failed, left in PEL for recovery", msg_id)


def _recover_pending(r) -> None:
    entries = r.xreadgroup(GROUP_DISPATCH, _CONSUMER_NAME, {STREAM_DISPATCH: "0-0"}, count=100)
    if not entries:
        return
    for _, messages in entries:
        for msg_id, data in messages:
            with bind_request_id(data.get(REQUEST_ID_FIELD)):
                try:
                    _process(data)
                    r.xack(STREAM_DISPATCH, GROUP_DISPATCH, msg_id)
                except Exception:
                    logger.exception("Dispatch consumer: pending msg %s failed, left in PEL for recovery", msg_id)


def _process(data: dict) -> None:
    from app.core.db import SessionLocal
    from app.modules.dispatch.models import DispatchJob, DispatchJobStatus
    from app.modules.dispatch.service import DispatchWorker

    job_id = int(data["dispatch_job_id"])

    with SessionLocal() as db:
        job = db.get(DispatchJob, job_id)
        if not job:
            logger.error("Dispatch consumer: job %d not found in DB", job_id)
            return
        if job.status != DispatchJobStatus.QUEUED:
            logger.info("Dispatch consumer: job %d already in status %s, skipping", job_id, job.status)
            return

        DispatchWorker().process_job(db, job)
