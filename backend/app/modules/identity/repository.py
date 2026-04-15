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
            .options(joinedload(User.role), joinedload(User.customer_profile))
            .where(User.email == email)
        )
        return db.scalar(stmt)

    def get_user_by_id(self, db: Session, user_id: int) -> User | None:
        stmt = (
            select(User)
            .options(joinedload(User.role), joinedload(User.customer_profile))
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
    ) -> CustomerProfile:
        profile = CustomerProfile(
            user_id=user_id,
            customer_type=customer_type,
            company_name=company_name,
            billing_mode=billing_mode,
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
        user.full_name = full_name
        user.phone = phone
        db.add(user)
        db.flush()
        return user

    def update_customer_profile(
        self,
        db: Session,
        *,
        profile: CustomerProfile,
        company_name: str | None = None,
        billing_mode: BillingMode | None = None,
    ) -> CustomerProfile:
        profile.company_name = company_name
        if billing_mode is not None:
            profile.billing_mode = billing_mode
        db.add(profile)
        db.flush()
        return profile