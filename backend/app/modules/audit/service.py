from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog
from app.modules.audit.repository import AuditLogRepository
from app.modules.identity.models import User

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, repo: AuditLogRepository | None = None) -> None:
        self.repo = repo or AuditLogRepository()

    def log(
        self,
        db: Session,
        *,
        actor: User,
        action: str,
        resource_type: str,
        resource_id: int | None = None,
        old_value: Any = None,
        new_value: Any = None,
    ) -> None:
        try:
            self.repo.create(
                db,
                actor_id=actor.id,
                actor_email=actor.email,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                old_value=json.dumps(old_value, ensure_ascii=False) if old_value is not None else None,
                new_value=json.dumps(new_value, ensure_ascii=False) if new_value is not None else None,
            )
        except Exception:
            logger.exception(
                "Audit log failed (non-fatal): action=%s actor_id=%s resource=%s/%s",
                action,
                actor.id,
                resource_type,
                resource_id,
            )

    def list_logs(
        self,
        db: Session,
        *,
        offset: int = 0,
        limit: int = 50,
        actor_id: int | None = None,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> tuple[Sequence[AuditLog], int]:
        return self.repo.list_all(
            db,
            offset=offset,
            limit=limit,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
        )
