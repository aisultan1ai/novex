const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ?? "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

// Endpoints where a 401 is a normal outcome (bad credentials, already logged
// out) - do NOT trigger the global session-expired flow. Match by URL suffix
// against the request path (already stripped of API_BASE_URL).
const AUTH_ENDPOINTS_NO_REDIRECT = [
  "/auth/login",
  "/auth/logout",
  "/auth/register",
  "/auth/forgot-password",
  "/auth/reset-password",
];

let sessionExpiredHandled = false;

async function handleSessionExpired(): Promise<void> {
  if (typeof window === "undefined") return;
  if (sessionExpiredHandled) return;
  sessionExpiredHandled = true;

  // Best-effort: ask the server to clear the httpOnly cookie. Ignore failures
  // - we redirect regardless so the user is never stuck on a stale page.
  try {
    await fetch(`${API_BASE_URL}/auth/logout`, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    });
  } catch {
    /* noop */
  }

  const { pathname, search } = window.location;
  // Avoid redirect loops if we're already on a public/auth page.
  if (pathname.startsWith("/login")) return;

  const next = encodeURIComponent(`${pathname}${search}`);
  window.location.href = `/login?next=${next}`;
}

async function parseJsonSafely(response: Response): Promise<unknown> {
  const ct = response.headers.get("content-type") ?? "";
  if (!ct.includes("application/json")) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

// FastAPI/Pydantic returns `detail` as either a plain string OR an array of
// validation errors: [{loc: ["body","phone"], msg: "Value error, ...", type: "..."}].
// Extract a user-facing message that keeps the actual field-level messages.
function extractErrorDetail(data: unknown, status: number): string {
  if (typeof data === "object" && data !== null && "detail" in data) {
    const detail = (data as { detail?: unknown }).detail;

    if (typeof detail === "string") return detail;

    if (Array.isArray(detail)) {
      const messages = detail
        .map((item: unknown) => {
          if (typeof item !== "object" || item === null) return null;
          const msg = (item as { msg?: unknown }).msg;
          if (typeof msg !== "string") return null;
          // Pydantic prefixes user errors with "Value error, " - strip it
          return msg.replace(/^Value error,\s*/, "");
        })
        .filter((m): m is string => !!m);
      if (messages.length > 0) return messages.join(". ");
    }
  }
  return `Request failed with status ${status}`;
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    credentials: "include",
    cache: "no-store",
  });

  const data = await parseJsonSafely(response);

  if (!response.ok) {
    if (
      response.status === 401 &&
      !AUTH_ENDPOINTS_NO_REDIRECT.some((p) => path.startsWith(p))
    ) {
      // Fire the session-expired flow but still throw so callers can bail
      // out of their current work - the browser will navigate away shortly.
      void handleSessionExpired();
    }
    throw new ApiError(response.status, extractErrorDetail(data, response.status));
  }

  return data as T;
}

export async function apiFormDataRequest<T>(
  path: string,
  body: FormData,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body,
    credentials: "include",
    cache: "no-store",
  });

  const data = await parseJsonSafely(response);

  if (!response.ok) {
    if (
      response.status === 401 &&
      !AUTH_ENDPOINTS_NO_REDIRECT.some((p) => path.startsWith(p))
    ) {
      // Fire the session-expired flow but still throw so callers can bail
      // out of their current work - the browser will navigate away shortly.
      void handleSessionExpired();
    }
    throw new ApiError(response.status, extractErrorDetail(data, response.status));
  }

  return data as T;
}
