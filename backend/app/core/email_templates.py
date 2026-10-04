from __future__ import annotations

import html as _html

from app.core.config import get_settings

_BASE_STYLE = """
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  max-width: 520px;
  margin: 0 auto;
  padding: 40px 32px;
  background: #ffffff;
"""

_HEADER_STYLE = "color: #0f172a; font-size: 22px; font-weight: 700; margin: 0 0 8px;"
_BODY_STYLE = "color: #475569; font-size: 15px; line-height: 1.6; margin: 0 0 24px;"
_FOOTER_STYLE = "color: #94a3b8; font-size: 12px; margin-top: 32px; border-top: 1px solid #e2e8f0; padding-top: 16px;"
_BTN_STYLE = (
    "display: inline-block; padding: 12px 28px; background: #0f172a; color: #ffffff;"
    " border-radius: 10px; text-decoration: none; font-weight: 600; font-size: 14px; margin-bottom: 24px;"
)
_BADGE_GREEN = "display:inline-block;padding:4px 12px;background:#dcfce7;color:#166534;border-radius:20px;font-size:13px;font-weight:600;margin-bottom:20px;"
_BADGE_RED = "display:inline-block;padding:4px 12px;background:#fee2e2;color:#991b1b;border-radius:20px;font-size:13px;font-weight:600;margin-bottom:20px;"
_BADGE_BLUE = "display:inline-block;padding:4px 12px;background:#dbeafe;color:#1e40af;border-radius:20px;font-size:13px;font-weight:600;margin-bottom:20px;"
_BADGE_GRAY = "display:inline-block;padding:4px 12px;background:#f1f5f9;color:#475569;border-radius:20px;font-size:13px;font-weight:600;margin-bottom:20px;"


def _wrap(body_inner: str) -> str:
    return f'<div style="{_BASE_STYLE}">{body_inner}<p style="{_FOOTER_STYLE}">Novex - агрегатор курьерских услуг. Если у вас есть вопросы, ответьте на это письмо.</p></div>'


def _order_link(order_id: int) -> str:
    url = get_settings().frontend_url
    return f"{url}/dashboard/orders/{order_id}"


def _cta(order_id: int, label: str) -> str:
    return f'<a href="{_order_link(order_id)}" style="{_BTN_STYLE}">{label}</a>'


def _greeting(user_name: str | None) -> str:
    # Escape the user-supplied name — full_name comes from the customer profile
    # and can contain HTML control characters that would otherwise inject markup.
    name = _html.escape(user_name) if user_name else "Клиент"
    return f"Здравствуйте, {name}!"


# ── templates ──────────────────────────────────────────────────────────────

def _tpl_payment_under_review(order_id: int, user_name: str | None) -> tuple[str, str]:
    subject = f"Чек получен - Заказ #{order_id} на проверке"
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">{_greeting(user_name)}</h2>
      <span style="{_BADGE_BLUE}">Чек на проверке</span>
      <p style="{_BODY_STYLE}">
        Мы получили ваш чек об оплате по заказу <b>#{order_id}</b>.<br>
        Наши менеджеры проверят его в течение рабочего дня и подтвердят платёж.
      </p>
      {_cta(order_id, 'Открыть заказ')}
    """)
    return subject, html


def _tpl_paid(order_id: int, user_name: str | None) -> tuple[str, str]:
    subject = f"Оплата подтверждена - Заказ #{order_id}"
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">{_greeting(user_name)}</h2>
      <span style="{_BADGE_GREEN}">Оплата подтверждена</span>
      <p style="{_BODY_STYLE}">
        Оплата по заказу <b>#{order_id}</b> успешно подтверждена.<br>
        Мы передаём ваш заказ в службу доставки - вы получите уведомление, как только он будет забран.
      </p>
      {_cta(order_id, 'Отследить заказ')}
    """)
    return subject, html


def _tpl_payment_rejected(order_id: int, user_name: str | None, reject_reason: str | None) -> tuple[str, str]:
    subject = f"Чек отклонён - Заказ #{order_id}"
    # reject_reason is typed by admin — always escape before splicing into HTML.
    safe_reason = _html.escape(reject_reason) if reject_reason else ""
    reason_block = (
        f'<p style="background:#fff1f2;border-left:3px solid #f43f5e;padding:12px 16px;border-radius:0 8px 8px 0;color:#9f1239;font-size:14px;margin-bottom:20px;"><b>Причина:</b> {safe_reason}</p>'
        if reject_reason else ""
    )
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">{_greeting(user_name)}</h2>
      <span style="{_BADGE_RED}">Чек отклонён</span>
      <p style="{_BODY_STYLE}">
        К сожалению, чек по заказу <b>#{order_id}</b> не прошёл проверку.
      </p>
      {reason_block}
      <p style="{_BODY_STYLE}">
        Пожалуйста, загрузите корректный чек об оплате, чтобы мы смогли подтвердить платёж.
      </p>
      {_cta(order_id, 'Загрузить новый чек')}
    """)
    return subject, html


def _tpl_dispatched(
    order_id: int,
    user_name: str | None,
    tracking_number: str | None = None,
) -> tuple[str, str]:
    subject = f"Заказ передан перевозчику - #{order_id}"
    # tracking_number приходит из dispatch-воркера сразу после успешного
    # create_invoice у перевозчика — на этом же шаге его показывает и
    # пользовательский UI, поэтому в письме имеет смысл продублировать.
    safe_tn = _html.escape(tracking_number) if tracking_number else ""
    tracking_block = (
        f'<p style="background:#eff6ff;border-left:3px solid #2563eb;padding:12px 16px;'
        f'border-radius:0 8px 8px 0;color:#1e3a8a;font-size:14px;margin-bottom:20px;">'
        f'<b>Ваш трек-номер:</b> <span style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace;">{safe_tn}</span></p>'
        if tracking_number else ""
    )
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">{_greeting(user_name)}</h2>
      <span style="{_BADGE_BLUE}">Передан перевозчику</span>
      <p style="{_BODY_STYLE}">
        Ваш заказ <b>#{order_id}</b> успешно передан перевозчику.<br>
        Ожидайте звонка курьера — он свяжется с отправителем для согласования времени забора.
      </p>
      {tracking_block}
      {_cta(order_id, 'Отследить заказ')}
    """)
    return subject, html


def _tpl_in_transit(order_id: int, user_name: str | None) -> tuple[str, str]:
    subject = f"Заказ в пути - #{order_id}"
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">{_greeting(user_name)}</h2>
      <span style="{_BADGE_BLUE}">В пути</span>
      <p style="{_BODY_STYLE}">
        Заказ <b>#{order_id}</b> в пути к получателю.
      </p>
      {_cta(order_id, 'Отследить заказ')}
    """)
    return subject, html


def _tpl_arrived(order_id: int, user_name: str | None) -> tuple[str, str]:
    subject = f"Заказ прибыл в пункт выдачи - #{order_id}"
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">{_greeting(user_name)}</h2>
      <span style="{_BADGE_GREEN}">Прибыл в пункт выдачи</span>
      <p style="{_BODY_STYLE}">
        Заказ <b>#{order_id}</b> прибыл в пункт выдачи и ожидает получателя.
      </p>
      {_cta(order_id, 'Подробнее')}
    """)
    return subject, html


def _tpl_out_for_delivery(order_id: int, user_name: str | None) -> tuple[str, str]:
    subject = f"Курьер выехал к вам — #{order_id}"
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">{_greeting(user_name)}</h2>
      <span style="{_BADGE_BLUE}">Выезд на доставку</span>
      <p style="{_BODY_STYLE}">
        Курьер выехал к получателю по заказу <b>#{order_id}</b>. Убедитесь, что
        получатель на связи по указанному номеру телефона.
      </p>
      {_cta(order_id, 'Открыть заказ')}
    """)
    return subject, html


def _tpl_delivery_failed(order_id: int, user_name: str | None) -> tuple[str, str]:
    subject = f"Попытка доставки не удалась — #{order_id}"
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">{_greeting(user_name)}</h2>
      <span style="{_BADGE_RED}">Попытка доставки не удалась</span>
      <p style="{_BODY_STYLE}">
        Курьер не смог доставить заказ <b>#{order_id}</b>. Обычно перевозчик
        связывается с получателем и назначает новую попытку — проверьте
        историю статусов в кабинете.
      </p>
      {_cta(order_id, 'Открыть заказ')}
    """)
    return subject, html


def _tpl_customs_hold(order_id: int, user_name: str | None) -> tuple[str, str]:
    subject = f"Заказ задержан на таможне — #{order_id}"
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">{_greeting(user_name)}</h2>
      <span style="{_BADGE_GRAY}">Задержан на таможне</span>
      <p style="{_BODY_STYLE}">
        Ваш заказ <b>#{order_id}</b> проходит таможенное оформление. Обычно
        это занимает несколько дней. Если понадобятся дополнительные
        документы — перевозчик или мы свяжемся с вами.
      </p>
      {_cta(order_id, 'Открыть заказ')}
    """)
    return subject, html


def _tpl_delivered(order_id: int, user_name: str | None) -> tuple[str, str]:
    subject = f"Заказ доставлен - #{order_id}"
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">{_greeting(user_name)}</h2>
      <span style="{_BADGE_GREEN}">Доставлен</span>
      <p style="{_BODY_STYLE}">
        Заказ <b>#{order_id}</b> успешно доставлен получателю. Спасибо, что воспользовались Novex!
      </p>
      {_cta(order_id, 'Оставить отзыв')}
    """)
    return subject, html


def _tpl_cancelled(order_id: int, user_name: str | None) -> tuple[str, str]:
    subject = f"Заказ отменён - #{order_id}"
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">{_greeting(user_name)}</h2>
      <span style="{_BADGE_GRAY}">Отменён</span>
      <p style="{_BODY_STYLE}">
        Заказ <b>#{order_id}</b> был отменён.<br>
        Если у вас есть вопросы - ответьте на это письмо, мы поможем.
      </p>
      {_cta(order_id, 'Создать новый заказ')}
    """)
    return subject, html


def _tpl_returned(order_id: int, user_name: str | None) -> tuple[str, str]:
    subject = f"Возврат оформлен - #{order_id}"
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">{_greeting(user_name)}</h2>
      <span style="{_BADGE_GRAY}">Возврат оформлен</span>
      <p style="{_BODY_STYLE}">
        Возврат по заказу <b>#{order_id}</b> успешно оформлен.
      </p>
      {_cta(order_id, 'Подробнее')}
    """)
    return subject, html


# ── Cancellation-request templates ─────────────────────────────────────────


def _tpl_cancellation_to_carrier(
    order_id: int,
    request_id: int,
    reason: str,
    tracking_number: str | None,
    carrier_tracking_number: str | None,
    customer_email: str | None,
    customer_phone: str | None,
) -> tuple[str, str]:
    """Ops-письмо перевозчику: клиент просит отменить заказ.

    Все user-supplied поля экранируем — reason приходит от клиента,
    контакты — из его профиля. Ссылка ведёт в карrier-кабинет.
    """
    subject = f"Novex: запрос на отмену заказа #{order_id}"
    portal_url = f"{get_settings().frontend_url}/dashboard/carrier/cancellation-requests/{request_id}"
    safe_reason = _html.escape(reason)
    safe_tn = _html.escape(tracking_number or "—")
    safe_ctn = _html.escape(carrier_tracking_number or "—")
    safe_email = _html.escape(customer_email or "—")
    safe_phone = _html.escape(customer_phone or "—")
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">Запрос на отмену от клиента</h2>
      <span style="{_BADGE_RED}">Требуется действие</span>
      <p style="{_BODY_STYLE}">
        Клиент запросил отмену заказа <b>#{order_id}</b>. Проверьте статус
        заказа у себя и подтвердите либо отклоните заявку в кабинете Novex.
      </p>
      <table style="width:100%;border-collapse:collapse;margin-bottom:20px;font-size:14px;color:#334155;">
        <tr><td style="padding:6px 0;color:#64748b;">Трек Novex</td><td style="padding:6px 0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;">{safe_tn}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">Ваш номер</td><td style="padding:6px 0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;">{safe_ctn}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">Email клиента</td><td style="padding:6px 0;">{safe_email}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">Телефон клиента</td><td style="padding:6px 0;">{safe_phone}</td></tr>
      </table>
      <p style="background:#fff1f2;border-left:3px solid #f43f5e;padding:12px 16px;border-radius:0 8px 8px 0;color:#9f1239;font-size:14px;margin-bottom:20px;">
        <b>Причина клиента:</b> {safe_reason}
      </p>
      <a href="{portal_url}" style="{_BTN_STYLE}">Открыть заявку в кабинете</a>
    """)
    return subject, html


def _tpl_cancellation_approved_to_customer(
    order_id: int, user_name: str | None
) -> tuple[str, str]:
    """Клиенту: перевозчик подтвердил отмену — заказ теперь cancelled."""
    subject = f"Отмена подтверждена — Заказ #{order_id}"
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">{_greeting(user_name)}</h2>
      <span style="{_BADGE_GREEN}">Заказ отменён</span>
      <p style="{_BODY_STYLE}">
        Перевозчик подтвердил отмену вашего заказа <b>#{order_id}</b>.
        Мы уже начали процедуру возврата средств — подробности появятся в
        карточке заказа.
      </p>
      {_cta(order_id, 'Открыть заказ')}
    """)
    return subject, html


def _tpl_cancellation_rejected_to_customer(
    order_id: int,
    user_name: str | None,
    carrier_response: str | None,
) -> tuple[str, str]:
    """Клиенту: перевозчик/админ отклонил заявку, заказ жив."""
    subject = f"Заявка на отмену отклонена — Заказ #{order_id}"
    safe_response = _html.escape(carrier_response) if carrier_response else ""
    response_block = (
        f'<p style="background:#fff1f2;border-left:3px solid #f43f5e;padding:12px 16px;border-radius:0 8px 8px 0;color:#9f1239;font-size:14px;margin-bottom:20px;"><b>Комментарий перевозчика:</b> {safe_response}</p>'
        if carrier_response else ""
    )
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">{_greeting(user_name)}</h2>
      <span style="{_BADGE_RED}">Заявка отклонена</span>
      <p style="{_BODY_STYLE}">
        К сожалению, заявку на отмену заказа <b>#{order_id}</b> отклонили.
        Заказ продолжает движение по обычному маршруту.
      </p>
      {response_block}
      <p style="{_BODY_STYLE}">Если у вас остались вопросы — ответьте на это письмо, мы поможем.</p>
      {_cta(order_id, 'Открыть заказ')}
    """)
    return subject, html


def cancellation_email(
    event_type: str,
    order_id: int,
    payload: dict,
    user_name: str | None = None,
) -> tuple[str, str] | None:
    """Отдельный dispatcher — cancellation-события не привязаны к статусу
    заказа, у них своя семантика и свои плейсхолдеры."""
    match event_type:
        case "cancellation_requested_to_carrier":
            return _tpl_cancellation_to_carrier(
                order_id=order_id,
                request_id=int(payload.get("request_id") or 0),
                reason=str(payload.get("reason") or ""),
                tracking_number=payload.get("tracking_number"),
                carrier_tracking_number=payload.get("carrier_tracking_number"),
                customer_email=payload.get("customer_email"),
                customer_phone=payload.get("customer_phone"),
            )
        case "cancellation_approved_to_customer":
            return _tpl_cancellation_approved_to_customer(order_id, user_name)
        case "cancellation_rejected_to_customer":
            return _tpl_cancellation_rejected_to_customer(
                order_id, user_name, payload.get("carrier_response"),
            )
        case _:
            return None


# ── staff alerts (admin + operator) ────────────────────────────────────────

def _admin_order_link(order_id: int) -> str:
    return f"{get_settings().frontend_url}/dashboard/admin/orders?order={order_id}"


def staff_email(event_type: str, order_id: int, payload: dict) -> tuple[str, str] | None:
    """Alerts for staff — see app.modules.notifications.staff."""
    cta = f'<a href="{_admin_order_link(order_id)}" style="{_BTN_STYLE}">Открыть заказ</a>'
    match event_type:
        case "staff_payment_proof":
            subject = f"Проверьте оплату по заказу #{order_id}"
            body = (
                f'<span style="{_BADGE_BLUE}">Новый чек</span>'
                f'<h1 style="{_HEADER_STYLE}">Клиент загрузил чек</h1>'
                f'<p style="{_BODY_STYLE}">По заказу <b>#{order_id}</b> загружено подтверждение оплаты. '
                "Проверьте чек и подтвердите или отклоните оплату — до этого заказ не уйдёт перевозчику.</p>"
            )
        case "staff_cancellation_request":
            reason = _html.escape(str(payload.get("reason") or "—"))
            subject = f"Заявка на отмену заказа #{order_id}"
            body = (
                f'<span style="{_BADGE_RED}">Отмена</span>'
                f'<h1 style="{_HEADER_STYLE}">Клиент просит отменить заказ</h1>'
                f'<p style="{_BODY_STYLE}">Заказ <b>#{order_id}</b>.<br>Причина: {reason}</p>'
            )
        case "staff_dispatch_failed":
            error = _html.escape(str(payload.get("error") or "—"))
            subject = f"Заказ #{order_id} не отправлен перевозчику"
            body = (
                f'<span style="{_BADGE_RED}">Ошибка отправки</span>'
                f'<h1 style="{_HEADER_STYLE}">Заказ не ушёл перевозчику</h1>'
                f'<p style="{_BODY_STYLE}">Заказ <b>#{order_id}</b> требует ручной проверки.<br>'
                f'<span style="font-family:monospace;font-size:13px">{error}</span></p>'
            )
        case _:
            return None
    return subject, _wrap(body + cta)


# ── public API ─────────────────────────────────────────────────────────────

def order_status_email(
    status: str,
    order_id: int,
    user_name: str | None = None,
    reject_reason: str | None = None,
    tracking_number: str | None = None,
) -> tuple[str, str] | None:
    """Return (subject, html) for statuses that warrant an email, else None."""
    match status:
        case "payment_under_review":
            return _tpl_payment_under_review(order_id, user_name)
        case "paid":
            return _tpl_paid(order_id, user_name)
        case "payment_rejected":
            return _tpl_payment_rejected(order_id, user_name, reject_reason)
        case "dispatched" | "sent_to_carrier":
            return _tpl_dispatched(order_id, user_name, tracking_number)
        case "in_transit":
            return _tpl_in_transit(order_id, user_name)
        case "out_for_delivery":
            return _tpl_out_for_delivery(order_id, user_name)
        case "arrived":
            return _tpl_arrived(order_id, user_name)
        case "delivery_failed":
            return _tpl_delivery_failed(order_id, user_name)
        case "customs_hold":
            return _tpl_customs_hold(order_id, user_name)
        case "delivered":
            return _tpl_delivered(order_id, user_name)
        case "cancelled":
            return _tpl_cancelled(order_id, user_name)
        case "returned":
            return _tpl_returned(order_id, user_name)
        case _:
            return None
