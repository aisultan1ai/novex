"use client";

import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { ApiError, deleteOrderDraft, listOrders } from "@/lib/api/orders";
import type { OrderDraftResponse } from "@/types/order";

const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  shipment_details_completed: "Детали заполнены",
  ready_for_checkout: "Готов к оплате",
  awaiting_payment: "Ожидает оплаты",
  paid: "Оплачен",
  sent_to_carrier: "Передан курьеру",
  picked_up: "Забран",
  in_transit: "В пути",
  arrived: "Прибыл",
  delivered: "Доставлен",
  cancelled: "Отменён",
  return: "Возврат",
};

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  draft: { bg: "#f1f5f9", color: "#475569" },
  shipment_details_completed: { bg: "#dbeafe", color: "#1e40af" },
  ready_for_checkout: { bg: "#ede9fe", color: "#5b21b6" },
  awaiting_payment: { bg: "#fef3c7", color: "#92400e" },
  paid: { bg: "#dcfce7", color: "#166534" },
  sent_to_carrier: { bg: "#dbeafe", color: "#1e40af" },
  picked_up: { bg: "#dbeafe", color: "#1e40af" },
  in_transit: { bg: "#ede9fe", color: "#5b21b6" },
  arrived: { bg: "#ede9fe", color: "#5b21b6" },
  delivered: { bg: "#dcfce7", color: "#166534" },
  cancelled: { bg: "#fee2e2", color: "#991b1b" },
  return: { bg: "#fee2e2", color: "#991b1b" },
};

const FILTER_GROUPS: Record<string, string[]> = {
  all: [],
  active: ["draft", "shipment_details_completed", "ready_for_checkout", "awaiting_payment", "sent_to_carrier", "picked_up", "in_transit", "arrived"],
  completed: ["delivered", "paid"],
  cancelled: ["cancelled", "return"],
};

const FILTER_LABELS: Record<string, string> = {
  all: "Все",
  active: "Активные",
  completed: "Завершённые",
  cancelled: "Отменённые",
};

function StatusBadge({ status }: { status: string }) {
  const colors = STATUS_COLORS[status] ?? { bg: "#f1f5f9", color: "#475569" };
  return (
    <span
      style={{
        display: "inline-block",
        padding: "4px 12px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        background: colors.bg,
        color: colors.color,
        whiteSpace: "nowrap",
      }}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString("ru-RU", { day: "2-digit", month: "short", year: "numeric" });
}

function formatPrice(price: number, currency: string): string {
  return `${new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(price)} ${currency}`;
}

function IconTrash() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  );
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

const PAYABLE_STATUSES = new Set(["shipment_details_completed", "ready_for_checkout"]);

export default function MyOrdersPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const justPaid = useMemo(() => searchParams.get("paid") === "1", [searchParams]);

  const [orders, setOrders] = useState<OrderDraftResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
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

  async function handleDelete(draftId: number) {
    setDeletingId(draftId);
    setConfirmingDeleteId(null);
    try {
      await deleteOrderDraft(draftId);
      setOrders((prev) => prev.filter((o) => o.draft_id !== draftId));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось удалить черновик.");
    } finally {
      setDeletingId(null);
    }
  }

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

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: "#0f172a" }}>
          Мои заказы
        </h1>
        <Link
          href="/"
          style={{
            background: "#0f172a",
            color: "#ffffff",
            borderRadius: 10,
            padding: "10px 20px",
            fontSize: 14,
            fontWeight: 600,
            textDecoration: "none",
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          + Новая доставка
        </Link>
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        {Object.entries(FILTER_LABELS).map(([key, label]) => {
          const active = activeFilter === key;
          return (
            <button
              key={key}
              onClick={() => setActiveFilter(key)}
              style={{
                padding: "6px 16px",
                borderRadius: 999,
                border: active ? "none" : "1px solid #e5e7eb",
                background: active ? "#0f172a" : "#ffffff",
                color: active ? "#ffffff" : "#64748b",
                fontSize: 13,
                fontWeight: 500,
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              {label}
            </button>
          );
        })}
      </div>

      {/* Content */}
      {isLoading ? (
        <div style={{ ...cardStyle, padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>
          Загружаем заказы…
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
          <p style={{ margin: "0 0 24px", fontSize: 14, color: "#64748b" }}>
            Оформите первую доставку прямо сейчас
          </p>
          <Link href="/" style={{ background: "#0f172a", color: "#ffffff", borderRadius: 10, padding: "10px 20px", fontSize: 14, fontWeight: 600, textDecoration: "none" }}>
            Рассчитать тариф
          </Link>
        </div>
      ) : (
        <div style={cardStyle}>
          {/* Table header */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "120px 1fr 180px 140px 140px",
              gap: 12,
              padding: "12px 24px",
              background: "#f8fafc",
              borderBottom: "1px solid #e5e7eb",
              fontSize: 12,
              fontWeight: 700,
              color: "#94a3b8",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              alignItems: "center",
            }}
          >
            <span>Реф. №</span>
            <span>Адрес получателя</span>
            <span>Служба / Тариф</span>
            <span>Статус заказа</span>
            <span>Оплата</span>
          </div>

          {/* Rows */}
          {filteredOrders.map((order, idx) => {
            const isDraft = order.status === "draft";
            const isPayable = PAYABLE_STATUSES.has(order.status);
            const isConfirming = confirmingDeleteId === order.draft_id;
            const isDeleting = deletingId === order.draft_id;
            const isLast = idx === filteredOrders.length - 1;
            const isPaid = (order.status as string) === "paid" || (order.status as string) === "delivered";

            return (
              <div key={order.draft_id}>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "120px 1fr 180px 140px 140px",
                    gap: 12,
                    padding: "16px 24px",
                    borderBottom: isConfirming || !isLast ? "1px solid #f1f5f9" : "none",
                    alignItems: "center",
                    background: isDeleting ? "#fff5f5" : undefined,
                    opacity: isDeleting ? 0.6 : 1,
                    cursor: "pointer",
                    transition: "background 0.1s",
                  }}
                  onMouseEnter={(e) => { if (!isDeleting) e.currentTarget.style.background = "#f8fafc"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = isDeleting ? "#fff5f5" : ""; }}
                >
                  <span style={{ fontFamily: "monospace", fontSize: 13, color: "#475569", fontWeight: 600 }}>
                    #{order.draft_id}
                  </span>

                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "#0f172a", marginBottom: 3 }}>
                      {order.to_city_snapshot || "—"}
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
                      {order.tariff_name_snapshot} · {order.eta_days_min_snapshot}–{order.eta_days_max_snapshot} дн.
                    </div>
                  </div>

                  <div>
                    <StatusBadge status={order.status} />
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    {isPayable ? (
                      <Link
                        href={`/checkout?draftId=${order.draft_id}`}
                        style={{ display: "inline-block", padding: "6px 12px", borderRadius: 8, background: "#0f172a", color: "#fff", fontSize: 12, fontWeight: 600, textDecoration: "none", whiteSpace: "nowrap" }}
                      >
                        Оплатить
                      </Link>
                    ) : (
                      <span style={{ padding: "4px 12px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: isPaid ? "#dcfce7" : "#f1f5f9", color: isPaid ? "#166534" : "#94a3b8" }}>
                        {isPaid ? "Оплачен" : "—"}
                      </span>
                    )}

                    {isDraft && (
                      <button
                        onClick={() => isConfirming ? setConfirmingDeleteId(null) : setConfirmingDeleteId(order.draft_id)}
                        disabled={isDeleting}
                        title="Удалить черновик"
                        style={{ display: "flex", alignItems: "center", justifyContent: "center", width: 32, height: 32, borderRadius: 8, border: isConfirming ? "1px solid #fca5a5" : "1px solid #fecaca", background: isConfirming ? "#fee2e2" : "#fff", color: "#ef4444", cursor: isDeleting ? "not-allowed" : "pointer", opacity: isDeleting ? 0.4 : 1, padding: 0, flexShrink: 0 }}
                      >
                        <IconTrash />
                      </button>
                    )}
                  </div>
                </div>

                {isConfirming && (
                  <div style={{ padding: "12px 24px", background: "#fef2f2", borderBottom: isLast ? "none" : "1px solid #fecaca", borderTop: "1px solid #fecaca", display: "flex", alignItems: "center", gap: 12, fontSize: 13, color: "#7f1d1d" }}>
                    <span style={{ flex: 1 }}>Удалить черновик #{order.draft_id}? Это нельзя отменить.</span>
                    <button onClick={() => void handleDelete(order.draft_id)} style={{ padding: "6px 14px", borderRadius: 8, border: "none", background: "#ef4444", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                      Удалить
                    </button>
                    <button onClick={() => setConfirmingDeleteId(null)} style={{ padding: "6px 14px", borderRadius: 8, border: "1px solid #fca5a5", background: "#fff", color: "#b91c1c", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                      Отмена
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
