from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.core.storage import get_storage
from app.modules.documents.service import DocumentsService

router = APIRouter(tags=["documents"])
_service = DocumentsService()


@router.get(
    "/orders/{order_draft_id}/label",
    summary="Скачать накладную (PDF)",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF-накладная",
        }
    },
)
def download_label(
    order_draft_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Response:
    object_name, filename = _service.get_label(
        db,
        user_id=current_user_id,
        order_draft_id=order_draft_id,
    )
    internal_path = get_storage().get_presigned_internal_path(object_name)
    return Response(
        headers={
            "X-Accel-Redirect": internal_path,
            "Content-Type": "application/pdf",
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
    )
