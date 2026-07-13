from __future__ import annotations

import logging
from html import escape
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.config import get_settings
from app.core.email import send_email
from app.core.limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/partners", tags=["partners"])


class PartnerApplication(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=200)
    contact_name: str = Field(..., min_length=2, max_length=200)
    phone: str = Field(..., min_length=6, max_length=30)
    email: EmailStr
    cities: str | None = Field(default=None, max_length=500)
    integration_type: Literal["api", "manual", "unsure"] = "unsure"
    comment: str | None = Field(default=None, max_length=2000)
    consent: bool

    @field_validator("consent")
    @classmethod
    def _consent_true(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Требуется согласие на обработку персональных данных")
        return v

    @field_validator("phone")
    @classmethod
    def _phone_digits(cls, v: str) -> str:
        digits = "".join(ch for ch in v if ch.isdigit() or ch == "+")
        if len(digits) < 6:
            raise ValueError("Некорректный номер телефона")
        return v.strip()


_INTEGRATION_LABEL = {
    "api": "Есть API — готовы к автоматической интеграции",
    "manual": "Нет API — принимаем заказы вручную",
    "unsure": "Не уверены / нужна консультация",
}


def _admin_html(app: PartnerApplication) -> str:
    rows = [
        ("Компания", app.company_name),
        ("Контактное лицо", app.contact_name),
        ("Телефон", app.phone),
        ("Email", app.email),
        ("Города / регионы", app.cities or "—"),
        ("Тип интеграции", _INTEGRATION_LABEL.get(app.integration_type, app.integration_type)),
        ("Комментарий", app.comment or "—"),
    ]
    tr = "".join(
        f"<tr><td style='padding:6px 12px;background:#f8fafc;font-weight:600;color:#334155;'>{escape(label)}</td>"
        f"<td style='padding:6px 12px;color:#0f172a;'>{escape(str(value))}</td></tr>"
        for label, value in rows
    )
    return (
        "<div style='font-family:Inter,Arial,sans-serif;color:#0f172a;'>"
        "<h2 style='margin:0 0 12px;font-size:18px;'>Новая заявка на партнёрство</h2>"
        f"<table style='border-collapse:collapse;font-size:14px;'>{tr}</table>"
        "</div>"
    )


def _applicant_html(app: PartnerApplication) -> str:
    return (
        "<div style='font-family:Inter,Arial,sans-serif;color:#0f172a;line-height:1.55;'>"
        f"<p>Здравствуйте, {escape(app.contact_name)}!</p>"
        f"<p>Мы получили заявку от <b>{escape(app.company_name)}</b> "
        "на партнёрство с Novex. Свяжемся с вами в течение 2 рабочих дней "
        "по указанным контактам.</p>"
        "<p>Если у вас появятся вопросы, можно ответить на это письмо.</p>"
        "<p style='margin-top:24px;color:#64748b;font-size:13px;'>Novex Logistics</p>"
        "</div>"
    )


def _recipient_list(settings) -> list[str]:
    raw = (settings.partners_email or "").strip()
    if not raw:
        return []
    return [e.strip() for e in raw.split(",") if e.strip()]


@router.post("/apply", status_code=202, summary="Заявка на партнёрство")
@limiter.limit("3/hour")
def submit_partner_application(
    request: Request,
    payload: PartnerApplication,
) -> dict:
    """Public endpoint. Sends the application to ops (partners inbox) and an
    auto-reply to the applicant. No DB — deliberately kept lightweight so a
    misconfigured SMTP does not block the form; failures are logged and the
    endpoint still returns 202 so the applicant sees a success screen."""
    settings = get_settings()
    admin_recipients = _recipient_list(settings)

    if not admin_recipients:
        logger.error(
            "partners.apply: partners_email is empty — application from %s "
            "(%s) not delivered anywhere", payload.company_name, payload.email,
        )
        raise HTTPException(
            status_code=500,
            detail="Приём заявок временно недоступен. Свяжитесь с нами напрямую.",
        )

    subject_admin = f"Заявка на партнёрство: {payload.company_name}"
    admin_html = _admin_html(payload)
    for rcpt in admin_recipients:
        try:
            send_email(to=rcpt, subject=subject_admin, html=admin_html)
        except Exception:
            logger.exception("partners.apply: failed to email admin %s", rcpt)

    try:
        send_email(
            to=payload.email,
            subject="Мы получили вашу заявку — Novex",
            html=_applicant_html(payload),
        )
    except Exception:
        logger.exception(
            "partners.apply: auto-reply to %s failed (application still accepted)",
            payload.email,
        )

    logger.info(
        "partners.apply: accepted company=%s email=%s integration=%s",
        payload.company_name, payload.email, payload.integration_type,
    )
    return {"ok": True, "message": "Заявка принята"}
