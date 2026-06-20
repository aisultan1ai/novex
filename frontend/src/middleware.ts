import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Decodes JWT payload without signature verification - routing only, real auth
// is enforced by the backend on every API call.
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

const ADMIN_ROLES = new Set(["admin", "operator"]);

export function middleware(req: NextRequest) {
  const host = req.headers.get("host") ?? "";
  const { pathname } = req.nextUrl;

  // Local development: skip subdomain logic entirely
  if (host.includes("localhost") || host.includes("127.0.0.1")) {
    return NextResponse.next();
  }

  const isAdminDomain = host.startsWith("admin.");
  const mainDomain = isAdminDomain ? host.slice("admin.".length) : host;

  // ── admin.novex.kz ────────────────────────────────────────────────────────
  if (isAdminDomain) {
    const token = req.cookies.get("access_token")?.value;

    // No cookie → back to main domain login
    if (!token) {
      return NextResponse.redirect(new URL(`https://${mainDomain}/login`));
    }

    const payload = decodeJwtPayload(token);
    const role = payload?.role as string | undefined;

    // Customer / carrier accidentally on admin domain → back to their dashboard
    if (!role || !ADMIN_ROLES.has(role)) {
      return NextResponse.redirect(new URL(`https://${mainDomain}/dashboard/orders`));
    }

    // Root → admin dashboard
    if (pathname === "/") {
      return NextResponse.redirect(new URL("/admin/dashboard", req.url));
    }

    return NextResponse.next();
  }

  // ── novex.kz - block direct /admin/* access ───────────────────────────────
  if (pathname.startsWith("/admin")) {
    return NextResponse.redirect(new URL("/", req.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico).*)"],
};
