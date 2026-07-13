from __future__ import annotations

from enum import Enum, StrEnum

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [item.value for item in enum_cls]


class RoleCode(StrEnum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    OPERATOR = "operator"
    CARRIER = "carrier"


class CustomerType(StrEnum):
    INDIVIDUAL = "individual"
    COMPANY = "company"


class BillingMode(StrEnum):
    PREPAID = "prepaid"
    POSTPAID = "postpaid"


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[RoleCode] = mapped_column(
        SqlEnum(
            RoleCode,
            name="role_code_enum",
            values_callable=enum_values,
        ),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    users: Mapped[list[User]] = relationship(back_populates="role")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)

    role: Mapped[Role] = relationship(back_populates="users")
    customer_profile: Mapped[CustomerProfile | None] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    carrier_profile: Mapped[CarrierProfile | None] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class CustomerProfile(Base, TimestampMixin):
    __tablename__ = "customer_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    customer_type: Mapped[CustomerType] = mapped_column(
        SqlEnum(
            CustomerType,
            name="customer_type_enum",
            values_callable=enum_values,
        ),
        nullable=False,
        default=CustomerType.INDIVIDUAL,
    )
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # ИИН (physical) / БИН (company) — Kazakhstan tax id, 12 digits. Nullable
    # in DB so legacy rows survive; API enforces required on new records.
    tax_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    billing_mode: Mapped[BillingMode] = mapped_column(
        SqlEnum(
            BillingMode,
            name="billing_mode_enum",
            values_callable=enum_values,
        ),
        nullable=False,
        default=BillingMode.PREPAID,
    )

    user: Mapped[User] = relationship(back_populates="customer_profile")


class CarrierProfile(Base, TimestampMixin):
    __tablename__ = "carrier_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    carrier_id: Mapped[int] = mapped_column(
        ForeignKey("carriers.id"),
        nullable=False,
        index=True,
    )

    user: Mapped[User] = relationship(back_populates="carrier_profile")
