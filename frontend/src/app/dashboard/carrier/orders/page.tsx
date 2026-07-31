"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { listCarrierOrders, type CarrierOrderItem } from "@/lib/api/carrier";
import { ORDER_STATUS_LABELS, orderStatusColors, orderStatusLabel } from "@/lib/status-labels";
import { useIsMobile } from "@/hooks/use-is-mobile";

const badge: React.CSSProperties = {
  padding: "2px 10px",
  borderRadius: 12,
  fontSize: 12,
  fontWeight: 600,
  display: "inline-block",
};

const PAGE_SIZE = 20;

function StatusBadge({ status }: { status: string }) {
  const c = orderStatusColors(status);
  return (
    <span style={{ ...badge, background: c.bg, color: c.color }}>
      {orderStatusLabel(status)}
    </span>
  );
}

function OrderMobileCard({ order }: { order: CarrierOrderItem }) {
  const pkg = order.packages[0];
  const sender = order.parties.find((p) => p.role === "sender");
  const recipient = order.parties.find((p) => p.role === "recipient");
  return (
    <Link
      href={`/dashboard/carrier/orders/${order.id}`}
      style={{
        display: "block",
        background: "#ffffff",
        border: "1px solid #e5e7eb",
        borderRadius: 12,
        padding: "14px 16px",
        textDecoration: "none",
        color: "inherit",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8, marginBottom: 6 }}>
        <span style={{ fontWeight: 700, color: "#111827" }}>#{order.id}</span>
        <StatusBadge status={order.status} />
      </div>
      <div style={{ fontSize: 14, fontWeight: 600, color: "#111827", marginBottom: 4 }}>
        {order.from_city} → {order.to_city}
      </div>
      <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 8 }}>
        {order.tariff_name}
        {pkg ? ` · ${pkg.weight_kg} кг` : ""}
      </div>
      {sender && <div style={{ fontSize: 12, color: "#6b7280" }}>От: {sender.full_name}</div>}
      {recipient && <div style={{ fontSize: 12, color: "#6b7280" }}>Кому: {recipient.full_name}</div>}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 10, paddingTop: 10, borderTop: "1px solid #f1f5f9" }}>
        <span style={{ fontSize: 11, color: "#94a3b8" }}>{new Date(order.created_at).toLocaleDateString("ru-KZ")}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: "#111827" }}>
          {order.price.toLocaleString()} {order.currency}
        </span>
      </div>
    </Link>
  );
}

export default function CarrierOrdersPage() {
  const isMobile = useIsMobile();
  const [orders, setOrders] = useState<CarrierOrderItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listCarrierOrders({ status: statusFilter || undefined, page, size: PAGE_SIZE });
      setOrders(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page]);

  useEffect(() => { load(); }, [load]);

  // Correct "next" gate: derived from `total`, not from the local page size.
  // Previously we blocked next when `orders.length < 20` - which mis-fired on
  // exactly-20-item last pages and left users clicking through to an empty page.
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasPrev = page > 1;
  const hasNext = page < totalPages;

  return (
    <div style={{ padding: "0 0 24px" }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16, color: "#111827" }}>Заказы</h2>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          style={styles.select}
        >
          <option value="">Все статусы</option>
          {Object.entries(ORDER_STATUS_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {loading ? (
        <p style={{ color: "#6b7280" }}>Загрузка...</p>
      ) : orders.length === 0 ? (
        <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 12, padding: "48px 24px", textAlign: "center", color: "#94a3b8", fontSize: 14 }}>
          Заказы не найдены
        </div>
      ) : isMobile ? (
        /* Mobile: card list - the desktop table would horizontally overflow */
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {orders.map((o) => <OrderMobileCard key={o.id} order={o} />)}
        </div>
      ) : (
        /* Desktop: same table as before, wrapped in an overflow container so
           narrow viewports scroll horizontally instead of clipping. */
        <div style={{ overflowX: "auto" }}>
          <table style={styles.table}>
            <thead>
              <tr>
                {["ID", "Маршрут", "Вес/Тариф", "Сумма", "Статус", "Дата", ""].map((h) => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => {
                const pkg = o.packages[0];
                const sender = o.parties.find((p) => p.role === "sender");
                const recipient = o.parties.find((p) => p.role === "recipient");
                return (
                  <tr key={o.id} style={styles.tr}>
                    <td style={styles.td}>
                      <span style={{ fontWeight: 600 }}>#{o.id}</span>
                    </td>
                    <td style={styles.td}>
                      <div style={{ fontWeight: 600 }}>{o.from_city} → {o.to_city}</div>
                      {sender && <div style={{ fontSize: 11, color: "#6b7280" }}>От: {sender.full_name}</div>}
                      {recipient && <div style={{ fontSize: 11, color: "#6b7280" }}>Кому: {recipient.full_name}</div>}
                    </td>
                    <td style={styles.td}>
                      <div>{pkg ? `${pkg.weight_kg} кг` : "-"}</div>
                      <div style={{ fontSize: 11, color: "#6b7280" }}>{o.tariff_name}</div>
                    </td>
                    <td style={styles.td}>
                      <span style={{ fontWeight: 700 }}>{o.price.toLocaleString()} {o.currency}</span>
                    </td>
                    <td style={styles.td}>
                      <StatusBadge status={o.status} />
                    </td>
                    <td style={styles.td}>
                      {new Date(o.created_at).toLocaleDateString("ru-KZ")}
                    </td>
                    <td style={styles.td}>
                      <Link href={`/dashboard/carrier/orders/${o.id}`} style={styles.btn}>
                        Открыть
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 24, flexWrap: "wrap" }}>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <button
              key={p}
              onClick={() => setPage(p)}
              style={{ width: 36, height: 36, borderRadius: 8, border: "1px solid #e5e7eb", background: p === page ? "#0f172a" : "#ffffff", color: p === page ? "#ffffff" : "#0f172a", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
            >
              {p}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  select: { border: "1px solid #e5e7eb", borderRadius: 6, padding: "6px 12px", fontSize: 13, outline: "none" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13, minWidth: 720 },
  th: { textAlign: "left", padding: "8px 12px", borderBottom: "2px solid #e5e7eb", fontWeight: 600, color: "#374151", whiteSpace: "nowrap" },
  tr: { borderBottom: "1px solid #f3f4f6" },
  td: { padding: "10px 12px", verticalAlign: "top" },
  btn: { background: "#4338ca", color: "#fff", borderRadius: 6, padding: "4px 12px", fontSize: 12, fontWeight: 600, textDecoration: "none", display: "inline-block" },
  pageBtn: { border: "1px solid #e5e7eb", borderRadius: 6, padding: "6px 12px", fontSize: 12, cursor: "pointer", background: "#fff" },
  error: { background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "8px 14px", fontSize: 13, color: "#991b1b", marginBottom: 12 },
};
