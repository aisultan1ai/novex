// Язык интерфейса для обычных (не React) функций: форматирование дат и чисел,
// тексты ошибок API. В компонентах предпочитайте useLocale()/useTranslations().
//
// В браузере язык задаёт <LocaleSync> из корневого layout — синхронно во время
// рендера, до дочерних компонентов. На сервере всегда "ru": модульная
// переменная на сервере общая для всех запросов, поэтому её там не используем
// (серверный код получает язык из next-intl / параметров маршрута).

export type UiLocale = "ru" | "kk";

let clientLocale: UiLocale | null = null;

export function setClientLocale(locale: string): void {
  if (typeof window === "undefined") return;
  clientLocale = locale === "kk" ? "kk" : "ru";
}

export function uiLocale(): UiLocale {
  if (typeof window === "undefined") return "ru";
  if (clientLocale) return clientLocale;
  return document.documentElement.lang === "kk" ? "kk" : "ru";
}

/** BCP-47 локаль для Intl / toLocaleString по коду языка сайта. */
export function toIntlLocale(locale: string): string {
  return locale === "kk" ? "kk-KZ" : "ru-RU";
}

/** BCP-47 локаль текущей страницы: "ru-RU" или "kk-KZ". */
export function intlLocale(): string {
  return toIntlLocale(uiLocale());
}
