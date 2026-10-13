import { defineRouting } from "next-intl/routing";

// Внутренний код казахского языка - ISO 639-1 `kk` (его же ждут Google в
// hreflang и браузеры в <html lang>). В URL при этом показываем `/kz`:
// русский живёт без префикса (novex.kz/tracking), казахский - novex.kz/kz/tracking.
export const routing = defineRouting({
  locales: ["ru", "kk"],
  defaultLocale: "ru",
  localePrefix: {
    mode: "as-needed",
    prefixes: { kk: "/kz" },
  },
  // Язык определяется только адресом. Автоопределение по Accept-Language
  // уводило бы поисковых ботов и пользователей с одного URL на другой,
  // а переключатель в шапке всё равно сохраняет выбор в ссылке.
  localeDetection: false,
});

export type Locale = (typeof routing.locales)[number];

/** Префикс URL для локали: "" для русского, "/kz" для казахского. */
export function localePrefix(locale: string): string {
  return locale === "kk" ? "/kz" : "";
}

/** Убирает префикс локали из пути: "/kz/tracking" → { locale: "kk", path: "/tracking" }. */
export function splitLocalePath(pathname: string): { locale: Locale; path: string } {
  if (pathname === "/kz" || pathname.startsWith("/kz/")) {
    return { locale: "kk", path: pathname.slice(3) || "/" };
  }
  // Явный /ru/... next-intl сам перенаправит на путь без префикса.
  if (pathname === "/ru" || pathname.startsWith("/ru/")) {
    return { locale: "ru", path: pathname.slice(3) || "/" };
  }
  return { locale: "ru", path: pathname };
}
