from __future__ import annotations

import logging
import secrets

from sqlalchemy.orm import Session

from app.core.email import send_email
from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.core.redis import get_redis

logger = logging.getLogger(__name__)
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.modules.identity.models import BillingMode, CustomerType, RoleCode, User
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)

_RESET_TTL = 3600  # 1 час


class IdentityService:
    def __init__(self, repository: IdentityRepository | None = None) -> None:
        self.repository = repository or IdentityRepository()

    def register_user(self, db: Session, payload: RegisterRequest) -> ProfileResponse:
        logger.info("Registering user: email=%s", payload.email)
        existing_user = self.repository.get_user_by_email(db, payload.email)
        if existing_user is not None:
            logger.warning("Registration conflict: email=%s already exists", payload.email)
            raise ConflictError("User with this email already exists")

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
            raise NotFoundError("Failed to load created user")

        logger.info("User registered: user_id=%s email=%s", created_user.id, created_user.email)
        return self._build_profile_response(created_user)

    def authenticate_user(self, db: Session, payload: LoginRequest) -> TokenResponse:
        logger.info("Login attempt: email=%s", payload.email)
        user = self.repository.get_user_by_email(db, payload.email)
        if user is None or not verify_password(payload.password, user.password_hash):
            logger.warning("Failed login attempt: email=%s", payload.email)
            raise UnauthorizedError("Invalid email or password")

        if not user.is_active:
            logger.warning("Login denied — inactive account: user_id=%s", user.id)
            raise UnauthorizedError("User account is inactive")

        role_code = user.role.code.value if user.role else RoleCode.CUSTOMER.value

        token = create_access_token(
            {
                "sub": str(user.id),
                "email": user.email,
                "role": role_code,
            }
        )

        profile = self._build_profile_response(user)
        logger.info("User authenticated: user_id=%s email=%s", user.id, user.email)

        return TokenResponse(
            access_token=token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            profile=profile,
        )

    def get_profile(self, db: Session, user_id: int) -> ProfileResponse:
        user = self.repository.get_user_by_id(db, user_id)
        if user is None:
            raise NotFoundError("User not found")
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
            raise NotFoundError("User not found")

        profile = user.customer_profile
        if profile is None:
            raise NotFoundError("Customer profile not found")

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
            raise NotFoundError("Failed to load updated user")

        return self._build_profile_response(updated_user)

    def forgot_password(self, db: Session, payload: ForgotPasswordRequest, frontend_url: str) -> None:
        user = self.repository.get_user_by_email(db, payload.email)
        if not user:
            # не раскрываем существование аккаунта
            return

        token = secrets.token_urlsafe(32)
        r = get_redis()
        r.setex(f"reset:{token}", _RESET_TTL, str(user.id))

        reset_link = f"{frontend_url}/reset-password?token={token}"
        send_email(
            to=user.email,
            subject="Сброс пароля — Novex",
            html=f"""
            <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
              <h2 style="color:#0f172a">Сброс пароля</h2>
              <p style="color:#475569">Вы запросили сброс пароля для аккаунта <b>{user.email}</b>.</p>
              <a href="{reset_link}"
                 style="display:inline-block;margin:24px 0;padding:12px 28px;background:#0f172a;color:#fff;
                        border-radius:10px;text-decoration:none;font-weight:600">
                Сбросить пароль
              </a>
              <p style="color:#94a3b8;font-size:13px">Ссылка действует 1 час. Если вы не запрашивали сброс — проигнорируйте это письмо.</p>
            </div>
            """,
        )
        logger.info("Токен сброса пароля создан: user_id=%s", user.id)

    def reset_password(self, db: Session, payload: ResetPasswordRequest) -> None:
        r = get_redis()
        user_id_str = r.get(f"reset:{payload.token}")
        if not user_id_str:
            raise UnauthorizedError("Ссылка недействительна или устарела")

        user = self.repository.get_user_by_id(db, int(user_id_str))
        if not user:
            raise NotFoundError("Пользователь не найден")

        user.password_hash = get_password_hash(payload.new_password)
        db.commit()

        r.delete(f"reset:{payload.token}")
        logger.info("Пароль сброшен: user_id=%s", user.id)

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
            raise NotFoundError("Customer profile is missing")

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
