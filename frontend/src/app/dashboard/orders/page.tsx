"use client";

import type { CSSProperties } from "react";
import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { ApiError, listOrders } from "@/lib/api/orders";
import type { OrderDraftResponse } from "@/types/order";

const STATUS_LABELS: Record<string, string> = {
  draft:                      "Черновик",
  shipment_details_completed: "Детали заполнены",
  ready_for_checkout:         "Готов к оплате",
  awaiting_payment:           "Ожидает оплаты",
  payment_under_review:       "Чек на проверке",
  payment_rejected:           "Чек отклонён",
  paid:                       "Оплачен",
  dispatch_queued:            "Ожидает отправки",
  dispatch_failed:            "Уточняем детали",
  pending_manual:             "Передаётся перевозчику",
  pending_manual_dispatch:    "Ожидает ручной отправки",
  sent_to_carrier:            "Передан курьеру",
  picked_up:                  "Забран",
  in_transit:                 "В пути",
  arrived:                    "Прибыл",
  delivered:                  "Доставлен",
  return_requested:           "Запрос возврата",
  return_in_progress:         "Возврат в пути",
  returned:                   "Возвращён",
  cancelled:                  "Отменён",
  return:                     "Возврат",
};

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  draft:                      { bg: "#f1f5f9", color: "#475569" },
  shipment_details_completed: { bg: "#dbeafe", color: "#1e40af" },
  ready_for_checkout:         { bg: "#ede9fe", color: "#5b21b6" },
  awaiting_payment:           { bg: "#fef3c7", color: "#92400e" },
  payment_under_review:       { bg: "#dbeafe", color: "#1e40af" },
  payment_rejected:           { bg: "#fee2e2", color: "#991b1b" },
  paid:                       { bg: "#dcfce7", color: "#166534" },
  dispatch_queued:            { bg: "#fef3c7", color: "#92400e" },
  dispatch_failed:            { bg: "#fef3c7", color: "#92400e" },
  pending_manual:             { bg: "#fef3c7", color: "#92400e" },
  pending_manual_dispatch:    { bg: "#fef3c7", color: "#92400e" },
  sent_to_carrier:            { bg: "#dbeafe", color: "#1e40af" },
  picked_up:                  { bg: "#dbeafe", color: "#1e40af" },
  in_transit:                 { bg: "#ede9fe", color: "#5b21b6" },
  arrived:                    { bg: "#ede9fe", color: "#5b21b6" },
  delivered:                  { bg: "#dcfce7", color: "#166534" },
  return_requested:           { bg: "#fee2e2", color: "#991b1b" },
  return_in_progress:         { bg: "#fee2e2", color: "#991b1b" },
  returned:                   { bg: "#f1f5f9", color: "#475569" },
  cancelled:                  { bg: "#fee2e2", color: "#991b1b" },
  return:                     { bg: "#fee2e2", color: "#991b1b" },
};

const FILTER_GROUPS: Record<string, string[]> = {
  all: [],
  active: [
    "draft", "shipment_details_completed", "ready_for_checkout",
    "awaiting_payment", "payment_under_review", "payment_rejected",
    "dispatch_queued", "dispatch_failed", "pending_manual", "pending_manual_dispatch",
    "sent_to_carrier", "picked_up", "in_transit", "arrived",
  ],
  completed: ["delivered", "paid"],
  cancelled: ["cancelled", "return", "return_requested", "return_in_progress", "returned"],
};

const FILTER_LABELS: Record<string, string> = {
  all:       "Все",
  active:    "Активные",
  completed: "Завершённые",
  cancelled: "Отменённые",
};

function StatusBadge({ status }: { status: string }) {
  const colors = STATUS_COLORS[status] ?? { bg: "#f1f5f9", color: "#475569" };
  return (
    <span style={{ display: "inline-block", padding: "4px 12px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: colors.bg, color: colors.color, whiteSpace: "nowrap" }}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function parseUTC(iso: string): Date {
  return new Date(/[Z+]/.test(iso) ? iso : iso + "Z");
}

function formatDate(isoString: string): string {
  return parseUTC(isoString).toLocaleDateString("ru-RU", { day: "2-digit", month: "short", year: "numeric" });
}

function formatPrice(price: number, currency: string): string {
  return `${new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(price)} ${currency}`;
}

function IconTruck() {
  return (
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: 12 }}>
      <rect x="1" y="3" width="15" height="13" rx="2" />
      <path d="M16 8h4l3 6v3h-7V8z" />
      <circle cx="5.5" cy="18.5" r="2.5" />
      <circle cx="18.5" cy="18.5" r="2.5" />
    </svg>
  );
}

const cardStyle: CSSProperties = {
  border: "1px solid #e5e7eb",
  borderRadius: 16,
  background: "#ffffff",
  overflow: "hidden",
};

function MyOrdersPageInner() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const isMobile = useIsMobile();

  const justPaid = useMemo(() => searchParams.get("paid") === "1", [searchParams]);

  const [orders, setOrders] = useState<OrderDraftResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<string>("all");

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push("/login");
  }, [isAuthenticated, authLoading, router]);

  useEffect(() => {
    if (!isAuthenticated) return;
    async function fetchOrders() {
      try {
        const data = await listOrders();
        setOrders(data.items);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "Не удалось загрузить заказы.");
      } finally {
        setIsLoading(false);
      }
    }
    void fetchOrders();
  }, [isAuthenticated]);

  if (authLoading || (!isAuthenticated && !authLoading)) return null;

  const filteredOrders = activeFilter === "all"
    ? orders
    : orders.filter((o) => FILTER_GROUPS[activeFilter]?.includes(o.status));

  return (
    <>
      {justPaid && (
        <div style={{ marginBottom: 20, padding: "14px 20px", background: "#dcfce7", border: "1px solid #86efac", borderRadius: 12, fontSize: 14, fontWeight: 600, color: "#166534", display: "flex", alignItems: "center", gap: 10 }}>
          ✓ Заказ успешно оплачен! Статус обновлён.
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: isMobile ? 22 : 28, fontWeight: 800, color: "#0f172a" }}>Мои заказы</h1>
        <Link
          href="/"
          style={{ background: "#0f172a", color: "#ffffff", borderRadius: 10, padding: "10px 20px", fontSize: 14, fontWeight: 600, textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4 }}
        >
          + Новая доставка
        </Link>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        {Object.entries(FILTER_LABELS).map(([key, label]) => {
          const active = activeFilter === key;
          return (
            <button
              key={key}
              onClick={() => setActiveFilter(key)}
              style={{ padding: "6px 16px", borderRadius: 999, border: active ? "none" : "1px solid #e5e7eb", background: active ? "#0f172a" : "#ffffff", color: active ? "#ffffff" : "#64748b", fontSize: 13, fontWeight: 500, cursor: "pointer", fontFamily: "inherit" }}
            >
              {label}
            </button>
          );
        })}
      </div>

      {isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <style>{`@keyframes skeleton-pulse { 0%,100%{opacity:1} 50%{opacity:.4} }`}</style>
          {[1, 2, 3].map((i) => (
            <div key={i} style={{ ...cardStyle, padding: "20px 24px", animation: "skeleton-pulse 1.5s ease infinite", animationDelay: `${i * 0.15}s` }}>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <div style={{ width: 80, height: 16, borderRadius: 6, background: "#e5e7eb", flexShrink: 0 }} />
                <div style={{ flex: 1, height: 16, borderRadius: 6, background: "#e5e7eb" }} />
                <div style={{ width: 90, height: 24, borderRadius: 999, background: "#e5e7eb", flexShrink: 0 }} />
              </div>
            </div>
          ))}
        </div>
      ) : error ? (
        <div style={{ ...cardStyle, border: "1px solid #fecaca", background: "#fef2f2", color: "#b91c1c", padding: "20px 24px", fontSize: 14 }}>
          {error}
        </div>
      ) : filteredOrders.length === 0 ? (
        <div style={{ ...cardStyle, padding: "64px 24px", textAlign: "center" }}>
          <IconTruck />
          <p style={{ fontSize: 16, fontWeight: 700, margin: "0 0 8px", color: "#0f172a" }}>
            {activeFilter === "all" ? "Заказов пока нет" : "Заказов в этой категории нет"}
          </p>
          <p style={{ margin: "0 0 24px", fontSize: 14, color: "#64748b" }}>Оформите первую доставку прямо сейчас</p>
          <Link href="/" style={{ background: "#0f172a", color: "#ffffff", borderRadius: 10, padding: "10px 20px", fontSize: 14, fontWeight: 600, textDecoration: "none" }}>
            Рассчитать тариф
          </Link>
        </div>
      ) : isMobile ? (
        /* ── Mobile: card list ── */
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {filteredOrders.map((order) => (
            <div
              key={order.draft_id}
              onClick={() => router.push(`/dashboard/orders/${order.draft_id}`)}
              style={{ ...cardStyle, padding: "16px", cursor: "pointer", display: "flex", flexDirection: "column", gap: 10 }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a", marginBottom: 2 }}>
                    {order.from_city_snapshot} → {order.to_city_snapshot}
                  </div>
                  <div style={{ fontSize: 12, color: "#94a3b8" }}>
                    #{order.draft_id} · {formatDate(order.created_at)}
                  </div>
                </div>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: 2 }}>
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                <StatusBadge status={order.status} />
                <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>
                  {formatPrice(order.price_snapshot, order.currency_snapshot)}
                </div>
              </div>

              <div style={{ fontSize: 12, color: "#64748b" }}>
                {order.carrier_name_snapshot} · {order.tariff_name_snapshot} · {order.eta_days_min_snapshot}–{order.eta_days_max_snapshot} дн.
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* ── Desktop: table ── */
        <div style={cardStyle}>
          <div style={{ display: "grid", gridTemplateColumns: "120px 1fr 180px 140px 140px 32px", gap: 12, padding: "12px 24px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb", fontSize: 12, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", alignItems: "center" }}>
            <span>Реф. №</span>
            <span>Адрес получателя</span>
            <span>Служба / Тариф</span>
            <span>Статус заказа</span>
            <span>Оплата</span>
            <span />
          </div>

          {filteredOrders.map((order, idx) => {
            const isLast = idx === filteredOrders.length - 1;
            return (
              <div
                key={order.draft_id}
                onClick={() => router.push(`/dashboard/orders/${order.draft_id}`)}
                style={{ display: "grid", gridTemplateColumns: "120px 1fr 180px 140px 140px 32px", gap: 12, padding: "16px 24px", borderBottom: isLast ? "none" : "1px solid #f1f5f9", alignItems: "center", cursor: "pointer", transition: "background 0.1s" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "#f8fafc"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = ""; }}
              >
                <span style={{ fontFamily: "monospace", fontSize: 13, color: "#475569", fontWeight: 600 }}>
                  #{order.draft_id}
                </span>

                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "#0f172a", marginBottom: 3 }}>
                    {order.to_city_snapshot || "-"}
                  </div>
                  <div style={{ fontSize: 12, color: "#94a3b8" }}>
                    {order.from_city_snapshot} → {order.to_city_snapshot} · {formatDate(order.created_at)}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: "#0f172a", marginBottom: 3 }}>
                    {order.carrier_name_snapshot}
                  </div>
                  <div style={{ fontSize: 12, color: "#94a3b8" }}>
                    {order.tariff_name_snapshot} · {order.eta_days_min_snapshot}-{order.eta_days_max_snapshot} дн.
                  </div>
                </div>

                <StatusBadge status={order.status} />

                <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>
                  {formatPrice(order.price_snapshot, order.currency_snapshot)}
                </div>

                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}

export default function MyOrdersPage() {
  return <Suspense><MyOrdersPageInner /></Suspense>;
}
