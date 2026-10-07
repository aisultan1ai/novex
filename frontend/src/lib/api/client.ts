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

// Понятные русские имена для полей API (в порядке появления в UI). Используется
// в переводе Pydantic-ошибок: без этой карты сообщение "String should have at
// least 1 character" не подсказывает пользователю какое именно поле пустое.
const FIELD_LABELS_RU: Record<string, string> = {
  from_city: "город отправления",
  to_city: "город доставки",
  from_country: "страна отправления",
  to_country: "страна доставки",
  shipment_type: "тип отправления",
  weight_kg: "вес",
  quantity: "количество",
  width_cm: "ширина",
  height_cm: "высота",
  depth_cm: "глубина",
  email: "email",
  password: "пароль",
  full_name: "имя",
  phone: "телефон",
  iin: "ИИН",
  bin: "БИН",
  company_name: "название компании",
  contact_name: "контактное лицо",
  comment: "комментарий",
  cities: "города",
  tracking_number: "трек-номер",
  address: "адрес",
  city: "город",
  postal_code: "индекс",
  recipient_name: "получатель",
  sender_name: "отправитель",
  rate_quote_id: "тариф",
};

function translatePydanticMsg(msg: string, fieldLabel: string | null): string {
  const field = fieldLabel ?? "поле";
  const cap = field.charAt(0).toUpperCase() + field.slice(1);
  // Все шаблоны через двоеточие или тире - чтобы не согласовывать род/падеж
  // русских имён полей ("Вес" м / "Ширина" ж / "Количество" ср).
  if (/^Field required$/i.test(msg)) return `Заполните поле: ${field}.`;
  if (/^String should have at least 1 character$/i.test(msg))
    return `Заполните поле: ${field}.`;
  if (/^String should have at least (\d+) characters?$/i.test(msg)) {
    const n = msg.match(/\d+/)?.[0];
    return `${cap} — минимум ${n} симв.`;
  }
  if (/^String should have at most (\d+) characters?$/i.test(msg)) {
    const n = msg.match(/\d+/)?.[0];
    return `${cap} — максимум ${n} симв.`;
  }
  if (/valid email/i.test(msg)) return `Некорректный email.`;
  if (/^Input should be greater than 0$/i.test(msg))
    return `${cap}: значение больше 0.`;
  if (/^Input should be greater than or equal to ([\d.]+)/i.test(msg)) {
    const n = msg.match(/[\d.]+/)?.[0];
    return `${cap}: не меньше ${n}.`;
  }
  if (/^Input should be less than or equal to ([\d.]+)/i.test(msg)) {
    const n = msg.match(/[\d.]+/)?.[0];
    return `${cap}: не больше ${n}.`;
  }
  if (/^Input should be a valid (integer|number)/i.test(msg))
    return `${cap}: нужно число.`;
  if (/^Input should be a valid boolean/i.test(msg))
    return `${cap}: неверное значение.`;
  if (/^Input should be/i.test(msg))
    return `${cap}: неверное значение.`;
  // Value-level ошибки уже часто идут по-русски - оставляем как есть.
  return msg;
}

// ── Human-readable errors ───────────────────────────────────────────────────
// Customers must never see raw backend / browser texts such as "Request failed
// with status 403", "Failed to fetch" or "User with this email already exists".
// Everything that reaches the UI goes through humanizeMessage().

const EXACT_MESSAGES_RU: Record<string, string> = {
  "user with this email already exists": "Пользователь с таким email уже зарегистрирован. Войдите или восстановите пароль.",
  "invalid email or password": "Неверный email или пароль.",
  "user account is inactive": "Аккаунт отключён. Обратитесь в поддержку.",
  "current user is inactive": "Аккаунт отключён. Обратитесь в поддержку.",
  "authorization credentials are required": "Войдите в аккаунт, чтобы продолжить.",
  "session expired. please log in again.": "Сессия истекла. Войдите в аккаунт снова.",
  "token has expired": "Сессия истекла. Войдите в аккаунт снова.",
  "token subject is missing": "Сессия недействительна. Войдите в аккаунт снова.",
  "invalid token subject": "Сессия недействительна. Войдите в аккаунт снова.",
  "current user not found": "Аккаунт не найден. Войдите в аккаунт снова.",
  "user not found": "Пользователь не найден.",
  "customer profile is missing": "Профиль не заполнен. Откройте раздел «Профиль» и заполните данные.",
  "access restricted to administrators": "Недостаточно прав для этого действия.",
  "access restricted to administrators and operators": "Недостаточно прав для этого действия.",
  "access restricted to carriers": "Недостаточно прав для этого действия.",
  "carrier profile not found": "Профиль перевозчика не найден. Обратитесь в поддержку.",
  "order draft not found": "Заказ не найден.",
  "order draft does not belong to the current user": "Нет доступа к этому заказу.",
  "only unpaid orders can be deleted": "Удалить можно только неоплаченный заказ.",
  "quote session not found": "Расчёт не найден. Выполните расчёт заново.",
  "quote session not found.": "Расчёт не найден. Выполните расчёт заново.",
  "quote session has expired": "Расчёт устарел. Выполните расчёт заново.",
  "invalid or missing quote token": "Расчёт недоступен. Выполните расчёт заново.",
  "no selected rate quote for the given quote session": "Сначала выберите тариф.",
  "rate quote not found.": "Тариф не найден. Выполните расчёт заново.",
  "payment transaction not found": "Платёж не найден.",
  "file storage unavailable": "Хранилище файлов временно недоступно. Попробуйте позже.",
  "file upload failed": "Не удалось загрузить файл. Попробуйте ещё раз.",
  "internal server error": "Сервер временно недоступен. Попробуйте позже.",
  "not found": "Не найдено.",
  "forbidden": "Недостаточно прав для этого действия.",
  "unauthorized": "Войдите в аккаунт, чтобы продолжить.",
  "method not allowed": "Действие недоступно.",
  "bad request": "Некорректный запрос. Проверьте введённые данные.",
};

const PATTERN_MESSAGES_RU: [RegExp, string][] = [
  [/^Cannot (upload proof for|approve|reject) payment in status/i, "Это действие недоступно для текущего статуса оплаты."],
  [/^File size exceeds/i, "Файл слишком большой. Загрузите файл меньшего размера."],
  [/^Detected file type/i, "Неподдерживаемый тип файла. Загрузите JPG, PNG или PDF."],
  [/^Allowed:/i, "Неподдерживаемый тип файла. Загрузите JPG, PNG или PDF."],
  [/^Invalid token/i, "Сессия недействительна. Войдите в аккаунт снова."],
  [/^Rate limit exceeded/i, "Слишком много попыток. Подождите немного и попробуйте снова."],
  [/^Request failed with status/i, ""],
];

function statusFallbackRu(status: number): string {
  switch (status) {
    case 0:
      return "Нет соединения с сервером. Проверьте интернет и попробуйте снова.";
    case 400:
      return "Некорректный запрос. Проверьте введённые данные.";
    case 401:
      return "Войдите в аккаунт, чтобы продолжить.";
    case 403:
      return "Недостаточно прав для этого действия.";
    case 404:
      return "Не найдено.";
    case 405:
      return "Действие недоступно.";
    case 409:
      return "Действие конфликтует с текущим состоянием. Обновите страницу и попробуйте снова.";
    case 413:
      return "Файл слишком большой. Загрузите файл меньшего размера.";
    case 415:
      return "Неподдерживаемый тип файла.";
    case 422:
      return "Проверьте введённые данные.";
    case 429:
      return "Слишком много попыток. Подождите немного и попробуйте снова.";
    case 500:
      return "Сервер временно недоступен. Попробуйте позже.";
    case 502:
    case 503:
    case 504:
      return "Сервис временно недоступен. Попробуйте через минуту.";
    default:
      return status >= 500
        ? "Сервер временно недоступен. Попробуйте позже."
        : "Не удалось выполнить действие. Попробуйте ещё раз или напишите в поддержку.";
  }
}

/**
 * Turn any backend / transport text into something a customer can read.
 * Russian text passes through; known English texts are translated; unknown
 * English technical text is replaced by a status-based Russian message.
 */
export function humanizeMessage(raw: string, status: number): string {
  const text = (raw ?? "").trim();
  if (!text) return statusFallbackRu(status);

  const exact = EXACT_MESSAGES_RU[text.toLowerCase()];
  if (exact) return exact;

  for (const [re, ru] of PATTERN_MESSAGES_RU) {
    if (re.test(text)) return ru || statusFallbackRu(status);
  }

  const hasCyrillic = /[А-Яа-яЁё]/.test(text);
  // Two+ latin words and no Cyrillic = a technical English sentence.
  const looksTechnical = !hasCyrillic && /[A-Za-z]{3,}[\s_:][A-Za-z]{2,}/.test(text);
  if (looksTechnical) {
    if (typeof console !== "undefined") console.warn("[api] untranslated error:", text);
    return statusFallbackRu(status);
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
          const fieldLabel =
            typeof fieldKey === "string" ? (FIELD_LABELS_RU[fieldKey] ?? null) : null;
          return translatePydanticMsg(msg, fieldLabel);
        })
        .filter((m): m is string => !!m);
      if (messages.length > 0) return { detail: messages.join(". "), code: null };
    }
  }
  // Нет понятного detail (например slowapi 429 отдаёт свой формат).
  return { detail: statusFallbackRu(status), code: null };
}

/** Network-level failure (offline, DNS, CORS, aborted connection) → ApiError(0). */
function networkError(): ApiError {
  return new ApiError(0, statusFallbackRu(0));
}

/** fetch() that never throws a raw TypeError("Failed to fetch") at the UI. */
export async function safeFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
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
