from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.db import get_async_db, get_db
from app.core.limiter import limiter
from app.modules.quotes.models import QuoteSession
from app.modules.quotes.schemas import (
    QuoteSelectionRequest,
    ShippingQuoteRequest,
    ShippingQuoteResponse,
)
from app.modules.quotes.service import QuotesService

router = APIRouter(prefix="/shipping", tags=["shipping"])
quotes_service = QuotesService()


def _validate_token(db: Session, quote_session_id: int, token: str | None) -> QuoteSession:
    session = db.get(QuoteSession, quote_session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Quote session not found")
    if session.public_token and token != session.public_token:
        raise HTTPException(status_code=403, detail="Invalid or missing quote token")
    if session.expires_at and session.expires_at < datetime.now(UTC).replace(tzinfo=None):
        raise HTTPException(status_code=410, detail="Quote session has expired")
    return session


@router.post(
    "/quote",
    response_model=ShippingQuoteResponse,
    status_code=200,
)
@limiter.limit("30/minute")
async def calculate_shipping_quote(
    request: Request,
    payload: ShippingQuoteRequest,
    db: AsyncSession = Depends(get_async_db),
) -> ShippingQuoteResponse:
    return await quotes_service.calculate_quotes(db, payload)


@router.get(
    "/quote/{quote_session_id}",
    response_model=ShippingQuoteResponse,
    status_code=200,
)
def get_shipping_quote(
    quote_session_id: int,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ShippingQuoteResponse:
    _validate_token(db, quote_session_id, token)
    return quotes_service.get_quote_session(db, quote_session_id)


@router.post(
    "/quote/{quote_session_id}/select",
    response_model=ShippingQuoteResponse,
    status_code=200,
)
def select_shipping_quote(
    quote_session_id: int,
    payload: QuoteSelectionRequest,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ShippingQuoteResponse:
    _validate_token(db, quote_session_id, token)
    return quotes_service.select_quote(
        db,
        quote_session_id=quote_session_id,
        payload=payload,
    )
