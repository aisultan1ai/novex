import { localePrefix, splitLocalePath } from "@/i18n/routing";
import {
  apiMsg,
  EXACT,
  FIELD_LABELS,
  PATTERNS,
  statusFallback,
  uiLocale,
  VALIDATION,
} from "./error-messages";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ?? "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  /** Machine-readable code when the backend sends `detail: {code, message}`
   *  (e.g. "email_not_verified"). Null for plain-string errors. */
  readonly code: string | null;

  constructor(status: number, detail: string, code: string | null = null) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

// Endpoints where a 401 is a normal outcome (bad credentials, already logged
// out) - do NOT trigger the global session-expired flow. Match by URL suffix
// against the request path (already stripped of API_BASE_URL).
const AUTH_ENDPOINTS_NO_REDIRECT = [
  "/auth/login",
  // Сохранение языка — фоновое удобство: истёкшая сессия не должна уводить
  // на страницу входа прямо в момент переключения языка.
  "/auth/locale",
  "/auth/logout",
  "/auth/register",
  "/auth/forgot-password",
  "/auth/reset-password",
  // Invalid / expired verification link is answered with 401 — show the
  // "Ссылка недействительна" page, don't bounce the visitor to /login.
  "/auth/verify-email",
];

let sessionExpiredHandled = false;

async function handleSessionExpired(): Promise<void> {
  if (typeof window === "undefined") return;
  if (sessionExpiredHandled) return;
  sessionExpiredHandled = true;

  // Best-effort: ask the server to clear the httpOnly cookie. Ignore failures
  // - we redirect regardless so the user is never stuck on a stale page.
  try {
    await safeFetch(`${API_BASE_URL}/auth/logout`, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    });
  } catch {
    /* noop */
  }

  const { search } = window.location;
  // Язык берём из адреса: /kz/... должно вести на /kz/login, а в next кладём
  // путь без префикса - логин-страница сама добавит его через локализованный router.
  const { locale, path: pathname } = splitLocalePath(window.location.pathname);
  // Avoid redirect loops if we're already on a public/auth page.
  if (pathname.startsWith("/login")) return;

  const next = encodeURIComponent(`${pathname}${search}`);
  window.location.href = `${localePrefix(locale)}/login?next=${next}`;
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

// Понятные имена полей API на языке интерфейса (error-messages.ts). Без них
// сообщение "String should have at least 1 character" не подсказывает
// пользователю, какое именно поле пустое.
function fieldLabel(field: string): string | null {
  return FIELD_LABELS[uiLocale()][field] ?? null;
}

function translatePydanticMsg(msg: string, label: string | null): string {
  const v = VALIDATION[uiLocale()];
  const field = label ?? v.field;
  const cap = field.charAt(0).toUpperCase() + field.slice(1);
  // Все шаблоны через двоеточие или тире - чтобы не согласовывать род/падеж
  // имён полей ("Вес" м / "Ширина" ж / "Количество" ср).
  const fill = (tpl: string, n?: string) =>
    tpl.replace("{field}", field).replace("{Field}", cap).replace("{n}", n ?? "");
  if (/^Field required$/i.test(msg)) return fill(v.required);
  if (/^String should have at least 1 character$/i.test(msg)) return fill(v.required);
  if (/^String should have at least (\d+) characters?$/i.test(msg))
    return fill(v.minLength, msg.match(/\d+/)?.[0]);
  if (/^String should have at most (\d+) characters?$/i.test(msg))
    return fill(v.maxLength, msg.match(/\d+/)?.[0]);
  if (/valid email/i.test(msg)) return v.email;
  if (/^Input should be greater than 0$/i.test(msg)) return fill(v.positive);
  if (/^Input should be greater than or equal to ([\d.]+)/i.test(msg))
    return fill(v.gte, msg.match(/[\d.]+/)?.[0]);
  if (/^Input should be less than or equal to ([\d.]+)/i.test(msg))
    return fill(v.lte, msg.match(/[\d.]+/)?.[0]);
  if (/^Input should be a valid (integer|number)/i.test(msg)) return fill(v.number);
  if (/^Input should be/i.test(msg)) return fill(v.invalid);
  // Value-level ошибки уже часто идут по-русски - оставляем как есть.
  return msg;
}

// ── Human-readable errors ───────────────────────────────────────────────────
// Customers must never see raw backend / browser texts such as "Request failed
// with status 403", "Failed to fetch" or "User with this email already exists".
// Everything that reaches the UI goes through humanizeMessage().

/**
 * Turn any backend / transport text into something a customer can read.
 * Russian text passes through; known English texts are translated; unknown
 * English technical text is replaced by a status-based message.
 */
export function humanizeMessage(raw: string, status: number): string {
  const text = (raw ?? "").trim();
  if (!text) return statusFallback(status);

  const exact = EXACT[text.toLowerCase()];
  if (exact) return apiMsg(exact);

  for (const [re, id] of PATTERNS) {
    if (re.test(text)) return id ? apiMsg(id) : statusFallback(status);
  }

  const hasCyrillic = /[А-Яа-яЁё]/.test(text);
  // Two+ latin words and no Cyrillic = a technical English sentence.
  const looksTechnical = !hasCyrillic && /[A-Za-z]{3,}[\s_:][A-Za-z]{2,}/.test(text);
  if (looksTechnical) {
    if (typeof console !== "undefined") console.warn("[api] untranslated error:", text);
    return statusFallback(status);
  }
  return text;
}

// FastAPI/Pydantic returns `detail` as a plain string, an object
// `{code, message}` (e.g. email_not_verified) OR an array of validation errors:
// [{loc: ["body","phone"], msg: "Value error, ...", type: "..."}].
function extractError(data: unknown, status: number): { detail: string; code: string | null } {
  if (typeof data === "object" && data !== null && "detail" in data) {
    const detail = (data as { detail?: unknown }).detail;

    if (typeof detail === "string") return { detail: humanizeMessage(detail, status), code: null };

    if (typeof detail === "object" && detail !== null && !Array.isArray(detail)) {
      const obj = detail as { code?: unknown; message?: unknown };
      const message = typeof obj.message === "string" ? obj.message : "";
      return {
        detail: humanizeMessage(message, status),
        code: typeof obj.code === "string" ? obj.code : null,
      };
    }

    if (Array.isArray(detail)) {
      const messages = detail
        .map((item: unknown) => {
          if (typeof item !== "object" || item === null) return null;
          const rawMsg = (item as { msg?: unknown }).msg;
          if (typeof rawMsg !== "string") return null;
          // Pydantic prefixes user errors with "Value error, " - strip it
          const msg = rawMsg.replace(/^Value error,\s*/, "");
          // Extract the target field from `loc`: ["body", "from_city"] → "from_city"
          const loc = (item as { loc?: unknown }).loc;
          const fieldKey =
            Array.isArray(loc)
              ? loc.filter((l) => typeof l === "string" && l !== "body").pop()
              : null;
          const label =
            typeof fieldKey === "string" ? fieldLabel(fieldKey) : null;
          return translatePydanticMsg(msg, label);
        })
        .filter((m): m is string => !!m);
      if (messages.length > 0) return { detail: messages.join(". "), code: null };
    }
  }
  // Нет понятного detail (например slowapi 429 отдаёт свой формат).
  return { detail: statusFallback(status), code: null };
}

/** Network-level failure (offline, DNS, CORS, aborted connection) → ApiError(0). */
function networkError(): ApiError {
  return new ApiError(0, statusFallback(0));
}

/** fetch() that never throws a raw TypeError("Failed to fetch") at the UI. */
export async function safeFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  // Язык интерфейса для бэкенда: на нём придут тексты ошибок (см. backend
  // app/core/i18n.py). Accept-Language — CORS-safelisted заголовок, поэтому
  // при API на другом домене не добавляет preflight-запрос.
  const headers = new Headers(init?.headers);
  headers.set("Accept-Language", uiLocale());
  try {
    return await fetch(input, { ...init, headers });
  } catch (err) {
    // An aborted request is intentional (component unmounted / newer request) — keep it.
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw networkError();
  }
}

/** Build an ApiError from a non-OK Response. Safe for non-JSON bodies. */
export async function responseToApiError(response: Response): Promise<ApiError> {
  const data = await parseJsonSafely(response);
  const { detail, code } = extractError(data, response.status);
  return new ApiError(response.status, detail, code);
}

/**
 * Message for the UI from any thrown value. ApiError → its (already Russian)
 * detail. Anything else (TypeError, DOMException, ...) → the given fallback,
 * never the raw JS message.
 */
export function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.detail;
  return fallback;
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await safeFetch(`${API_BASE_URL}${path}`, {
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
    const { detail, code } = extractError(data, response.status);
    throw new ApiError(response.status, detail, code);
  }

  return data as T;
}

export async function apiFormDataRequest<T>(
  path: string,
  body: FormData,
): Promise<T> {
  const response = await safeFetch(`${API_BASE_URL}${path}`, {
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
    const { detail, code } = extractError(data, response.status);
    throw new ApiError(response.status, detail, code);
  }

  return data as T;
}
