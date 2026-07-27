from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.modules.identity.models import (
    BillingMode,
    CustomerProfile,
    CustomerType,
    Role,
    RoleCode,
    User,
)


class IdentityRepository:
    def get_role_by_code(self, db: Session, code: RoleCode) -> Role | None:
        stmt = select(Role).where(Role.code == code)
        return db.scalar(stmt)

    def ensure_role(self, db: Session, code: RoleCode, name: str) -> Role:
        existing_role = self.get_role_by_code(db, code)
        if existing_role:
            return existing_role

        role = Role(code=code, name=name)
        db.add(role)
        db.flush()
        return role

    def get_user_by_email(self, db: Session, email: str) -> User | None:
        stmt = (
            select(User)
            .options(
                joinedload(User.role),
                joinedload(User.customer_profile),
                joinedload(User.carrier_profile),
            )
            .where(User.email == email)
        )
        return db.scalar(stmt)

    def get_user_by_id(self, db: Session, user_id: int) -> User | None:
        stmt = (
            select(User)
            .options(
                joinedload(User.role),
                joinedload(User.customer_profile),
                joinedload(User.carrier_profile),
            )
            .where(User.id == user_id)
        )
        return db.scalar(stmt)

    def create_user(
        self,
        db: Session,
        *,
        email: str,
        password_hash: str,
        full_name: str | None,
        phone: str | None,
        role: Role,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            phone=phone,
            role_id=role.id,
            is_active=True,
        )
        db.add(user)
        db.flush()
        return user

    def create_customer_profile(
        self,
        db: Session,
        *,
        user_id: int,
        customer_type: CustomerType,
        company_name: str | None,
        billing_mode: BillingMode,
        tax_id: str | None = None,
    ) -> CustomerProfile:
        profile = CustomerProfile(
            user_id=user_id,
            customer_type=customer_type,
            company_name=company_name,
            billing_mode=billing_mode,
            tax_id=tax_id,
        )
        db.add(profile)
        db.flush()
        return profile

    def update_user(
        self,
        db: Session,
        *,
        user: User,
        full_name: str | None = None,
        phone: str | None = None,
    ) -> User:
        if full_name is not None:
            user.full_name = full_name
        if phone is not None:
            user.phone = phone
        db.add(user)
        db.flush()
        return user

    def update_customer_profile(
        self,
        db: Session,
        *,
        profile: CustomerProfile,
        fields: dict,
    ) -> CustomerProfile:
        # Пишем только те поля, которые клиент реально прислал (сервис уже
        # отфильтровал через model_dump(exclude_unset=True)). Присвоение None
        # трактуется как "явно очистить" — differs от "поле не пришло".
        allowed = {"company_name", "tax_id", "billing_mode"}
        for key, value in fields.items():
            if key in allowed:
                setattr(profile, key, value)
        db.add(profile)
        db.flush()
        return profile
