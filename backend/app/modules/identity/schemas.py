from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.modules.identity.models import BillingMode, CustomerType, RoleCode


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    customer_type: CustomerType = CustomerType.INDIVIDUAL
    company_name: str | None = Field(default=None, max_length=255)
    billing_mode: BillingMode | None = None

    @field_validator("full_name", "phone", "company_name")
    @classmethod
    def strip_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_company_fields(self) -> "RegisterRequest":
        if self.customer_type == CustomerType.COMPANY and not self.company_name:
            raise ValueError("company_name is required for company customer type")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str | None
    phone: str | None
    is_active: bool
    role: RoleCode


class ProfileResponse(BaseModel):
    user_id: int
    email: str
    full_name: str | None
    phone: str | None
    is_active: bool
    role: RoleCode
    customer_type: CustomerType
    company_name: str | None
    billing_mode: BillingMode


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    company_name: str | None = Field(default=None, max_length=255)
    billing_mode: BillingMode | None = None

    @field_validator("full_name", "phone", "company_name")
    @classmethod
    def strip_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    profile: ProfileResponse