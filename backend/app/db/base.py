from __future__ import annotations

from app.core.db import Base
from app.modules.identity.models import CustomerProfile, Role, User
from app.modules.quotes.models import QuoteSession, RateQuote

__all__ = [
    "Base",
    "Role",
    "User",
    "CustomerProfile",
    "QuoteSession",
    "RateQuote",
]