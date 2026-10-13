"use client";

import { setClientLocale } from "@/i18n/runtime";

/**
 * Сообщает обычным (не React) функциям — форматированию дат, текстам ошибок
 * API — язык текущей страницы. Стоит в корневом layout ПЕРЕД страницей:
 * React рендерит его раньше дочерних компонентов, поэтому после переключения
 * языка они в том же рендере уже видят новый язык (а не старый <html lang>).
 */
export default function LocaleSync({ locale }: { locale: string }) {
  setClientLocale(locale);
  return null;
}
