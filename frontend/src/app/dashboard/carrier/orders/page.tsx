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
    <span style={{ display: "inline-block", padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, lineHeight: 1.35, background: c.bg, color: c.color, maxWidth: "100%", whiteSpace: "normal", wordBreak: "break-word" }}>
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

  const GRID = "70px 1fr 160px 130px 180px 110px 100px";

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0f172a" }}>Заказы</h2>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>Все заказы · {total} всего</p>
        </div>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #e5e7eb", background: "#ffffff", fontSize: 14, cursor: "pointer", fontFamily: "inherit", color: "#0f172a" }}
        >
          <option value="">Все статусы</option>
          {Object.entries(ORDER_STATUS_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      </div>

      {error && <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 14, marginBottom: 20 }}>{error}</div>}

      {isMobile ? (
        loading ? (
          <p style={{ color: "#64748b" }}>Загружаем…</p>
        ) : orders.length === 0 ? (
          <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: "48px 24px", textAlign: "center", color: "#94a3b8", fontSize: 14 }}>
            Заказы не найдены
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {orders.map((o) => <OrderMobileCard key={o.id} order={o} />)}
          </div>
        )
      ) : (
        <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
          <div style={{ display: "grid", gridTemplateColumns: GRID, gap: 12, padding: "12px 20px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            <span>№</span>
            <span>Маршрут</span>
            <span>Тариф / вес</span>
            <span>Сумма</span>
            <span>Статус</span>
            <span>Дата</span>
            <span>Действие</span>
          </div>

          {loading ? (
            <div style={{ padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>Загружаем…</div>
          ) : orders.length === 0 ? (
            <div style={{ padding: 48, textAlign: "center", color: "#94a3b8", fontSize: 14 }}>Заказы не найдены</div>
          ) : (
            orders.map((o, idx) => {
              const pkg = o.packages[0];
              const sender = o.parties.find((p) => p.role === "sender");
              const recipient = o.parties.find((p) => p.role === "recipient");
              return (
                <div
                  key={o.id}
                  style={{ display: "grid", gridTemplateColumns: GRID, gap: 12, padding: "14px 20px", borderBottom: idx < orders.length - 1 ? "1px solid #f1f5f9" : "none", alignItems: "center", fontSize: 14 }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "#f8fafc"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = ""; }}
                >
                  <span style={{ fontFamily: "monospace", fontSize: 13, color: "#475569", fontWeight: 600 }}>#{o.id}</span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#0f172a" }}>{o.from_city} → {o.to_city}</div>
                    {sender && <div style={{ fontSize: 11, color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>От: {sender.full_name}</div>}
                    {recipient && <div style={{ fontSize: 11, color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>Кому: {recipient.full_name}</div>}
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: "#0f172a" }}>{o.tariff_name}</div>
                    <div style={{ fontSize: 11, color: "#94a3b8" }}>{pkg ? `${pkg.weight_kg} кг` : "—"}</div>
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>
                    {o.price.toLocaleString()} {o.currency}
                  </div>
                  <div>
                    <StatusBadge status={o.status} />
                  </div>
                  <span style={{ fontSize: 12, color: "#94a3b8" }}>
                    {new Date(o.created_at).toLocaleDateString("ru-KZ")}
                  </span>
                  <Link
                    href={`/dashboard/carrier/orders/${o.id}`}
                    style={{ padding: "6px 12px", borderRadius: 8, border: "none", fontSize: 12, fontWeight: 600, background: "#0f172a", color: "#ffffff", textDecoration: "none", textAlign: "center", fontFamily: "inherit" }}
                  >
                    Открыть
                  </Link>
                </div>
              );
            })
          )}
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
    </>
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
