import type { AbstractIntlMessages } from "next-intl";

// Какие разделы messages/*.json нужны в браузере на каждом участке сайта.
// Клиенту отдаём только их, а не весь файл (~105 КБ, вместе с админкой):
// публичные страницы не тянут тексты кабинета и админки.
//
// Вложенный NextIntlClientProvider ЗАМЕНЯЕТ сообщения родителя, поэтому
// каждый следующий набор включает предыдущий.
//
// Серверные компоненты (metadata, 404, юридические страницы) читают переводы
// через getTranslations напрямую и в эти списки не входят.

/** Шапка, футер, лендинг, отслеживание, партнёрам, вход/регистрация. */
export const PUBLIC_NAMESPACES = [
  "localeSwitcher",
  "common",
  "errorPage",
  "nav",
  "footer",
  "citySelect",
  "home",
  "tracking",
  "partners",
  "auth",
  "emailVerify",
  "consent",
] as const;

/** Расчёт тарифа и оформление отправления (/quote/*). */
export const QUOTE_NAMESPACES = [...PUBLIC_NAMESPACES, "quote", "shipment"] as const;

/** Оплата (/checkout/*): шаги оформления берутся из shipment.steps. */
export const CHECKOUT_NAMESPACES = [...PUBLIC_NAMESPACES, "checkout", "shipment"] as const;

/** Кабинеты клиента и перевозчика (/dashboard/*). */
export const DASHBOARD_NAMESPACES = [
  ...PUBLIC_NAMESPACES,
  "dashboard",
  "orderStatus",
  "export",
  "carrier",
] as const;

/** Админка (/dashboard/admin/*). */
export const ADMIN_NAMESPACES = [...DASHBOARD_NAMESPACES, "admin"] as const;

export function pickMessages(
  messages: AbstractIntlMessages,
  namespaces: readonly string[],
): AbstractIntlMessages {
  const picked: AbstractIntlMessages = {};
  for (const ns of namespaces) {
    if (ns in messages) picked[ns] = messages[ns];
  }
  return picked;
}
