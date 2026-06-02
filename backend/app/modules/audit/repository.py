from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog


class AuditLogRepository:
    def create(
        self,
        db: Session,
        *,
        actor_id: int | None,
        actor_email: str,
        action: str,
        resource_type: str,
        resource_id: int | None = None,
        old_value: str | None = None,
        new_value: str | None = None,
    ) -> AuditLog:
        log = AuditLog(
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value,
            new_value=new_value,
        )
        db.add(log)
        return log

    def list_all(
        self,
        db: Session,
        *,
        offset: int = 0,
        limit: int = 50,
        actor_id: int | None = None,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> tuple[Sequence[AuditLog], int]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        if actor_id is not None:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        if resource_type is not None:
            stmt = stmt.where(AuditLog.resource_type == resource_type)

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = db.scalars(stmt.offset(offset).limit(limit)).all()
        return items, total
