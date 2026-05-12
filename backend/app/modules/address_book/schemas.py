from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AddressEntryCreate(BaseModel):
    label: str | None = Field(default=None, max_length=100)
    full_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=50)
    email: str | None = None
    company_name: str | None = None
    country: str = Field(min_length=2, max_length=2)
    city: str = Field(min_length=1, max_length=100)
    address_line1: str = Field(min_length=1, max_length=255)
    address_line2: str | None = None
    postal_code: str | None = None
    is_default: bool = False


class AddressEntryResponse(BaseModel):
    id: int
    user_id: int
    label: str | None
    full_name: str
    phone: str
    email: str | None
    company_name: str | None
    country: str
    city: str
    address_line1: str
    address_line2: str | None
    postal_code: str | None
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}
