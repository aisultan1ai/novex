from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.quotes.schemas import (
    QuoteSelectionRequest,
    ShippingQuoteRequest,
    ShippingQuoteResponse,
)
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


@router.get(
    "/quote/{quote_session_id}",
    response_model=ShippingQuoteResponse,
    status_code=status.HTTP_200_OK,
)
def get_shipping_quote(
    quote_session_id: int,
    db: Session = Depends(get_db),
) -> ShippingQuoteResponse:
    try:
        return quotes_service.get_quote_session(db, quote_session_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/quote/{quote_session_id}/select",
    response_model=ShippingQuoteResponse,
    status_code=status.HTTP_200_OK,
)
def select_shipping_quote(
    quote_session_id: int,
    payload: QuoteSelectionRequest,
    db: Session = Depends(get_db),
) -> ShippingQuoteResponse:
    try:
        return quotes_service.select_quote(
            db,
            quote_session_id=quote_session_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc