from __future__ import annotations

from app.core.db import Base
from app.modules.identity.models import CustomerProfile, Role, User

__all__ = [
    "Base",
    "Role",
    "User",
    "CustomerProfile",
]