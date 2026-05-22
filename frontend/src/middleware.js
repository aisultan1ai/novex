import { NextResponse } from "next/server";

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

  // Sanitize ?next= on the login page to prevent open-redirect attacks (BUG #2).
  // Only relative paths (starting with "/") are allowed.
  if (pathname === "/login") {
    const next = request.nextUrl.searchParams.get("next");
    if (next && !next.startsWith("/")) {
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
