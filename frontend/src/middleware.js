import { NextResponse } from "next/server";

/**
 * Returns true only if `raw` is a same-origin relative path.
 * Rejects: external URLs, protocol-relative //foo, backslash tricks, control chars.
 */
function isSafeNext(raw, base) {
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
  "/quote",
  "/api",
  "/_next",
  "/favicon",
];

export function middleware(request) {
  const { pathname } = request.nextUrl;

  // Sanitize ?next= on the login page to prevent open-redirect attacks.
  // Rejects external URLs, protocol-relative (//), backslash tricks, control chars.
  if (pathname === "/login") {
    const next = request.nextUrl.searchParams.get("next");
    if (next && !isSafeNext(next, request.url)) {
      const cleanUrl = new URL("/login", request.url);
      // Preserve other params (e.g. ?registered=1, ?expired=1) but drop the bad next
      request.nextUrl.searchParams.forEach((value, key) => {
        if (key !== "next") cleanUrl.searchParams.set(key, value);
      });
      return NextResponse.redirect(cleanUrl);
    }
    return NextResponse.next();
  }

  const isPublic =
    pathname === "/" ||
    PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  if (isPublic) return NextResponse.next();

  const token = request.cookies.get("access_token")?.value;
  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
