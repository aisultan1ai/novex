"use client";

import { useCallback, useEffect, useState } from "react";

interface PaymentItem {
  id: number;
  order_id: number;
  provider: string;
  method: string;
  status: string;
  amount: number;
  currency: string;
  payment_reference: string | null;
  created_at: string;
}

interface PaymentListResponse {
  items: PaymentItem[];
  total: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

const STATUS_LABELS: Record<string, string> = {
  awaiting_payment: "Ожидает оплаты",
  payment_under_review: "На проверке",
  paid: "Оплачено",
  payment_rejected: "Отклонено",
  cancelled: "Отменён",
  expired: "Истёк",
};

function statusStyle(status: string): React.CSSProperties {
  const map: Record<string, React.CSSProperties> = {
    awaiting_payment: { background: "#fef9c3", color: "#854d0e" },
    payment_under_review: { background: "#dbeafe", color: "#1e40af" },
    paid: { background: "#dcfce7", color: "#166534" },
    payment_rejected: { background: "#fee2e2", color: "#991b1b" },
    cancelled: { background: "#f1f5f9", color: "#475569" },
  };
  return { ...badgeBase, ...(map[status] ?? { background: "#f1f5f9" }) };
}

const badgeBase: React.CSSProperties = {
  padding: "2px 10px",
  borderRadius: 12,
  fontSize: 12,
  fontWeight: 600,
  display: "inline-block",
};

export default function AdminPaymentsPage() {
  const [payments, setPayments] = useState<PaymentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const fetchPayments = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (statusFilter) params.set("status", statusFilter);
    const res = await fetch(`${API_BASE}/api/v1/admin/payments?${params}`, {
      credentials: "include",
    });
    if (res.ok) {
      const data: PaymentListResponse = await res.json();
      setPayments(data.items);
      setTotal(data.total);
    }
    setLoading(false);
  }, [statusFilter, page]);

  useEffect(() => {
    fetchPayments();
  }, [fetchPayments]);

  const handleApprove = async (id: number) => {
    setActionLoading(true);
    setActionMsg(null);
    const res = await fetch(`${API_BASE}/api/v1/admin/payments/${id}/approve`, {
      method: "POST",
      credentials: "include",
    });
    const data = await res.json();
    setActionMsg(res.ok ? data.message : data.detail);
    setActionLoading(false);
    if (res.ok) fetchPayments();
  };

  const handleReject = async (id: number) => {
    if (!rejectReason.trim()) {
      setActionMsg("Укажите причину отклонения");
      return;
    }
    setActionLoading(true);
    setActionMsg(null);
    const res = await fetch(`${API_BASE}/api/v1/admin/payments/${id}/reject`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reject_reason: rejectReason }),
    });
    const data = await res.json();
    setActionMsg(res.ok ? data.message : data.detail);
    setActionLoading(false);
    if (res.ok) {
      setSelectedId(null);
      setRejectReason("");
      fetchPayments();
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 16 }}>Оплаты</h1>

      {/* Filter */}
      <div style={{ marginBottom: 16, display: "flex", gap: 8 }}>
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

      {actionMsg && (
        <div style={styles.msg}>{actionMsg}</div>
      )}

      {/* Table */}
      {loading ? (
        <p style={{ color: "#6b7280" }}>Загрузка...</p>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              {["ID", "Заказ", "Провайдер", "Сумма", "Статус", "Дата", "Действия"].map((h) => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {payments.map((p) => (
              <tr key={p.id} style={styles.tr}>
                <td style={styles.td}>{p.id}</td>
                <td style={styles.td}>
                  <span style={{ fontWeight: 600 }}>#{p.order_id}</span>
                  {p.payment_reference && (
                    <div style={{ fontSize: 11, color: "#9ca3af" }}>{p.payment_reference}</div>
                  )}
                </td>
                <td style={styles.td}>{p.provider}</td>
                <td style={styles.td}>
                  <span style={{ fontWeight: 700 }}>
                    {p.amount.toLocaleString()} {p.currency}
                  </span>
                </td>
                <td style={styles.td}>
                  <span style={statusStyle(p.status)}>
                    {STATUS_LABELS[p.status] ?? p.status}
                  </span>
                </td>
                <td style={styles.td}>
                  {new Date(p.created_at).toLocaleDateString("ru-KZ")}
                </td>
                <td style={styles.td}>
                  {p.status === "payment_under_review" && (
                    <div style={{ display: "flex", gap: 6, flexDirection: "column" }}>
                      <div style={{ display: "flex", gap: 6 }}>
                        <button
                          onClick={() => handleApprove(p.id)}
                          disabled={actionLoading}
                          style={styles.btnApprove}
                        >
                          Подтвердить
                        </button>
                        <button
                          onClick={() => setSelectedId(selectedId === p.id ? null : p.id)}
                          disabled={actionLoading}
                          style={styles.btnReject}
                        >
                          Отклонить
                        </button>
                      </div>
                      {selectedId === p.id && (
                        <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                          <input
                            placeholder="Причина отклонения..."
                            value={rejectReason}
                            onChange={(e) => setRejectReason(e.target.value)}
                            style={styles.input}
                          />
                          <button
                            onClick={() => handleReject(p.id)}
                            disabled={actionLoading}
                            style={styles.btnReject}
                          >
                            OK
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {payments.length === 0 && (
              <tr>
                <td colSpan={7} style={{ ...styles.td, textAlign: "center", color: "#9ca3af" }}>
                  Оплаты не найдены
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}

      {/* Pagination */}
      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          style={styles.pageBtn}
        >
          ← Назад
        </button>
        <span style={{ lineHeight: "32px", fontSize: 13 }}>
          Стр. {page} · Всего {total}
        </span>
        <button
          onClick={() => setPage((p) => p + 1)}
          disabled={payments.length < 20}
          style={styles.pageBtn}
        >
          Вперёд →
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  select: {
    border: "1px solid #e5e7eb",
    borderRadius: 6,
    padding: "6px 12px",
    fontSize: 13,
    outline: "none",
  },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: {
    textAlign: "left",
    padding: "8px 12px",
    borderBottom: "2px solid #e5e7eb",
    fontWeight: 600,
    color: "#374151",
    whiteSpace: "nowrap",
  },
  tr: { borderBottom: "1px solid #f3f4f6" },
  td: { padding: "10px 12px", verticalAlign: "top" },
  btnApprove: {
    background: "#166534",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "5px 10px",
    fontSize: 12,
    cursor: "pointer",
    fontWeight: 600,
  },
  btnReject: {
    background: "#991b1b",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "5px 10px",
    fontSize: 12,
    cursor: "pointer",
    fontWeight: 600,
  },
  input: {
    border: "1px solid #e5e7eb",
    borderRadius: 6,
    padding: "4px 8px",
    fontSize: 12,
    outline: "none",
    minWidth: 180,
  },
  msg: {
    background: "#f0fdf4",
    border: "1px solid #bbf7d0",
    borderRadius: 8,
    padding: "8px 14px",
    fontSize: 13,
    marginBottom: 12,
    color: "#166534",
  },
  pageBtn: {
    border: "1px solid #e5e7eb",
    borderRadius: 6,
    padding: "6px 12px",
    fontSize: 12,
    cursor: "pointer",
    background: "#fff",
  },
};
