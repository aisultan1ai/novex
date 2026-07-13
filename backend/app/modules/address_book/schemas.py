from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class AddressEntryCreate(BaseModel):
    label: str | None = Field(default=None, max_length=100)
    full_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=50)
    email: str | None = None
    company_name: str | None = None
    tax_id: str | None = Field(default=None, max_length=12)
    country: str = Field(min_length=2, max_length=2)
    city: str = Field(min_length=1, max_length=100)
    address_line1: str = Field(min_length=1, max_length=255)
    address_line2: str | None = None
    postal_code: str | None = None
    is_default: bool = False

    @field_validator("tax_id")
    @classmethod
    def _validate_tax_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if not cleaned.isdigit() or len(cleaned) != 12:
            raise ValueError("ИИН / БИН должен состоять ровно из 12 цифр")
        return cleaned


class AddressEntryResponse(BaseModel):
    id: int
    user_id: int
    label: str | None
    full_name: str
    phone: str
    email: str | None
    company_name: str | None
    tax_id: str | None
    country: str
    city: str
    address_line1: str
    address_line2: str | None
    postal_code: str | None
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}
