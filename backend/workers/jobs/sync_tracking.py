from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.modules.carriers.polling.scheduler import poll_all_active_shipments

logger = logging.getLogger(__name__)


def run(db: Session) -> None:
    poll_all_active_shipments(db)
