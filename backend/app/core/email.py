from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_email(*, to: str, subject: str, html: str) -> None:
    settings = get_settings()

    if not settings.smtp_host or not settings.smtp_user:
        logger.warning(
            "SMTP не настроен — письмо не отправлено. To: %s | Subject: %s", to, subject
        )
        return

    # Envelope-from stays a bare address — most SMTP servers reject a MAIL FROM
    # command that carries a display name. The header From: gets the pretty
    # "Name <addr>" via formataddr, which handles RFC 2047 encoding for
    # non-ASCII display names (Cyrillic works out of the box).
    from_addr = settings.smtp_from or settings.smtp_user
    from_name = settings.smtp_from_name or "Novex"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, from_addr))
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))

    # Port 465 = SMTPS (implicit SSL from the handshake, use SMTP_SSL).
    # Port 587 / 25 = plain SMTP with optional STARTTLS upgrade.
    use_ssl = settings.smtp_port == 465
    try:
        if use_ssl:
            server_ctx = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10)
        else:
            server_ctx = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
        with server_ctx as server:
            server.ehlo()
            if not use_ssl and settings.smtp_tls:
                server.starttls()
                server.ehlo()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(from_addr, [to], msg.as_string())
        logger.info("Письмо отправлено: %s", to)
    except Exception:
        logger.exception("Ошибка отправки письма на %s", to)
        raise
