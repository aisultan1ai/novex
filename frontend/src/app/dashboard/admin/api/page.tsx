"use client";

import { useState } from "react";

type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE" | "PUT";
type AuthLevel = "public" | "auth" | "admin";

interface Endpoint {
  method: HttpMethod;
  path: string;
  description: string;
  auth: AuthLevel;
  body?: string;
  response?: string;
}

interface ApiGroup {
  tag: string;
  description: string;
  color: string;
  endpoints: Endpoint[];
}

const BASE = "/api/v1";

const METHOD_COLORS: Record<HttpMethod, { bg: string; color: string }> = {
  GET:    { bg: "#dbeafe", color: "#1d4ed8" },
  POST:   { bg: "#dcfce7", color: "#15803d" },
  PATCH:  { bg: "#fef9c3", color: "#a16207" },
  DELETE: { bg: "#fee2e2", color: "#b91c1c" },
  PUT:    { bg: "#ede9fe", color: "#7c3aed" },
};

const AUTH_LABELS: Record<AuthLevel, { label: string; bg: string; color: string }> = {
  public: { label: "Public",    bg: "#f1f5f9", color: "#64748b" },
  auth:   { label: "Auth",      bg: "#eff6ff", color: "#1d4ed8" },
  admin:  { label: "Admin only", bg: "#fdf4ff", color: "#9333ea" },
};

const API_GROUPS: ApiGroup[] = [
  {
    tag: "Аутентификация",
    description: "Регистрация, вход, управление паролем и профилем",
    color: "#6366f1",
    endpoints: [
      { method: "POST",  path: "/auth/register",       auth: "public", description: "Регистрация нового пользователя", body: "email, password, full_name", response: "ProfileResponse" },
      { method: "POST",  path: "/auth/login",           auth: "public", description: "Вход - возвращает JWT токен", body: "email, password", response: "{ access_token, token_type }" },
      { method: "GET",   path: "/auth/profile",         auth: "auth",   description: "Получить профиль текущего пользователя", response: "ProfileResponse" },
      { method: "PATCH", path: "/auth/profile",         auth: "auth",   description: "Обновить профиль (имя, телефон и др.)", body: "Partial<ProfileUpdateRequest>" },
      { method: "POST",  path: "/auth/forgot-password", auth: "public", description: "Запросить сброс пароля - отправляет письмо", body: "email" },
      { method: "POST",  path: "/auth/reset-password",  auth: "public", description: "Установить новый пароль по токену из письма", body: "token, new_password" },
    ],
  },
  {
    tag: "Котировки",
    description: "Расчёт стоимости доставки по перевозчикам",
    color: "#0891b2",
    endpoints: [
      { method: "GET", path: "/shipping/quotes", auth: "auth", description: "Получить котировки всех перевозчиков по параметрам отправления", response: "QuoteResponse[]" },
    ],
  },
  {
    tag: "Заказы",
    description: "Создание и управление заказами клиента",
    color: "#059669",
    endpoints: [
      { method: "POST", path: "/orders/drafts/from-quote", auth: "auth", description: "Создать черновик заказа из котировки", body: "quote_id, sender_address, recipient_address", response: "OrderDraftResponse" },
      { method: "GET",  path: "/orders",                   auth: "auth", description: "Список заказов текущего клиента (пагинация: page, size)", response: "OrderDraftListResponse" },
      { method: "GET",  path: "/orders/drafts/{draft_id}", auth: "auth", description: "Получить черновик заказа по ID", response: "OrderDraftResponse" },
    ],
  },
  {
    tag: "Трекинг",
    description: "Отслеживание статуса отправлений",
    color: "#d97706",
    endpoints: [
      { method: "GET",  path: "/tracking/{tracking_number}", auth: "auth", description: "Получить события трекинга по номеру отправления", response: "TrackingEvent[]" },
      { method: "POST", path: "/carrier-tracking/webhook",   auth: "public", description: "Webhook для приёма событий от перевозчиков (HMAC-подпись)", body: "carrier_code, events[]" },
    ],
  },
  {
    tag: "Платежи",
    description: "Инициация и статус оплаты заказов",
    color: "#7c3aed",
    endpoints: [
      { method: "POST", path: "/payments/initiate", auth: "auth", description: "Инициировать оплату заказа", body: "order_id, payment_method", response: "{ payment_url, payment_id }" },
      { method: "GET",  path: "/payments/{payment_id}", auth: "auth", description: "Статус платежа", response: "PaymentStatus" },
    ],
  },
  {
    tag: "Уведомления",
    description: "Push- и email-уведомления пользователя",
    color: "#db2777",
    endpoints: [
      { method: "GET",   path: "/notifications",      auth: "auth", description: "Список уведомлений пользователя (пагинация)", response: "Notification[]" },
      { method: "PATCH", path: "/notifications/{id}", auth: "auth", description: "Отметить уведомление как прочитанное" },
    ],
  },
  {
    tag: "Адресная книга",
    description: "Сохранённые адреса пользователя",
    color: "#0f766e",
    endpoints: [
      { method: "GET",    path: "/address-book",      auth: "auth", description: "Список адресов", response: "Address[]" },
      { method: "POST",   path: "/address-book",      auth: "auth", description: "Добавить адрес", body: "city, street, house, apartment, postal_code" },
      { method: "PATCH",  path: "/address-book/{id}", auth: "auth", description: "Обновить адрес" },
      { method: "DELETE", path: "/address-book/{id}", auth: "auth", description: "Удалить адрес" },
    ],
  },
  {
    tag: "Admin - Перевозчики",
    description: "Управление перевозчиками, услугами и тарифами",
    color: "#1e40af",
    endpoints: [
      { method: "GET",    path: "/admin/carriers",                                             auth: "admin", description: "Список всех перевозчиков", response: "AdminCarrier[]" },
      { method: "POST",   path: "/admin/carriers",                                             auth: "admin", description: "Создать перевозчика", body: "code, name, description?" },
      { method: "GET",    path: "/admin/carriers/{carrier_id}",                                auth: "admin", description: "Получить перевозчика вместе с услугами" },
      { method: "PATCH",  path: "/admin/carriers/{carrier_id}",                                auth: "admin", description: "Обновить имя / описание / is_active" },
      { method: "POST",   path: "/admin/carriers/{carrier_id}/services",                       auth: "admin", description: "Создать услугу перевозчика", body: "code, name, shipment_type?" },
      { method: "PATCH",  path: "/admin/carriers/{carrier_id}/services/{service_id}",          auth: "admin", description: "Обновить услугу" },
      { method: "GET",    path: "/admin/carriers/{carrier_id}/services/{service_id}/rates",    auth: "admin", description: "Тарифные ставки услуги (пагинация)" },
      { method: "POST",   path: "/admin/carriers/{carrier_id}/services/{service_id}/rates",    auth: "admin", description: "Добавить одну ставку", body: "zone, weight_from_kg, weight_to_kg, base_price, …" },
      { method: "DELETE", path: "/admin/carriers/{carrier_id}/services/{service_id}/rates/{rate_id}", auth: "admin", description: "Удалить ставку" },
      { method: "POST",   path: "/admin/carriers/{carrier_id}/services/{service_id}/rates/upload", auth: "admin", description: "Загрузить тарифную сетку из JSON (multipart/form-data)", body: "file: File (≤ 1 MB)", response: "{ inserted: number }" },
      { method: "GET",    path: "/admin/carriers/{carrier_id}/cities",                         auth: "admin", description: "Маппинг город → зона (пагинация)" },
      { method: "POST",   path: "/admin/carriers/{carrier_id}/cities",                         auth: "admin", description: "Добавить маппинг города", body: "city_name, zone, city_type?" },
    ],
  },
  {
    tag: "Admin - Webhooks перевозчиков",
    description: "Конфигурация webhook-эндпоинтов для push-статусов",
    color: "#0369a1",
    endpoints: [
      { method: "GET",    path: "/admin/carrier-webhooks",              auth: "admin", description: "Список webhook-конфигураций" },
      { method: "POST",   path: "/admin/carrier-webhooks",              auth: "admin", description: "Создать конфигурацию", body: "carrier_code, push_url, webhook_secret?, retry_count?, timeout_seconds?" },
      { method: "GET",    path: "/admin/carrier-webhooks/{carrier_code}", auth: "admin", description: "Получить конфигурацию по коду перевозчика" },
      { method: "PATCH",  path: "/admin/carrier-webhooks/{carrier_code}", auth: "admin", description: "Обновить конфигурацию" },
      { method: "DELETE", path: "/admin/carrier-webhooks/{carrier_code}", auth: "admin", description: "Удалить конфигурацию" },
    ],
  },
  {
    tag: "Admin - Заказы",
    description: "Просмотр и управление заказами всех клиентов",
    color: "#065f46",
    endpoints: [
      { method: "GET",   path: "/admin/orders",             auth: "admin", description: "Список заказов (фильтры: page, size, status, user_id)" },
      { method: "GET",   path: "/admin/orders/{order_id}",  auth: "admin", description: "Детали заказа" },
      { method: "PATCH", path: "/admin/orders/{order_id}/status", auth: "admin", description: "Изменить статус заказа", body: "status" },
    ],
  },
  {
    tag: "Admin - Пользователи",
    description: "Управление клиентами платформы",
    color: "#92400e",
    endpoints: [
      { method: "GET",   path: "/admin/users",          auth: "admin", description: "Список пользователей (page, size, search)" },
      { method: "GET",   path: "/admin/users/{user_id}", auth: "admin", description: "Детали пользователя с историей заказов" },
      { method: "PATCH", path: "/admin/users/{user_id}", auth: "admin", description: "Обновить пользователя (is_active)", body: "is_active" },
      { method: "GET",   path: "/admin/users/stats",    auth: "admin", description: "Статистика платформы (users, orders, conversion)" },
    ],
  },
  {
    tag: "Admin - Комиссии",
    description: "Отчёты по комиссиям платформы",
    color: "#7e22ce",
    endpoints: [
      { method: "GET", path: "/admin/commissions",         auth: "admin", description: "Список транзакций комиссий (пагинация)" },
      { method: "GET", path: "/admin/commissions/summary", auth: "admin", description: "Сводка: итого комиссий за период" },
    ],
  },
  {
    tag: "Admin - Настройки",
    description: "Глобальные настройки платформы",
    color: "#374151",
    endpoints: [
      { method: "GET",   path: "/admin/settings", auth: "admin", description: "Получить настройки платформы (ставка комиссии и др.)" },
      { method: "PATCH", path: "/admin/settings", auth: "admin", description: "Обновить настройки", body: "commission_rate?" },
    ],
  },
];

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }
  return (
    <button
      onClick={copy}
      title="Скопировать путь"
      style={{ background: "none", border: "none", cursor: "pointer", padding: "2px 6px", borderRadius: 6, color: copied ? "#15803d" : "#94a3b8", fontSize: 11, fontFamily: "inherit", transition: "color 0.15s" }}
    >
      {copied ? "✓" : "copy"}
    </button>
  );
}

function EndpointRow({ ep }: { ep: Endpoint }) {
  const [open, setOpen] = useState(false);
  const m = METHOD_COLORS[ep.method];
  const a = AUTH_LABELS[ep.auth];
  const fullPath = `${BASE}${ep.path}`;

  return (
    <div
      style={{ borderBottom: "1px solid #f1f5f9", cursor: "pointer" }}
      onClick={() => setOpen((v) => !v)}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 20px", userSelect: "none" }}>
        <span style={{ fontFamily: "monospace", fontWeight: 700, fontSize: 12, padding: "3px 10px", borderRadius: 6, background: m.bg, color: m.color, minWidth: 56, textAlign: "center", flexShrink: 0 }}>
          {ep.method}
        </span>
        <span style={{ fontFamily: "monospace", fontSize: 13, color: "#1e293b", flex: 1, wordBreak: "break-all" }}>
          {fullPath}
        </span>
        <span style={{ fontSize: 12, padding: "2px 8px", borderRadius: 999, background: a.bg, color: a.color, fontWeight: 600, flexShrink: 0 }}>
          {a.label}
        </span>
        <CopyButton text={fullPath} />
        <span style={{ color: "#94a3b8", fontSize: 12, flexShrink: 0 }}>{open ? "▲" : "▼"}</span>
      </div>

      {open && (
        <div style={{ padding: "0 20px 16px", display: "flex", flexDirection: "column", gap: 8 }} onClick={(e) => e.stopPropagation()}>
          <p style={{ margin: 0, fontSize: 14, color: "#334155" }}>{ep.description}</p>
          {ep.body && (
            <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: "#64748b", minWidth: 80, paddingTop: 2 }}>Body / Params:</span>
              <code style={{ fontSize: 12, background: "#f1f5f9", padding: "4px 10px", borderRadius: 6, color: "#0f172a", fontFamily: "monospace" }}>{ep.body}</code>
            </div>
          )}
          {ep.response && (
            <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: "#64748b", minWidth: 80, paddingTop: 2 }}>Response:</span>
              <code style={{ fontSize: 12, background: "#f0fdf4", padding: "4px 10px", borderRadius: 6, color: "#15803d", fontFamily: "monospace" }}>{ep.response}</code>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function AdminApiPage() {
  const [search, setSearch] = useState("");
  const [activeGroup, setActiveGroup] = useState<string | null>(null);

  const query = search.toLowerCase();

  const filtered = API_GROUPS
    .filter((g) => activeGroup === null || g.tag === activeGroup)
    .map((g) => ({
      ...g,
      endpoints: query
        ? g.endpoints.filter((e) => e.path.toLowerCase().includes(query) || e.description.toLowerCase().includes(query) || e.method.toLowerCase().includes(query))
        : g.endpoints,
    }))
    .filter((g) => g.endpoints.length > 0);

  const totalEndpoints = API_GROUPS.reduce((s, g) => s + g.endpoints.length, 0);

  return (
    <>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0f172a" }}>API Документация</h2>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>
            {totalEndpoints} эндпоинтов · Base URL: <code style={{ fontFamily: "monospace", background: "#f1f5f9", padding: "1px 6px", borderRadius: 4 }}>{BASE}</code>
          </p>
        </div>
        <a
          href="/docs"
          target="_blank"
          rel="noopener noreferrer"
          style={{ padding: "10px 20px", borderRadius: 10, border: "1px solid #e5e7eb", background: "#ffffff", color: "#0f172a", fontSize: 13, fontWeight: 600, textDecoration: "none", display: "flex", alignItems: "center", gap: 8 }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
          </svg>
          Swagger UI
        </a>
      </div>

      {/* Auth info banner */}
      <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 12, padding: "14px 20px", marginBottom: 20, display: "flex", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#64748b", flexShrink: 0 }} />
          <span style={{ fontSize: 13, color: "#334155" }}><b>Public</b> - без токена</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#1d4ed8", flexShrink: 0 }} />
          <span style={{ fontSize: 13, color: "#334155" }}><b>Auth</b> - <code style={{ fontFamily: "monospace", fontSize: 12 }}>Authorization: Bearer &lt;token&gt;</code></span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#9333ea", flexShrink: 0 }} />
          <span style={{ fontSize: 13, color: "#334155" }}><b>Admin only</b> - Bearer + роль admin</span>
        </div>
      </div>

      {/* Search */}
      <div style={{ marginBottom: 16 }}>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Поиск по пути или описанию…"
          style={{ border: "1px solid #e5e7eb", borderRadius: 10, padding: "10px 16px", fontSize: 14, width: "100%", boxSizing: "border-box", fontFamily: "inherit", outline: "none", background: "#f8fafc", color: "#0f172a" }}
        />
      </div>

      {/* Group filter pills */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 20 }}>
        <button
          onClick={() => setActiveGroup(null)}
          style={{ padding: "5px 14px", borderRadius: 999, fontSize: 12, fontWeight: 600, border: "1px solid #e5e7eb", background: activeGroup === null ? "#0f172a" : "#ffffff", color: activeGroup === null ? "#ffffff" : "#64748b", cursor: "pointer", fontFamily: "inherit" }}
        >
          Все группы
        </button>
        {API_GROUPS.map((g) => (
          <button
            key={g.tag}
            onClick={() => setActiveGroup(activeGroup === g.tag ? null : g.tag)}
            style={{ padding: "5px 14px", borderRadius: 999, fontSize: 12, fontWeight: 600, border: `1px solid ${g.color}22`, background: activeGroup === g.tag ? g.color : `${g.color}11`, color: activeGroup === g.tag ? "#ffffff" : g.color, cursor: "pointer", fontFamily: "inherit" }}
          >
            {g.tag}
          </button>
        ))}
      </div>

      {/* Endpoint groups */}
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {filtered.length === 0 ? (
          <div style={{ padding: 48, textAlign: "center", color: "#94a3b8", background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16 }}>
            Ничего не найдено
          </div>
        ) : filtered.map((group) => (
          <div key={group.tag} style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
            {/* Group header */}
            <div style={{ padding: "16px 20px", borderBottom: "1px solid #f1f5f9", display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{ width: 10, height: 10, borderRadius: "50%", background: group.color, flexShrink: 0 }} />
              <div>
                <span style={{ fontSize: 15, fontWeight: 700, color: "#0f172a" }}>{group.tag}</span>
                <span style={{ fontSize: 12, color: "#94a3b8", marginLeft: 8 }}>{group.endpoints.length} эндпоинтов</span>
              </div>
              <span style={{ fontSize: 13, color: "#64748b", marginLeft: 4 }}>- {group.description}</span>
            </div>

            {/* Endpoints */}
            {group.endpoints.map((ep) => (
              <EndpointRow key={`${ep.method}-${ep.path}`} ep={ep} />
            ))}
          </div>
        ))}
      </div>
    </>
  );
}
