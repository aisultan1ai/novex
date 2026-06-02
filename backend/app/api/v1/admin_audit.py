from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import require_admin
from app.modules.audit.service import AuditService

router = APIRouter(prefix="/admin/audit-logs", tags=["admin:audit"])
_audit_svc = AuditService()


@router.get("", summary="Журнал действий администраторов")
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    actor_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    offset = (page - 1) * size
    items, total = _audit_svc.list_logs(
        db,
        offset=offset,
        limit=size,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
    )
    pages = math.ceil(total / size) if total > 0 else 1
    return {
        "items": [
            {
                "id": log.id,
                "actor_id": log.actor_id,
                "actor_email": log.actor_email,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "created_at": log.created_at.isoformat(),
            }
            for log in items
        ],
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }
