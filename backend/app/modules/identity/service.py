from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.modules.identity.models import BillingMode, CustomerType, RoleCode, User
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.schemas import (
    LoginRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    TokenResponse,
)


class IdentityService:
    def __init__(self, repository: IdentityRepository | None = None) -> None:
        self.repository = repository or IdentityRepository()

    def register_user(self, db: Session, payload: RegisterRequest) -> ProfileResponse:
        existing_user = self.repository.get_user_by_email(db, payload.email)
        if existing_user is not None:
            raise ValueError("User with this email already exists")

        customer_role = self.repository.ensure_role(
            db,
            RoleCode.CUSTOMER,
            "Customer",
        )

        user = self.repository.create_user(
            db,
            email=payload.email,
            password_hash=get_password_hash(payload.password),
            full_name=payload.full_name,
            phone=payload.phone,
            role=customer_role,
        )

        billing_mode = self._resolve_billing_mode(
            customer_type=payload.customer_type,
            explicit_mode=payload.billing_mode,
        )

        self.repository.create_customer_profile(
            db,
            user_id=user.id,
            customer_type=payload.customer_type,
            company_name=payload.company_name,
            billing_mode=billing_mode,
        )

        db.commit()

        created_user = self.repository.get_user_by_id(db, user.id)
        if created_user is None:
            raise ValueError("Failed to load created user")

        return self._build_profile_response(created_user)

    def authenticate_user(self, db: Session, payload: LoginRequest) -> TokenResponse:
        user = self.repository.get_user_by_email(db, payload.email)
        if user is None:
            raise ValueError("Invalid email or password")

        if not verify_password(payload.password, user.password_hash):
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("User is inactive")

        role_code = user.role.code.value if user.role else RoleCode.CUSTOMER.value

        token = create_access_token(
            {
                "sub": str(user.id),
                "email": user.email,
                "role": role_code,
            }
        )

        profile = self._build_profile_response(user)

        return TokenResponse(
            access_token=token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            profile=profile,
        )

    def get_profile(self, db: Session, user_id: int) -> ProfileResponse:
        user = self.repository.get_user_by_id(db, user_id)
        if user is None:
            raise ValueError("User not found")
        return self._build_profile_response(user)

    def update_profile(
        self,
        db: Session,
        *,
        user_id: int,
        payload: ProfileUpdateRequest,
    ) -> ProfileResponse:
        user = self.repository.get_user_by_id(db, user_id)
        if user is None:
            raise ValueError("User not found")

        profile = user.customer_profile
        if profile is None:
            raise ValueError("Customer profile not found")

        self.repository.update_user(
            db,
            user=user,
            full_name=payload.full_name,
            phone=payload.phone,
        )

        self.repository.update_customer_profile(
            db,
            profile=profile,
            company_name=payload.company_name,
            billing_mode=payload.billing_mode,
        )

        db.commit()

        updated_user = self.repository.get_user_by_id(db, user_id)
        if updated_user is None:
            raise ValueError("Failed to load updated user")

        return self._build_profile_response(updated_user)

    def _resolve_billing_mode(
        self,
        *,
        customer_type: CustomerType,
        explicit_mode: BillingMode | None,
    ) -> BillingMode:
        if explicit_mode is not None:
            return explicit_mode

        if customer_type == CustomerType.COMPANY:
            return BillingMode.POSTPAID

        return BillingMode.PREPAID

    def _build_profile_response(self, user: User) -> ProfileResponse:
        profile = user.customer_profile
        if profile is None:
            raise ValueError("Customer profile is missing")

        role_code = user.role.code if user.role else RoleCode.CUSTOMER

        return ProfileResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            is_active=user.is_active,
            role=role_code,
            customer_type=profile.customer_type,
            company_name=profile.company_name,
            billing_mode=profile.billing_mode,
        )