"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { listCarrierOrders, type CarrierOrderItem } from "@/lib/api/carrier";

const STATUS_LABELS: Record<string, string> = {
  sent_to_carrier: "Передан перевозчику",
  pending_manual: "Ожидает обработки",
  pending_manual_dispatch: "Ожидает отправки",
  dispatch_failed: "Ошибка отправки",
  picked_up: "Принят",
  in_transit: "В пути",
  arrived: "Прибыл",
  delivered: "Доставлен",
};

const STATUS_STYLE: Record<string, React.CSSProperties> = {
  sent_to_carrier: { background: "#dbeafe", color: "#1e40af" },
  pending_manual: { background: "#fef9c3", color: "#854d0e" },
  pending_manual_dispatch: { background: "#fef9c3", color: "#854d0e" },
  dispatch_failed: { background: "#fee2e2", color: "#991b1b" },
  picked_up: { background: "#dcfce7", color: "#166534" },
  in_transit: { background: "#dbeafe", color: "#1e40af" },
  arrived: { background: "#ede9fe", color: "#5b21b6" },
  delivered: { background: "#dcfce7", color: "#166534" },
};

const badge: React.CSSProperties = {
  padding: "2px 10px",
  borderRadius: 12,
  fontSize: 12,
  fontWeight: 600,
  display: "inline-block",
};

export default function CarrierOrdersPage() {
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
      const res = await listCarrierOrders({ status: statusFilter || undefined, page, size: 20 });
      setOrders(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page]);

  useEffect(() => { load(); }, [load]);

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
          {Object.entries(STATUS_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {loading ? (
        <p style={{ color: "#6b7280" }}>Загрузка...</p>
      ) : (
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
                    <span style={{ ...badge, ...(STATUS_STYLE[o.status] ?? { background: "#f1f5f9" }) }}>
                      {STATUS_LABELS[o.status] ?? o.status}
                    </span>
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
            {orders.length === 0 && (
              <tr>
                <td colSpan={7} style={{ ...styles.td, textAlign: "center", color: "#9ca3af" }}>
                  Заказы не найдены
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 16, alignItems: "center" }}>
        <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} style={styles.pageBtn}>← Назад</button>
        <span style={{ fontSize: 13 }}>Стр. {page} · Всего {total}</span>
        <button onClick={() => setPage((p) => p + 1)} disabled={orders.length < 20} style={styles.pageBtn}>Вперёд →</button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  select: { border: "1px solid #e5e7eb", borderRadius: 6, padding: "6px 12px", fontSize: 13, outline: "none" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: { textAlign: "left", padding: "8px 12px", borderBottom: "2px solid #e5e7eb", fontWeight: 600, color: "#374151", whiteSpace: "nowrap" },
  tr: { borderBottom: "1px solid #f3f4f6" },
  td: { padding: "10px 12px", verticalAlign: "top" },
  btn: { background: "#4338ca", color: "#fff", borderRadius: 6, padding: "4px 12px", fontSize: 12, fontWeight: 600, textDecoration: "none", display: "inline-block" },
  pageBtn: { border: "1px solid #e5e7eb", borderRadius: 6, padding: "6px 12px", fontSize: 12, cursor: "pointer", background: "#fff" },
  error: { background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "8px 14px", fontSize: 13, color: "#991b1b", marginBottom: 12 },
};
