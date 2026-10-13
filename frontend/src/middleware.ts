import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import createIntlMiddleware from "next-intl/middleware";

import { localePrefix, routing, splitLocalePath } from "@/i18n/routing";

const intlMiddleware = createIntlMiddleware(routing);

function isSafeNext(raw: string, base: string): boolean {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return false;
  if (/[\\\x00-\x1f]/.test(raw)) return false;
  try {
    const resolved = new URL(raw, base);
    return resolved.origin === new URL(base).origin;
  } catch {
    return false;
  }
}

const PUBLIC_PATHS = [
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  // The link from the verification email is opened in whatever browser the mail
  // app uses (often with no session) and carries a one-time token in the query.
  "/verify-email",
  "/tracking",
  "/quote",
  "/partners",
  "/privacy",
  "/terms",
  "/api",
  "/_next",
  "/favicon",
];

// Админка открывается на основном домене по /dashboard/admin; роль проверяет
// AdminShell по профилю, а данные защищает бэкенд (JWT с подписью). Отдельного
// поддомена admin.* нет, поэтому роль из токена здесь не читается.
export function middleware(req: NextRequest) {
  // API-прокси (rewrites в next.config) и внутренности Next - без локализации,
  // иначе next-intl переписал бы /api/v1/... в /ru/api/v1/...
  const rawPath = req.nextUrl.pathname;
  if (rawPath.startsWith("/api/") || rawPath.startsWith("/_next")) {
    return NextResponse.next();
  }

  // Все правила ниже работают с путём без языкового префикса ("/kz/login" → "/login"),
  // а редиректы возвращают префикс обратно, чтобы пользователь не терял язык.
  const { locale, path: pathname } = splitLocalePath(rawPath);
  const prefix = localePrefix(locale);

  // ── Sanitize ?next= on /login (open-redirect protection) ─────────────────
  if (pathname === "/login") {
    const next = req.nextUrl.searchParams.get("next");
    if (next && !isSafeNext(next, req.url)) {
      const cleanUrl = new URL(`${prefix}/login`, req.url);
      req.nextUrl.searchParams.forEach((value, key) => {
        if (key !== "next") cleanUrl.searchParams.set(key, value);
      });
      return NextResponse.redirect(cleanUrl);
    }
    return intlMiddleware(req);
  }

  // ── Auth guard for protected paths ────────────────────────────────────────
  const isPublic =
    pathname === "/" ||
    PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  if (isPublic) return intlMiddleware(req);

  const token = req.cookies.get("access_token")?.value;
  if (!token) {
    const loginUrl = new URL(`${prefix}/login`, req.url);
    // Keep the query string: /checkout?draftId=… must survive the login detour.
    loginUrl.searchParams.set("next", `${pathname}${req.nextUrl.search}`);
    return NextResponse.redirect(loginUrl);
  }

  return intlMiddleware(req);
}

export const config = {
  // Skip Next.js internals and any static asset (by extension) so the middleware
  // never redirects e.g. /carriers/azimuth.png to /login. Auth is enforced only
  // on real page routes.
  matcher: [
    "/((?!_next/static|_next/image|favicon\\.ico|.*\\.(?:png|jpg|jpeg|gif|svg|webp|ico|avif|woff|woff2|ttf|otf|css|js|map|txt|xml)).*)",
  ],
};
