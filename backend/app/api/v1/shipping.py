from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.quotes.schemas import ShippingQuoteRequest, ShippingQuoteResponse
from app.modules.quotes.service import QuotesService

router = APIRouter(prefix="/shipping", tags=["shipping"])
quotes_service = QuotesService()


@router.post(
    "/quote",
    response_model=ShippingQuoteResponse,
    status_code=status.HTTP_200_OK,
)
def calculate_shipping_quote(
    payload: ShippingQuoteRequest,
    db: Session = Depends(get_db),
) -> ShippingQuoteResponse:
    try:
        return quotes_service.calculate_quotes(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc