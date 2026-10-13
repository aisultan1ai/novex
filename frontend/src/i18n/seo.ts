import type { Metadata } from "next";
import { localePrefix } from "./routing";

export const SITE_URL = "https://novex.kz";

/**
 * canonical + hreflang для страницы. `path` - путь без префикса локали
 * ("/", "/tracking"). Google получает обе языковые версии и x-default.
 */
export function localeAlternates(path: string, locale: string): Metadata["alternates"] {
  const clean = path === "/" ? "" : path;
  const ru = clean || "/";
  const kk = `/kz${clean}`;
  return {
    canonical: `${localePrefix(locale)}${clean}` || "/",
    languages: {
      "ru-KZ": ru,
      "kk-KZ": kk,
      "x-default": ru,
    },
  };
}

export const OG_LOCALE: Record<string, string> = { ru: "ru_KZ", kk: "kk_KZ" };
