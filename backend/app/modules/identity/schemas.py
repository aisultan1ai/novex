from __future__ import annotations

import re

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.modules.identity.models import BillingMode, CustomerType, RoleCode

# Known disposable / throwaway email domains
_DISPOSABLE_DOMAINS: frozenset[str] = frozenset({
    "ais.re", "mailinator.com", "guerrillamail.com", "guerrillamail.net",
    "guerrillamail.org", "guerrillamail.de", "guerrillamail.info",
    "sharklasers.com", "spam4.me", "trashmail.com", "trashmail.net",
    "trashmail.me", "trashmail.at", "trashmail.io", "tempmail.com",
    "temp-mail.org", "dispostable.com", "yopmail.com", "yopmail.fr",
    "cool.fr.nf", "jetable.fr.nf", "nospam.ze.tc", "nomail.xl.cx",
    "mega.zik.dj", "speed.1s.fr", "courriel.fr.nf", "moncourrier.fr.nf",
    "monemail.fr.nf", "monmail.fr.nf", "fakeinbox.com", "maildrop.cc",
    "mailnull.com", "spamgourmet.com", "spamgourmet.net", "spamgourmet.org",
    "throwam.com", "throwaway.email", "discard.email", "crapmail.org",
    "armyspy.com", "cuvox.de", "dayrep.com", "einrot.com", "fleckens.hu",
    "gustr.com", "jourrapide.com", "rhyta.com", "superrito.com",
    "teleworm.us", "10minutemail.com", "10minutemail.net", "10mail.org",
    "mailnesia.com", "mailnull.com", "spambog.com", "spambog.ru",
    "getnada.com", "filzmail.com", "binkmail.com", "bobmail.info",
    "chammy.info", "devnullmail.com", "dump-email.info",
})

_PHONE_RE = re.compile(r"^(\+?7|8)[0-9]{10}$")


def _validate_phone(value: str | None) -> str | None:
    if value is None:
        return None
    digits_only = re.sub(r"[\s\-\(\)]", "", value.strip())
    if not digits_only:
        return None
    if not _PHONE_RE.match(digits_only):
        raise ValueError(
            "Укажите номер телефона в формате +7XXXXXXXXXX или 8XXXXXXXXXX"
        )
    # Normalize to +7 format
    if digits_only.startswith("8"):
        digits_only = "+7" + digits_only[1:]
    elif digits_only.startswith("7"):
        digits_only = "+" + digits_only
    return digits_only


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    customer_type: CustomerType = CustomerType.INDIVIDUAL
    company_name: str | None = Field(default=None, max_length=255)
    billing_mode: BillingMode | None = None

    @field_validator("email")
    @classmethod
    def block_disposable_email(cls, value: str) -> str:
        domain = value.split("@")[-1].lower()
        if domain in _DISPOSABLE_DOMAINS:
            raise ValueError("Используйте постоянный email адрес")
        return value

    @field_validator("full_name", "company_name")
    @classmethod
    def strip_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return _validate_phone(value)

    @model_validator(mode="after")
    def validate_company_fields(self) -> RegisterRequest:
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
    customer_type: CustomerType | None = None
    company_name: str | None = None
    billing_mode: BillingMode | None = None
    carrier_id: int | None = None


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    company_name: str | None = Field(default=None, max_length=255)
    billing_mode: BillingMode | None = None

    @field_validator("full_name", "company_name")
    @classmethod
    def strip_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return _validate_phone(value)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    profile: ProfileResponse


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
