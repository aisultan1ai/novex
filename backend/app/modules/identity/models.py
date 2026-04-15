from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Enum as SqlEnum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [item.value for item in enum_cls]


class RoleCode(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    OPERATOR = "operator"


class CustomerType(str, Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"


class BillingMode(str, Enum):
    PREPAID = "prepaid"
    POSTPAID = "postpaid"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


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

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)

    role: Mapped["Role"] = relationship(back_populates="users")
    customer_profile: Mapped["CustomerProfile | None"] = relationship(
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
    billing_mode: Mapped[BillingMode] = mapped_column(
        SqlEnum(
            BillingMode,
            name="billing_mode_enum",
            values_callable=enum_values,
        ),
        nullable=False,
        default=BillingMode.PREPAID,
    )

    user: Mapped["User"] = relationship(back_populates="customer_profile")