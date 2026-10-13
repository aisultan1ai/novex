from __future__ import annotations

import html as _html

from app.core.config import get_settings
from app.core.i18n import normalize_locale

# Письма клиенту уходят на его языке (users.locale: "ru" | "kk"). Служебные
# письма сотрудникам (staff_email) и ops-письмо перевозчику остаются на русском.

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
_REASON_STYLE = "background:#fff1f2;border-left:3px solid #f43f5e;padding:12px 16px;border-radius:0 8px 8px 0;color:#9f1239;font-size:14px;margin-bottom:20px;"
_TRACK_STYLE = "background:#eff6ff;border-left:3px solid #2563eb;padding:12px 16px;border-radius:0 8px 8px 0;color:#1e3a8a;font-size:14px;margin-bottom:20px;"
_MONO = "font-family:ui-monospace,SFMono-Regular,Menlo,monospace;"


# ── Тексты писем клиенту ──────────────────────────────────────────────────────
# {id} — номер заказа. Значения подставляются через str.format, поэтому
# фигурные скобки в текстах не используются.

_T: dict[str, dict[str, str]] = {
    "ru": {
        "footer": "Novex - агрегатор курьерских услуг. Если у вас есть вопросы, ответьте на это письмо.",
        "client": "Клиент",
        "hello": "Здравствуйте, {name}!",
        "reason": "Причина:",
        "open_order": "Открыть заказ",
        "track_order": "Отследить заказ",
        "details": "Подробнее",
        # payment_under_review
        "review_subject": "Чек получен - Заказ #{id} на проверке",
        "review_badge": "Чек на проверке",
        "review_text": "Мы получили ваш чек об оплате по заказу <b>#{id}</b>.<br>Наши менеджеры проверят его в течение рабочего дня и подтвердят платёж.",
        # paid
        "paid_subject": "Оплата подтверждена - Заказ #{id}",
        "paid_badge": "Оплата подтверждена",
        "paid_text": "Оплата по заказу <b>#{id}</b> успешно подтверждена.<br>Мы передаём ваш заказ в службу доставки - вы получите уведомление, как только он будет забран.",
        # payment_rejected
        "rejected_subject": "Чек отклонён - Заказ #{id}",
        "rejected_badge": "Чек отклонён",
        "rejected_text": "К сожалению, чек по заказу <b>#{id}</b> не прошёл проверку.",
        "rejected_hint": "Пожалуйста, загрузите корректный чек об оплате, чтобы мы смогли подтвердить платёж.",
        "rejected_cta": "Загрузить новый чек",
        # dispatched
        "dispatched_subject": "Заказ передан перевозчику - #{id}",
        "dispatched_badge": "Передан перевозчику",
        "dispatched_text": "Ваш заказ <b>#{id}</b> успешно передан перевозчику.<br>Ожидайте звонка курьера — он свяжется с отправителем для согласования времени забора.",
        "tracking_number": "Ваш трек-номер:",
        # in_transit
        "transit_subject": "Заказ в пути - #{id}",
        "transit_badge": "В пути",
        "transit_text": "Заказ <b>#{id}</b> в пути к получателю.",
        # arrived
        "arrived_subject": "Заказ прибыл в пункт выдачи - #{id}",
        "arrived_badge": "Прибыл в пункт выдачи",
        "arrived_text": "Заказ <b>#{id}</b> прибыл в пункт выдачи и ожидает получателя.",
        # out_for_delivery
        "ofd_subject": "Курьер выехал к вам — #{id}",
        "ofd_badge": "Выезд на доставку",
        "ofd_text": "Курьер выехал к получателю по заказу <b>#{id}</b>. Убедитесь, что получатель на связи по указанному номеру телефона.",
        # delivery_failed
        "failed_subject": "Попытка доставки не удалась — #{id}",
        "failed_badge": "Попытка доставки не удалась",
        "failed_text": "Курьер не смог доставить заказ <b>#{id}</b>. Обычно перевозчик связывается с получателем и назначает новую попытку — проверьте историю статусов в кабинете.",
        # customs_hold
        "customs_subject": "Заказ задержан на таможне — #{id}",
        "customs_badge": "Задержан на таможне",
        "customs_text": "Ваш заказ <b>#{id}</b> проходит таможенное оформление. Обычно это занимает несколько дней. Если понадобятся дополнительные документы — перевозчик или мы свяжемся с вами.",
        # delivered
        "delivered_subject": "Заказ доставлен - #{id}",
        "delivered_badge": "Доставлен",
        "delivered_text": "Заказ <b>#{id}</b> успешно доставлен получателю. Спасибо, что воспользовались Novex!",
        "delivered_cta": "Оставить отзыв",
        # cancelled
        "cancelled_subject": "Заказ отменён - #{id}",
        "cancelled_badge": "Отменён",
        "cancelled_text": "Заказ <b>#{id}</b> был отменён.<br>Если у вас есть вопросы - ответьте на это письмо, мы поможем.",
        "cancelled_cta": "Создать новый заказ",
        # returned
        "returned_subject": "Возврат оформлен - #{id}",
        "returned_badge": "Возврат оформлен",
        "returned_text": "Возврат по заказу <b>#{id}</b> успешно оформлен.",
        # cancellation approved / rejected
        "cancel_ok_subject": "Отмена подтверждена — Заказ #{id}",
        "cancel_ok_badge": "Заказ отменён",
        "cancel_ok_text": "Перевозчик подтвердил отмену вашего заказа <b>#{id}</b>. Мы уже начали процедуру возврата средств — подробности появятся в карточке заказа.",
        "cancel_no_subject": "Заявка на отмену отклонена — Заказ #{id}",
        "cancel_no_badge": "Заявка отклонена",
        "cancel_no_text": "К сожалению, заявку на отмену заказа <b>#{id}</b> отклонили. Заказ продолжает движение по обычному маршруту.",
        "cancel_no_comment": "Комментарий перевозчика:",
        "cancel_no_hint": "Если у вас остались вопросы — ответьте на это письмо, мы поможем.",
    },
    "kk": {
        "footer": "Novex — курьерлік қызметтер агрегаторы. Сұрақтарыңыз болса, осы хатқа жауап беріңіз.",
        "client": "Клиент",
        "hello": "Сәлеметсіз бе, {name}!",
        "reason": "Себебі:",
        "open_order": "Тапсырысты ашу",
        "track_order": "Тапсырысты бақылау",
        "details": "Толығырақ",
        "review_subject": "Түбіртек алынды - #{id} тапсырыс тексерілуде",
        "review_badge": "Түбіртек тексерілуде",
        "review_text": "<b>#{id}</b> тапсырыс бойынша төлем түбіртегіңізді алдық.<br>Менеджерлеріміз оны жұмыс күні ішінде тексеріп, төлемді растайды.",
        "paid_subject": "Төлем расталды - #{id} тапсырыс",
        "paid_badge": "Төлем расталды",
        "paid_text": "<b>#{id}</b> тапсырыс бойынша төлем сәтті расталды.<br>Тапсырысыңызды жеткізу қызметіне береміз — ол алып кетілген сәтте хабарлама аласыз.",
        "rejected_subject": "Түбіртек қабылданбады - #{id} тапсырыс",
        "rejected_badge": "Түбіртек қабылданбады",
        "rejected_text": "Өкінішке қарай, <b>#{id}</b> тапсырыс бойынша түбіртек тексеруден өтпеді.",
        "rejected_hint": "Төлемді растай алуымыз үшін дұрыс төлем түбіртегін жүктеңіз.",
        "rejected_cta": "Жаңа түбіртек жүктеу",
        "dispatched_subject": "Тапсырыс тасымалдаушыға берілді - #{id}",
        "dispatched_badge": "Тасымалдаушыға берілді",
        "dispatched_text": "<b>#{id}</b> тапсырысыңыз тасымалдаушыға сәтті берілді.<br>Курьердің қоңырауын күтіңіз — ол алып кету уақытын келісу үшін жөнелтушімен хабарласады.",
        "tracking_number": "Трек-нөміріңіз:",
        "transit_subject": "Тапсырыс жолда - #{id}",
        "transit_badge": "Жолда",
        "transit_text": "<b>#{id}</b> тапсырыс алушыға қарай жолда.",
        "arrived_subject": "Тапсырыс беру пунктіне келді - #{id}",
        "arrived_badge": "Беру пунктіне келді",
        "arrived_text": "<b>#{id}</b> тапсырыс беру пунктіне келді және алушыны күтуде.",
        "ofd_subject": "Курьер сізге шықты — #{id}",
        "ofd_badge": "Жеткізуге шықты",
        "ofd_text": "Курьер <b>#{id}</b> тапсырыс бойынша алушыға шықты. Алушының көрсетілген телефон нөмірі бойынша байланыста екенін тексеріңіз.",
        "failed_subject": "Жеткізу әрекеті сәтсіз болды — #{id}",
        "failed_badge": "Жеткізу әрекеті сәтсіз болды",
        "failed_text": "Курьер <b>#{id}</b> тапсырысты жеткізе алмады. Әдетте тасымалдаушы алушымен хабарласып, жаңа әрекет тағайындайды — кабинеттегі мәртебелер тарихын тексеріңіз.",
        "customs_subject": "Тапсырыс кеденде ұсталды — #{id}",
        "customs_badge": "Кеденде ұсталды",
        "customs_text": "<b>#{id}</b> тапсырысыңыз кедендік рәсімдеуден өтуде. Әдетте бұл бірнеше күнге созылады. Қосымша құжаттар қажет болса, тасымалдаушы немесе біз сізбен хабарласамыз.",
        "delivered_subject": "Тапсырыс жеткізілді - #{id}",
        "delivered_badge": "Жеткізілді",
        "delivered_text": "<b>#{id}</b> тапсырыс алушыға сәтті жеткізілді. Novex-ті пайдаланғаныңызға рахмет!",
        "delivered_cta": "Пікір қалдыру",
        "cancelled_subject": "Тапсырыстан бас тартылды - #{id}",
        "cancelled_badge": "Бас тартылды",
        "cancelled_text": "<b>#{id}</b> тапсырыстан бас тартылды.<br>Сұрақтарыңыз болса — осы хатқа жауап беріңіз, көмектесеміз.",
        "cancelled_cta": "Жаңа тапсырыс жасау",
        "returned_subject": "Қайтару рәсімделді - #{id}",
        "returned_badge": "Қайтару рәсімделді",
        "returned_text": "<b>#{id}</b> тапсырыс бойынша қайтару сәтті рәсімделді.",
        "cancel_ok_subject": "Бас тарту расталды — #{id} тапсырыс",
        "cancel_ok_badge": "Тапсырыстан бас тартылды",
        "cancel_ok_text": "Тасымалдаушы <b>#{id}</b> тапсырысыңыздан бас тартуды растады. Қаражатты қайтару рәсімін бастадық — толық ақпарат тапсырыс бетінде пайда болады.",
        "cancel_no_subject": "Бас тарту өтінімі қабылданбады — #{id} тапсырыс",
        "cancel_no_badge": "Өтінім қабылданбады",
        "cancel_no_text": "Өкінішке қарай, <b>#{id}</b> тапсырыстан бас тарту өтінімі қабылданбады. Тапсырыс әдеттегі бағыт бойынша жалғасуда.",
        "cancel_no_comment": "Тасымалдаушының түсініктемесі:",
        "cancel_no_hint": "Сұрақтарыңыз қалса — осы хатқа жауап беріңіз, көмектесеміз.",
    },
}


def _tx(locale: str | None, key: str, **kw: object) -> str:
    loc = normalize_locale(locale) or "ru"
    return _T[loc][key].format(**kw)


def _wrap(body_inner: str, locale: str | None = "ru") -> str:
    return f'<div style="{_BASE_STYLE}">{body_inner}<p style="{_FOOTER_STYLE}">{_tx(locale, "footer")}</p></div>'


def frontend_url_for(locale: str | None) -> str:
    """Адрес сайта с языковым префиксом: казахская версия живёт на /kz."""
    url = get_settings().frontend_url.rstrip("/")
    return f"{url}/kz" if normalize_locale(locale) == "kk" else url


def _order_link(order_id: int, locale: str | None = "ru") -> str:
    return f"{frontend_url_for(locale)}/dashboard/orders/{order_id}"


def _cta(order_id: int, label: str, locale: str | None = "ru") -> str:
    return f'<a href="{_order_link(order_id, locale)}" style="{_BTN_STYLE}">{label}</a>'


def _greeting(user_name: str | None, locale: str | None = "ru") -> str:
    # Escape the user-supplied name — full_name comes from the customer profile
    # and can contain HTML control characters that would otherwise inject markup.
    name = _html.escape(user_name) if user_name else _tx(locale, "client")
    return _tx(locale, "hello", name=name)


def _simple(
    prefix: str,
    badge_style: str,
    order_id: int,
    user_name: str | None,
    locale: str | None,
    cta_key: str,
    extra_html: str = "",
) -> tuple[str, str]:
    """Типовое письмо: заголовок-приветствие, бейдж, абзац, кнопка."""
    subject = _tx(locale, f"{prefix}_subject", id=order_id)
    html = _wrap(f"""
      <h2 style="{_HEADER_STYLE}">{_greeting(user_name, locale)}</h2>
      <span style="{badge_style}">{_tx(locale, f"{prefix}_badge")}</span>
      <p style="{_BODY_STYLE}">{_tx(locale, f"{prefix}_text", id=order_id)}</p>
      {extra_html}
      {_cta(order_id, _tx(locale, cta_key), locale)}
    """, locale)
    return subject, html


# ── templates ──────────────────────────────────────────────────────────────

def _tpl_payment_rejected(
    order_id: int, user_name: str | None, reject_reason: str | None, locale: str | None
) -> tuple[str, str]:
    # reject_reason is typed by admin — always escape before splicing into HTML.
    safe_reason = _html.escape(reject_reason) if reject_reason else ""
    reason_block = (
        f'<p style="{_REASON_STYLE}"><b>{_tx(locale, "reason")}</b> {safe_reason}</p>'
        if reject_reason else ""
    )
    hint = f'<p style="{_BODY_STYLE}">{_tx(locale, "rejected_hint")}</p>'
    return _simple("rejected", _BADGE_RED, order_id, user_name, locale, "rejected_cta", reason_block + hint)


def _tpl_dispatched(
    order_id: int, user_name: str | None, tracking_number: str | None, locale: str | None
) -> tuple[str, str]:
    # tracking_number приходит из dispatch-воркера сразу после успешного
    # create_invoice у перевозчика — на этом же шаге его показывает и
    # пользовательский UI, поэтому в письме имеет смысл продублировать.
    safe_tn = _html.escape(tracking_number) if tracking_number else ""
    tracking_block = (
        f'<p style="{_TRACK_STYLE}"><b>{_tx(locale, "tracking_number")}</b> '
        f'<span style="{_MONO}">{safe_tn}</span></p>'
        if tracking_number else ""
    )
    return _simple("dispatched", _BADGE_BLUE, order_id, user_name, locale, "track_order", tracking_block)


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
    """Ops-письмо перевозчику (на ops-адрес компании, всегда по-русски):
    клиент просит отменить заказ.

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
        <tr><td style="padding:6px 0;color:#64748b;">Трек Novex</td><td style="padding:6px 0;{_MONO}">{safe_tn}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">Ваш номер</td><td style="padding:6px 0;{_MONO}">{safe_ctn}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">Email клиента</td><td style="padding:6px 0;">{safe_email}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">Телефон клиента</td><td style="padding:6px 0;">{safe_phone}</td></tr>
      </table>
      <p style="{_REASON_STYLE}">
        <b>Причина клиента:</b> {safe_reason}
      </p>
      <a href="{portal_url}" style="{_BTN_STYLE}">Открыть заявку в кабинете</a>
    """)
    return subject, html


def _tpl_cancellation_rejected_to_customer(
    order_id: int,
    user_name: str | None,
    carrier_response: str | None,
    locale: str | None,
) -> tuple[str, str]:
    """Клиенту: перевозчик/админ отклонил заявку, заказ жив."""
    safe_response = _html.escape(carrier_response) if carrier_response else ""
    response_block = (
        f'<p style="{_REASON_STYLE}"><b>{_tx(locale, "cancel_no_comment")}</b> {safe_response}</p>'
        if carrier_response else ""
    )
    hint = f'<p style="{_BODY_STYLE}">{_tx(locale, "cancel_no_hint")}</p>'
    return _simple("cancel_no", _BADGE_RED, order_id, user_name, locale, "open_order", response_block + hint)


def cancellation_email(
    event_type: str,
    order_id: int,
    payload: dict,
    user_name: str | None = None,
    locale: str | None = "ru",
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
            return _simple("cancel_ok", _BADGE_GREEN, order_id, user_name, locale, "open_order")
        case "cancellation_rejected_to_customer":
            return _tpl_cancellation_rejected_to_customer(
                order_id, user_name, payload.get("carrier_response"), locale,
            )
        case _:
            return None


# ── staff alerts (admin + operator) ────────────────────────────────────────

def _admin_order_link(order_id: int) -> str:
    return f"{get_settings().frontend_url}/dashboard/admin/orders?order={order_id}"


def staff_email(event_type: str, order_id: int, payload: dict) -> tuple[str, str] | None:
    """Alerts for staff — see app.modules.notifications.staff. Всегда по-русски."""
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
    locale: str | None = "ru",
) -> tuple[str, str] | None:
    """Return (subject, html) for statuses that warrant an email, else None.

    ``locale`` — язык получателя (users.locale)."""
    match status:
        case "payment_under_review":
            return _simple("review", _BADGE_BLUE, order_id, user_name, locale, "open_order")
        case "paid":
            return _simple("paid", _BADGE_GREEN, order_id, user_name, locale, "track_order")
        case "payment_rejected":
            return _tpl_payment_rejected(order_id, user_name, reject_reason, locale)
        case "dispatched" | "sent_to_carrier":
            return _tpl_dispatched(order_id, user_name, tracking_number, locale)
        case "in_transit":
            return _simple("transit", _BADGE_BLUE, order_id, user_name, locale, "track_order")
        case "out_for_delivery":
            return _simple("ofd", _BADGE_BLUE, order_id, user_name, locale, "open_order")
        case "arrived":
            return _simple("arrived", _BADGE_GREEN, order_id, user_name, locale, "details")
        case "delivery_failed":
            return _simple("failed", _BADGE_RED, order_id, user_name, locale, "open_order")
        case "customs_hold":
            return _simple("customs", _BADGE_GRAY, order_id, user_name, locale, "open_order")
        case "delivered":
            return _simple("delivered", _BADGE_GREEN, order_id, user_name, locale, "delivered_cta")
        case "cancelled":
            return _simple("cancelled", _BADGE_GRAY, order_id, user_name, locale, "cancelled_cta")
        case "returned":
            return _simple("returned", _BADGE_GRAY, order_id, user_name, locale, "details")
        case _:
            return None
