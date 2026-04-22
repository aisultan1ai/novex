"use client";

import type { CSSProperties } from "react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { ApiError, listOrders } from "@/lib/api/orders";
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

function StatusBadge({ status }: { status: string }) {
  const colors = STATUS_COLORS[status] ?? { bg: "#f1f5f9", color: "#475569" };
  return (
    <span
      style={{
        display: "inline-block",
        padding: "4px 10px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        background: colors.bg,
        color: colors.color,
      }}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatPrice(price: number, currency: string): string {
  return `${new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(price)} ${currency}`;
}

const cardStyle: CSSProperties = {
  border: "1px solid #e5e7eb",
  borderRadius: 16,
  background: "#ffffff",
  boxShadow: "0 4px 16px rgba(15, 23, 42, 0.05)",
  overflow: "hidden",
};

const rowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "auto 1fr 1fr auto auto",
  gap: 16,
  alignItems: "center",
  padding: "16px 20px",
  borderBottom: "1px solid #f1f5f9",
  fontSize: 14,
  color: "#0f172a",
};

const headerRowStyle: CSSProperties = {
  ...rowStyle,
  background: "#f8fafc",
  fontWeight: 600,
  fontSize: 12,
  color: "#64748b",
  borderBottom: "1px solid #e5e7eb",
};

const emptyStyle: CSSProperties = {
  padding: "60px 24px",
  textAlign: "center",
  color: "#64748b",
};

const buttonPrimary: CSSProperties = {
  background: "#0f172a",
  color: "#ffffff",
  border: "none",
  borderRadius: 12,
  padding: "10px 16px",
  fontSize: 14,
  fontWeight: 600,
  cursor: "pointer",
  textDecoration: "none",
  display: "inline-block",
};

export default function MyOrdersPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();

  const [orders, setOrders] = useState<OrderDraftResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, authLoading, router]);

  useEffect(() => {
    if (!isAuthenticated) return;

    async function fetchOrders() {
      try {
        const data = await listOrders();
        setOrders(data.items);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.detail);
        } else {
          setError("Не удалось загрузить заказы.");
        }
      } finally {
        setIsLoading(false);
      }
    }

    fetchOrders();
  }, [isAuthenticated]);

  if (authLoading || (!isAuthenticated && !authLoading)) return null;

  return (
    <>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: "#0f172a" }}>
            Мои заказы
          </h1>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>
            История отправлений и черновики
          </p>
        </div>

        <Link href="/" style={buttonPrimary}>
          + Новая доставка
        </Link>
      </div>

      {isLoading ? (
        <div style={{ ...cardStyle, padding: 40, textAlign: "center", color: "#64748b" }}>
          Загружаем заказы…
        </div>
      ) : error ? (
        <div
          style={{
            ...cardStyle,
            border: "1px solid #fecaca",
            background: "#fef2f2",
            color: "#b91c1c",
            padding: 20,
          }}
        >
          {error}
        </div>
      ) : orders.length === 0 ? (
        <div style={{ ...cardStyle, ...emptyStyle }}>
          <p style={{ fontSize: 16, fontWeight: 600, margin: "0 0 8px" }}>
            Заказов пока нет
          </p>
          <p style={{ margin: "0 0 20px", fontSize: 14 }}>
            Оформите первую доставку прямо сейчас
          </p>
          <Link href="/" style={buttonPrimary}>
            Рассчитать тариф
          </Link>
        </div>
      ) : (
        <div style={cardStyle}>
          <div style={headerRowStyle}>
            <span>#</span>
            <span>Маршрут</span>
            <span>Служба / Тариф</span>
            <span>Статус</span>
            <span>Сумма</span>
          </div>

          {orders.map((order) => (
            <div key={order.draft_id} style={rowStyle}>
              <span style={{ color: "#64748b", fontFamily: "monospace" }}>
                #{order.draft_id}
              </span>

              <div>
                <div style={{ fontWeight: 600 }}>
                  {order.from_city_snapshot} → {order.to_city_snapshot}
                </div>
                <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
                  {order.shipment_type_snapshot} · {formatDate(order.created_at)}
                </div>
              </div>

              <div>
                <div style={{ fontWeight: 500 }}>{order.carrier_name_snapshot}</div>
                <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
                  {order.tariff_name_snapshot} · {order.eta_days_min_snapshot}–
                  {order.eta_days_max_snapshot} дн.
                </div>
              </div>

              <StatusBadge status={order.status} />

              <div style={{ textAlign: "right", fontWeight: 700 }}>
                {formatPrice(order.price_snapshot, order.currency_snapshot)}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}