from __future__ import annotations

import logging
import secrets
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.common.time_utils import utcnow
from app.core.email import send_email
from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.core.redis import get_redis
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
    get_token_version,
    verify_password,
)
from app.modules.identity.models import (
    BillingMode,
    CarrierProfile,
    CustomerType,
    RoleCode,
    User,
)
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)

logger = logging.getLogger(__name__)


class CreateCarrierAccountRequest(BaseModel):
    email: EmailStr
    full_name: str | None = None
    temp_password: str | None = None  # if omitted, a secure random password is generated


_RESET_TTL = 3600          # 1 час — forgot-password
_SETUP_LINK_TTL = 172_800  # 48 часов — первичная активация аккаунта перевозчика
_VERIFY_EMAIL_TTL = 86_400  # 24 часа — подтверждение email при регистрации
_VERIFY_RESEND_COOLDOWN = 60  # секунд между повторными отправками письма


class IdentityService:
    def __init__(self, repository: IdentityRepository | None = None) -> None:
        self.repository = repository or IdentityRepository()

    def register_user(
        self,
        db: Session,
        payload: RegisterRequest,
        frontend_url: str | None = None,
    ) -> ProfileResponse:
        logger.info("Registering user: email=%s", payload.email)
        existing_user = self.repository.get_user_by_email(db, payload.email)
        if existing_user is not None:
            logger.warning(
                "Registration conflict: email=%s already exists", payload.email
            )
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
            tax_id=payload.tax_id,
        )

        db.commit()

        created_user = self.repository.get_user_by_id(db, user.id)
        if created_user is None:
            raise NotFoundError("Failed to load created user")

        logger.info(
            "User registered: user_id=%s email=%s", created_user.id, created_user.email
        )

        # Send verification link. Non-fatal — a broken SMTP setup should not
        # break registration itself. The user can request a resend later.
        if frontend_url:
            try:
                self._send_verification_email(db, created_user, frontend_url)
            except Exception:
                logger.exception(
                    "Verification email send failed (non-fatal): user_id=%s",
                    created_user.id,
                )

        return self._build_profile_response(created_user)

    def _send_verification_email(self, db: Session, user: User, frontend_url: str) -> None:
        """Generate a one-time token, store it in Redis, send the email, and
        (only on success) record the send timestamp for resend cooldown.

        The timestamp is set AFTER `send_email` returns so that an SMTP outage
        does not lock the user out of a legitimate resend attempt.
        """
        import html as _html

        token = secrets.token_urlsafe(32)
        r = get_redis()
        r.setex(f"verify_email:{token}", _VERIFY_EMAIL_TTL, str(user.id))

        verify_link = f"{frontend_url.rstrip('/')}/verify-email?token={token}"
        safe_email = _html.escape(user.email)
        send_email(
            to=user.email,
            subject="Подтвердите email — Novex",
            html=f"""
            <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
              <h2 style="color:#0f172a">Подтвердите email</h2>
              <p style="color:#475569">
                Здравствуйте! Вы зарегистрировались на Novex как <b>{safe_email}</b>.<br>
                Нажмите кнопку ниже, чтобы подтвердить адрес и оформлять заказы.
              </p>
              <a href="{verify_link}"
                 style="display:inline-block;margin:24px 0;padding:12px 28px;background:#0f172a;color:#fff;
                        border-radius:10px;text-decoration:none;font-weight:600">
                Подтвердить аккаунт
              </a>
              <p style="color:#94a3b8;font-size:13px">
                Ссылка действует 24 часа. Если вы не регистрировались на Novex — просто проигнорируйте это письмо.
              </p>
            </div>
            """,
        )
        # Send succeeded — record the timestamp so the cooldown starts counting
        # only when a real email actually left our SMTP.
        user.email_verify_sent_at = utcnow()
        db.commit()
        logger.info("Verification email sent: user_id=%s", user.id)

    def verify_email(self, db: Session, token: str) -> None:
        """Validate the token from the email link and mark the account
        verified. Idempotent: verifying an already-verified account is a no-op."""
        r = get_redis()
        user_id_str = r.get(f"verify_email:{token}")
        if not user_id_str:
            raise UnauthorizedError("Ссылка недействительна или устарела")

        user = self.repository.get_user_by_id(db, int(user_id_str))  # type: ignore[arg-type]
        if not user:
            raise NotFoundError("Пользователь не найден")

        if user.email_verified_at is None:
            user.email_verified_at = utcnow()
            db.commit()
            logger.info("Email verified: user_id=%s", user.id)

        # Burn the token even if the account was already verified — prevents
        # link reuse across sessions or shared browsers.
        r.delete(f"verify_email:{token}")

    def resend_verification_email(
        self, db: Session, user_id: int, frontend_url: str
    ) -> None:
        """Re-issue a verification link. Rate-limited to _VERIFY_RESEND_COOLDOWN
        seconds per user so a stuck client can't spam our SMTP."""
        user = self.repository.get_user_by_id(db, user_id)
        if not user:
            raise NotFoundError("Пользователь не найден")
        if user.email_verified_at is not None:
            # Already verified — nothing to do, but don't error either.
            return

        if user.email_verify_sent_at is not None:
            elapsed = (utcnow() - user.email_verify_sent_at).total_seconds()
            if elapsed < _VERIFY_RESEND_COOLDOWN:
                wait = int(_VERIFY_RESEND_COOLDOWN - elapsed)
                raise ConflictError(
                    f"Подождите {wait} сек. перед повторной отправкой письма."
                )

        self._send_verification_email(db, user, frontend_url)

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
                "role": role_code,
                "ver": get_token_version(user.id),
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
            tax_id=payload.tax_id,
        )

        db.commit()

        updated_user = self.repository.get_user_by_id(db, user_id)
        if updated_user is None:
            raise NotFoundError("Failed to load updated user")

        return self._build_profile_response(updated_user)

    def forgot_password(
        self, db: Session, payload: ForgotPasswordRequest, frontend_url: str
    ) -> None:
        user = self.repository.get_user_by_email(db, payload.email)
        if not user:
            # не раскрываем существование аккаунта
            return

        import html as _html

        token = secrets.token_urlsafe(32)
        r = get_redis()
        r.setex(f"reset:{token}", _RESET_TTL, str(user.id))

        reset_link = f"{frontend_url}/reset-password?token={token}"
        safe_email = _html.escape(user.email)
        send_email(
            to=user.email,
            subject="Сброс пароля — Novex",
            html=f"""
            <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
              <h2 style="color:#0f172a">Сброс пароля</h2>
              <p style="color:#475569">Вы запросили сброс пароля для аккаунта <b>{safe_email}</b>.</p>
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

    def change_password(
        self, db: Session, user_id: int, payload: ChangePasswordRequest
    ) -> None:
        user = self.repository.get_user_by_id(db, user_id)
        if not user:
            raise NotFoundError("Пользователь не найден")
        if not verify_password(payload.current_password, user.password_hash):
            raise UnauthorizedError("Текущий пароль неверный")
        user.password_hash = get_password_hash(payload.new_password)
        db.commit()
        logger.info("Пароль изменён: user_id=%s", user_id)

    def reset_password(self, db: Session, payload: ResetPasswordRequest) -> None:
        r = get_redis()
        user_id_str = r.get(f"reset:{payload.token}")
        if not user_id_str:
            raise UnauthorizedError("Ссылка недействительна или устарела")

        user = self.repository.get_user_by_id(db, int(user_id_str))  # type: ignore[arg-type]
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

    def create_carrier_account(
        self,
        db: Session,
        *,
        carrier_id: int,
        carrier_name: str,
        payload: CreateCarrierAccountRequest,
        frontend_url: str,
    ) -> ProfileResponse:
        if self.repository.get_user_by_email(db, payload.email):
            raise ConflictError("Пользователь с таким email уже существует")

        carrier_role = self.repository.ensure_role(db, RoleCode.CARRIER, "Carrier")

        # Use provided temp_password or auto-generate — never transmitted in email
        initial_password = payload.temp_password or secrets.token_urlsafe(24)

        user = self.repository.create_user(
            db,
            email=payload.email,
            password_hash=get_password_hash(initial_password),
            full_name=payload.full_name or carrier_name,
            phone=None,
            role=carrier_role,
        )

        carrier_profile = CarrierProfile(user_id=user.id, carrier_id=carrier_id)
        db.add(carrier_profile)
        db.flush()

        db.commit()

        # Generate a one-time setup link so the carrier sets their own password.
        # Reuses the existing reset-password flow (same Redis key prefix, same endpoint).
        import html as _html

        setup_token = secrets.token_urlsafe(32)
        get_redis().setex(f"reset:{setup_token}", _SETUP_LINK_TTL, str(user.id))
        setup_link = f"{frontend_url}/reset-password?token={setup_token}"

        safe_email = _html.escape(payload.email)
        safe_carrier = _html.escape(carrier_name)
        send_email(
            to=payload.email,
            subject=f"Добро пожаловать в Novex — активируйте аккаунт {carrier_name}",
            html=f"""
            <div style="font-family:sans-serif;max-width:520px;margin:0 auto;padding:32px">
              <h2 style="color:#0f172a">Ваш аккаунт перевозчика создан</h2>
              <p style="color:#475569">
                Платформа Novex открыла для вас доступ как перевозчику <b>{safe_carrier}</b>.
              </p>
              <p style="color:#475569">Нажмите кнопку ниже чтобы установить пароль и начать работу:</p>
              <a href="{setup_link}"
                 style="display:inline-block;margin:24px 0;padding:12px 28px;background:#0f172a;color:#fff;
                        border-radius:10px;text-decoration:none;font-weight:600">
                Установить пароль
              </a>
              <p style="color:#475569;font-size:14px">
                Email для входа: <b>{safe_email}</b>
              </p>
              <p style="color:#94a3b8;font-size:13px">
                Ссылка активна 48 часов. Если она истекла — воспользуйтесь восстановлением пароля на странице входа.
              </p>
            </div>
            """,
        )

        created = self.repository.get_user_by_id(db, user.id)
        if not created:
            raise NotFoundError("Не удалось загрузить созданного пользователя")
        return self._build_profile_response(created)

    def _build_profile_response(self, user: User) -> ProfileResponse:
        role_code = user.role.code if user.role else RoleCode.CUSTOMER

        if role_code == RoleCode.CARRIER:
            cp = user.carrier_profile
            return ProfileResponse(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                phone=user.phone,
                is_active=user.is_active,
                email_verified=user.email_verified_at is not None,
                role=role_code,
                carrier_id=cp.carrier_id if cp else None,
            )

        if role_code in (RoleCode.ADMIN, RoleCode.OPERATOR):
            return ProfileResponse(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                phone=user.phone,
                is_active=user.is_active,
                email_verified=user.email_verified_at is not None,
                role=role_code,
            )

        profile = user.customer_profile
        if profile is None:
            raise NotFoundError("Customer profile is missing")

        return ProfileResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            is_active=user.is_active,
            email_verified=user.email_verified_at is not None,
            role=role_code,
            customer_type=profile.customer_type,
            company_name=profile.company_name,
            tax_id=profile.tax_id,
            billing_mode=profile.billing_mode,
        )
