"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { intlLocale, uiLocale } from "@/i18n/runtime";
import { errorMessage, responseToApiError, safeFetch } from "@/lib/api/client";

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

interface ProofItem {
  id: number;
  file_url: string;
  file_name: string;
  file_mime_type: string;
  file_size: number;
  comment: string | null;
  review_status: string;
  reject_reason: string | null;
  created_at: string;
  reviewed_at: string | null;
}

interface PaymentDetail {
  payment: PaymentItem;
  proofs: ProofItem[];
  history: { old_status: string; new_status: string; comment: string | null; created_at: string }[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

// TxStatus enum в backend/app/modules/payments/transaction_models.py:40.
// Все 9 значений покрыты: unpaid и refund_pending обязательны, иначе после
// клиентской отмены (см. cancellations/service.py) админ видит сырой slug.
// Подписи статусов платежа - admin.payments.status.<status>.
const PAYMENT_STATUSES = [
  "unpaid", "awaiting_payment", "payment_under_review", "paid", "payment_rejected",
  "refund_pending", "refunded", "cancelled", "expired",
];

function usePaymentStatusLabel() {
  const t = useTranslations("admin.payments.status");
  return (s: string) => (t.has(s) ? t(s) : s);
}

function statusStyle(status: string): React.CSSProperties {
  const map: Record<string, React.CSSProperties> = {
    unpaid: { background: "#f1f5f9", color: "#475569" },
    awaiting_payment: { background: "#fef9c3", color: "#854d0e" },
    payment_under_review: { background: "#E6EEF7", color: "#1e40af" },
    paid: { background: "#dcfce7", color: "#166534" },
    payment_rejected: { background: "#fee2e2", color: "#991b1b" },
    refund_pending: { background: "#fed7aa", color: "#9a3412" },
    refunded: { background: "#ede9fe", color: "#5b21b6" },
    cancelled: { background: "#f1f5f9", color: "#475569" },
    expired: { background: "#f1f5f9", color: "#475569" },
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

// POST helper for the approve / refund / reject actions: never throws, never
// shows a raw backend / network text, and always returns a Russian message.
async function postPaymentAction(url: string, body?: unknown): Promise<{ ok: boolean; message: string }> {
  try {
    const res = await safeFetch(url, {
      method: "POST",
      credentials: "include",
      ...(body !== undefined
        ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
        : {}),
    });
    if (res.ok) {
      const data = await res.json().catch(() => null);
      return { ok: true, message: (data as { message?: string } | null)?.message ?? (uiLocale() === "kk" ? "Дайын." : "Готово.") };
    }
    return { ok: false, message: (await responseToApiError(res)).detail };
  } catch (err) {
    return { ok: false, message: errorMessage(err, uiLocale() === "kk" ? "Әрекетті орындау мүмкін болмады. Қайталап көріңіз." : "Не удалось выполнить действие. Попробуйте ещё раз.") };
  }
}

function ProofModal({ paymentId, onClose }: { paymentId: number; onClose: () => void }) {
  const t = useTranslations("admin.payments");
  const statusLabel = usePaymentStatusLabel();
  const [detail, setDetail] = useState<PaymentDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    safeFetch(`${API_BASE}/api/v1/admin/payments/${paymentId}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setDetail(d))
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [paymentId]);

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 1000,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#fff", borderRadius: 14, padding: 28, width: "90%", maxWidth: 560,
          maxHeight: "85vh", overflowY: "auto", boxShadow: "0 20px 60px rgba(0,0,0,0.2)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>{t("proofTitle", { id: paymentId })}</h2>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", color: "#5F6E7E", lineHeight: 1 }}
          >
            ×
          </button>
        </div>

        {loading && <p style={{ color: "#5F6E7E", textAlign: "center" }}>{t("loading")}</p>}

        {!loading && detail && (
          <>
            {/* Payment info */}
            <div style={{ background: "#f9fafb", borderRadius: 10, padding: "12px 16px", marginBottom: 20, fontSize: 13 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 16px" }}>
                <div><span style={{ color: "#5F6E7E" }}>{t("order")}</span> <strong>#{detail.payment.order_id}</strong></div>
                <div><span style={{ color: "#5F6E7E" }}>{t("provider")}</span> <strong>{detail.payment.provider}</strong></div>
                <div><span style={{ color: "#5F6E7E" }}>{t("amount")}</span> <strong>{detail.payment.amount.toLocaleString()} {detail.payment.currency}</strong></div>
                <div>
                  <span style={{ color: "#5F6E7E" }}>{t("statusLabel")}</span>{" "}
                  <span style={statusStyle(detail.payment.status)}>{statusLabel(detail.payment.status)}</span>
                </div>
              </div>
            </div>

            {/* Proofs */}
            <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>
              {t("proofs", { n: detail.proofs.length })}
            </h3>
            {detail.proofs.length === 0 ? (
              <p style={{ color: "#9ca3af", fontSize: 13 }}>{t("noProofs")}</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {detail.proofs.map((proof) => (
                  <div
                    key={proof.id}
                    style={{
                      border: "1px solid #E2E8EE", borderRadius: 10, padding: "12px 14px",
                      display: "flex", alignItems: "center", gap: 12,
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {proof.file_name}
                      </div>
                      <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>
                        {(proof.file_size / 1024).toFixed(1)} KB · {new Date(proof.created_at).toLocaleString(intlLocale())}
                      </div>
                      {proof.comment && (
                        <div style={{ fontSize: 12, color: "#374151", marginTop: 4 }}>{proof.comment}</div>
                      )}
                      {proof.review_status === "rejected" && proof.reject_reason && (
                        <div style={{ fontSize: 12, color: "#991b1b", marginTop: 4 }}>{t("rejectReason", { reason: proof.reject_reason })}</div>
                      )}
                    </div>
                    <a
                      href={proof.file_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        background: "#0B2545", color: "#fff", borderRadius: 8, padding: "6px 14px",
                        fontSize: 12, fontWeight: 600, textDecoration: "none", whiteSpace: "nowrap", flexShrink: 0,
                      }}
                    >
                      {t("open")}
                    </a>
                  </div>
                ))}
              </div>
            )}

            {/* History */}
            {detail.history.length > 0 && (
              <>
                <h3 style={{ fontSize: 14, fontWeight: 700, marginTop: 20, marginBottom: 10 }}>{t("history")}</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {detail.history.map((h, i) => (
                    <div key={i} style={{ fontSize: 12, color: "#5F6E7E", display: "flex", gap: 8 }}>
                      <span>{new Date(h.created_at).toLocaleString(intlLocale())}</span>
                      <span>
                        <span style={statusStyle(h.old_status)}>{statusLabel(h.old_status)}</span>
                        {" → "}
                        <span style={statusStyle(h.new_status)}>{statusLabel(h.new_status)}</span>
                      </span>
                      {h.comment && <span>· {h.comment}</span>}
                    </div>
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default function AdminPaymentsPage() {
  const t = useTranslations("admin.payments");
  const statusLabel = usePaymentStatusLabel();
  const [payments, setPayments] = useState<PaymentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [refundId, setRefundId] = useState<number | null>(null);
  const [refundReason, setRefundReason] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [proofPaymentId, setProofPaymentId] = useState<number | null>(null);

  const fetchPayments = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (statusFilter) params.set("status", statusFilter);
    try {
      const res = await safeFetch(`${API_BASE}/api/v1/admin/payments?${params}`, {
        credentials: "include",
      });
      if (res.ok) {
        const data: PaymentListResponse = await res.json();
        setPayments(data.items);
        setTotal(data.total);
      } else {
        setActionMsg((await responseToApiError(res)).detail);
      }
    } catch (err) {
      setActionMsg(errorMessage(err, t("loadFailed")));
    }
    setLoading(false);
  }, [statusFilter, page]);

  useEffect(() => {
    fetchPayments();
  }, [fetchPayments]);

  const handleApprove = async (id: number) => {
    setActionLoading(true);
    setActionMsg(null);
    const result = await postPaymentAction(`${API_BASE}/api/v1/admin/payments/${id}/approve`);
    setActionMsg(result.message);
    setActionLoading(false);
    if (result.ok) {
      setStatusFilter("");
      setPage(1);
    }
  };

  const handleRefund = async (id: number) => {
    if (!refundReason.trim()) {
      setActionMsg(t("refundReasonRequired"));
      return;
    }
    setActionLoading(true);
    setActionMsg(null);
    const result = await postPaymentAction(`${API_BASE}/api/v1/admin/payments/${id}/refund`, { reason: refundReason });
    setActionMsg(result.message);
    setActionLoading(false);
    if (result.ok) {
      setRefundId(null);
      setRefundReason("");
      setStatusFilter("");
      setPage(1);
    }
  };

  const handleReject = async (id: number) => {
    if (!rejectReason.trim()) {
      setActionMsg(t("rejectReasonRequired"));
      return;
    }
    setActionLoading(true);
    setActionMsg(null);
    const result = await postPaymentAction(`${API_BASE}/api/v1/admin/payments/${id}/reject`, { reject_reason: rejectReason });
    setActionMsg(result.message);
    setActionLoading(false);
    if (result.ok) {
      setSelectedId(null);
      setRejectReason("");
      setStatusFilter("");
      setPage(1);
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 16 }}>{t("title")}</h1>

      {/* Filter */}
      <div style={{ marginBottom: 16, display: "flex", gap: 8 }}>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          style={styles.select}
        >
          <option value="">{t("allStatuses")}</option>
          {PAYMENT_STATUSES.map((v) => (
            <option key={v} value={v}>{statusLabel(v)}</option>
          ))}
        </select>
      </div>

      {actionMsg && (
        <div style={styles.msg}>{actionMsg}</div>
      )}

      {/* Table */}
      {loading ? (
        <p style={{ color: "#5F6E7E" }}>{t("loading")}</p>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              {["ID", t("cols.order"), t("cols.provider"), t("cols.amount"), t("cols.status"), t("cols.date"), t("cols.actions")].map((h) => (
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
                    {statusLabel(p.status)}
                  </span>
                </td>
                <td style={styles.td}>
                  {new Date(p.created_at).toLocaleDateString(intlLocale())}
                </td>
                <td style={styles.td}>
                  <div style={{ display: "flex", gap: 6, flexDirection: "column" }}>
                    {/* View proof button - always visible */}
                    <button
                      onClick={() => setProofPaymentId(p.id)}
                      style={styles.btnProof}
                    >
                      {t("proof")}
                    </button>

                    {p.status === "payment_under_review" && (
                      <>
                        <div style={{ display: "flex", gap: 6 }}>
                          <button
                            onClick={() => handleApprove(p.id)}
                            disabled={actionLoading}
                            style={styles.btnApprove}
                          >
                            {t("approve")}
                          </button>
                          <button
                            onClick={() => setSelectedId(selectedId === p.id ? null : p.id)}
                            disabled={actionLoading}
                            style={styles.btnReject}
                          >
                            {t("reject")}
                          </button>
                        </div>
                        {selectedId === p.id && (
                          <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                            <input
                              placeholder={t("rejectPlaceholder")}
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
                      </>
                    )}

                    {p.status === "paid" && (
                      <>
                        <button
                          onClick={() => setRefundId(refundId === p.id ? null : p.id)}
                          disabled={actionLoading}
                          style={styles.btnRefund}
                        >
                          {t("refund")}
                        </button>
                        {refundId === p.id && (
                          <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                            <input
                              placeholder={t("refundPlaceholder")}
                              value={refundReason}
                              onChange={(e) => setRefundReason(e.target.value)}
                              style={styles.input}
                            />
                            <button
                              onClick={() => handleRefund(p.id)}
                              disabled={actionLoading}
                              style={styles.btnRefund}
                            >
                              OK
                            </button>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {payments.length === 0 && (
              <tr>
                <td colSpan={7} style={{ ...styles.td, textAlign: "center", color: "#9ca3af" }}>
                  {t("empty")}
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
          {t("prev")}
        </button>
        <span style={{ lineHeight: "32px", fontSize: 13 }}>
          {t("page", { page, total })}
        </span>
        <button
          onClick={() => setPage((p) => p + 1)}
          disabled={payments.length < 20}
          style={styles.pageBtn}
        >
          {t("next")}
        </button>
      </div>

      {/* Proof modal */}
      {proofPaymentId !== null && (
        <ProofModal paymentId={proofPaymentId} onClose={() => setProofPaymentId(null)} />
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  select: {
    border: "1px solid #E2E8EE",
    borderRadius: 6,
    padding: "6px 12px",
    fontSize: 13,
    outline: "none",
  },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: {
    textAlign: "left",
    padding: "8px 12px",
    borderBottom: "2px solid #E2E8EE",
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
  btnProof: {
    background: "#f3f4f6",
    color: "#374151",
    border: "1px solid #E2E8EE",
    borderRadius: 6,
    padding: "5px 10px",
    fontSize: 12,
    cursor: "pointer",
    fontWeight: 600,
  },
  input: {
    border: "1px solid #E2E8EE",
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
  btnRefund: {
    background: "#5b21b6",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "5px 10px",
    fontSize: 12,
    cursor: "pointer",
    fontWeight: 600,
  },
  pageBtn: {
    border: "1px solid #E2E8EE",
    borderRadius: 6,
    padding: "6px 12px",
    fontSize: 12,
    cursor: "pointer",
    background: "#fff",
  },
};
