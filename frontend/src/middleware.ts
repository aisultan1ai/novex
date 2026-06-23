import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const part = token.split(".")[1];
    if (!part) return null;
    const decoded = atob(part.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(decoded) as Record<string, unknown>;
  } catch {
    return null;
  }
}

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

const ADMIN_ROLES = new Set(["admin", "operator"]);

const PUBLIC_PATHS = [
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/tracking",
  "/quote",
  "/api",
  "/_next",
  "/favicon",
];

export function middleware(req: NextRequest) {
  const host = req.headers.get("host") ?? "";
  const { pathname } = req.nextUrl;

  const isLocal = host.includes("localhost") || host.includes("127.0.0.1");

  // ── Subdomain routing (production only) ──────────────────────────────────
  if (!isLocal) {
    const isAdminDomain = host.startsWith("admin.");
    const mainDomain = isAdminDomain ? host.slice("admin.".length) : host;

    if (isAdminDomain) {
      const token = req.cookies.get("access_token")?.value;
      if (!token) {
        return NextResponse.redirect(new URL(`https://${mainDomain}/login`));
      }
      const payload = decodeJwtPayload(token);
      const role = payload?.role as string | undefined;
      if (!role || !ADMIN_ROLES.has(role)) {
        return NextResponse.redirect(new URL(`https://${mainDomain}/dashboard/orders`));
      }
      if (pathname === "/") {
        return NextResponse.redirect(new URL("/admin/dashboard", req.url));
      }
      return NextResponse.next();
    }

    if (pathname.startsWith("/admin")) {
      return NextResponse.redirect(new URL("/", req.url));
    }
  }

  // ── Sanitize ?next= on /login (open-redirect protection) ─────────────────
  if (pathname === "/login") {
    const next = req.nextUrl.searchParams.get("next");
    if (next && !isSafeNext(next, req.url)) {
      const cleanUrl = new URL("/login", req.url);
      req.nextUrl.searchParams.forEach((value, key) => {
        if (key !== "next") cleanUrl.searchParams.set(key, value);
      });
      return NextResponse.redirect(cleanUrl);
    }
    return NextResponse.next();
  }

  // ── Auth guard for protected paths ────────────────────────────────────────
  const isPublic =
    pathname === "/" ||
    PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  if (isPublic) return NextResponse.next();

  const token = req.cookies.get("access_token")?.value;
  if (!token) {
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico).*)"],
};
