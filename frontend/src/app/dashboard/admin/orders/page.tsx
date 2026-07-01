"use client";

import { useEffect, useState, useCallback } from "react";

import {
  listAdminOrders,
  updateOrderStatus,
  getAdminOrderPayments,
  getAdminPayment,
  approveAdminPayment,
  rejectAdminPayment,
} from "@/lib/api/admin";
import type { AdminOrderRow, AdminPaymentDetail } from "@/types/admin";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  shipment_details_completed: "Детали заполнены",
  ready_for_checkout: "Готов к оплате",
  awaiting_payment: "Ожидает оплаты",
  payment_under_review: "Чек на проверке",
  payment_rejected: "Чек отклонён",
  paid: "Оплачен",
  dispatch_queued: "Ожидает отправки",
  dispatch_failed: "Уточняем детали",
  pending_manual: "Передаётся перевозчику",
  pending_manual_dispatch: "Ожидает ручной отправки",
  sent_to_carrier: "Передан курьеру",
  picked_up: "Забран",
  in_transit: "В пути",
  out_for_delivery: "Выезд на доставку",
  arrived: "Прибыл",
  delivered: "Доставлен",
  delivery_failed: "Попытка доставки не удалась",
  return_requested: "Запрос возврата",
  return_in_progress: "Возврат в пути",
  returned: "Возвращён",
  cancelled: "Отменён",
  return: "Возврат",
};

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  draft:                      { bg: "#f1f5f9", color: "#475569" },
  shipment_details_completed: { bg: "#dbeafe", color: "#1e40af" },
  ready_for_checkout:         { bg: "#ede9fe", color: "#5b21b6" },
  awaiting_payment:           { bg: "#fef3c7", color: "#92400e" },
  payment_under_review:       { bg: "#dbeafe", color: "#1e40af" },
  payment_rejected:           { bg: "#fee2e2", color: "#991b1b" },
  paid:                       { bg: "#dcfce7", color: "#166534" },
  sent_to_carrier:            { bg: "#dbeafe", color: "#1e40af" },
  picked_up:                  { bg: "#dbeafe", color: "#1e40af" },
  in_transit:                 { bg: "#ede9fe", color: "#5b21b6" },
  arrived:                    { bg: "#ede9fe", color: "#5b21b6" },
  delivered:                  { bg: "#dcfce7", color: "#166534" },
  cancelled:                  { bg: "#fee2e2", color: "#991b1b" },
  return:                     { bg: "#fee2e2", color: "#991b1b" },
  dispatch_failed:            { bg: "#fee2e2", color: "#991b1b" },
  pending_manual:             { bg: "#fef3c7", color: "#92400e" },
};

const ALL_STATUSES = Object.keys(STATUS_LABELS);

function StatusBadge({ status }: { status: string }) {
  const c = STATUS_COLORS[status] ?? { bg: "#f1f5f9", color: "#475569" };
  return (
    <span style={{ display: "inline-block", padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: c.bg, color: c.color, whiteSpace: "nowrap" }}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function formatPrice(price: number, currency: string) {
  return `${new Intl.NumberFormat("ru-RU").format(price)} ${currency}`;
}

function isImage(mime: string) {
  return mime.startsWith("image/");
}

interface PaymentPanelProps {
  orderId: number;
  onAction: () => void;
}

function PaymentPanel({ orderId, onAction }: PaymentPanelProps) {
  const [detail, setDetail] = useState<AdminPaymentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [showReject, setShowReject] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getAdminOrderPayments(orderId)
      .then(async (res) => {
        if (res.items.length === 0) { setLoading(false); return; }
        const d = await getAdminPayment(res.items[0].id);
        setDetail(d);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [orderId]);

  async function handleApprove() {
    if (!detail) return;
    setActionLoading(true);
    setMsg(null);
    try {
      const res = await approveAdminPayment(detail.payment.id);
      setMsg(res.message);
      onAction();
    } catch (e: unknown) {
      setMsg((e as Error).message);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject() {
    if (!detail || !rejectReason.trim()) { setMsg("Укажите причину отклонения"); return; }
    setActionLoading(true);
    setMsg(null);
    try {
      const res = await rejectAdminPayment(detail.payment.id, rejectReason);
      setMsg(res.message);
      setShowReject(false);
      setRejectReason("");
      onAction();
    } catch (e: unknown) {
      setMsg((e as Error).message);
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) return <div style={ps.wrap}><span style={{ color: "#64748b", fontSize: 13 }}>Загружаем платёж…</span></div>;
  if (error) return <div style={ps.wrap}><span style={{ color: "#dc2626", fontSize: 13 }}>{error}</span></div>;
  if (!detail) return <div style={ps.wrap}><span style={{ color: "#94a3b8", fontSize: 13 }}>Платёж не найден</span></div>;

  const { payment, proofs } = detail;
  const canAct = payment.status === "payment_under_review";

  return (
    <div style={ps.wrap}>
      {/* Payment summary */}
      <div style={ps.row}>
        <span style={ps.label}>Сумма</span>
        <span style={ps.val}>{formatPrice(payment.amount, payment.currency)}</span>
        <span style={{ ...ps.label, marginLeft: 24 }}>Статус платежа</span>
        <StatusBadge status={payment.status} />
        <span style={{ ...ps.label, marginLeft: 24 }}>Метод</span>
        <span style={ps.val}>{payment.method}</span>
        <span style={{ ...ps.label, marginLeft: 24 }}>Создан</span>
        <span style={ps.val}>{new Date(payment.created_at).toLocaleString("ru-RU")}</span>
      </div>

      {/* Proofs */}
      {proofs.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>Чеки / доказательства оплаты</div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {proofs.map((proof) => {
              const fileUrl = `${API_BASE}${proof.file_url}`;
              return (
                <div key={proof.id} style={ps.proofCard}>
                  {isImage(proof.file_mime_type) ? (
                    <a href={fileUrl} target="_blank" rel="noreferrer">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={fileUrl}
                        alt={proof.file_name}
                        style={{ width: 140, height: 100, objectFit: "cover", borderRadius: 6, display: "block", border: "1px solid #e5e7eb" }}
                      />
                    </a>
                  ) : (
                    <a href={fileUrl} target="_blank" rel="noreferrer" style={ps.fileLink}>
                      📄 {proof.file_name}
                    </a>
                  )}
                  <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>
                    {new Date(proof.created_at).toLocaleDateString("ru-RU")}
                  </div>
                  {proof.reject_reason && (
                    <div style={{ fontSize: 11, color: "#dc2626", marginTop: 2 }}>Причина: {proof.reject_reason}</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Feedback message */}
      {msg && (
        <div style={{ marginTop: 10, padding: "7px 12px", borderRadius: 8, background: "#f0fdf4", border: "1px solid #bbf7d0", fontSize: 13, color: "#166534" }}>
          {msg}
        </div>
      )}

      {/* Actions */}
      {canAct && (
        <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "flex-start", flexWrap: "wrap" }}>
          <button onClick={handleApprove} disabled={actionLoading} style={ps.btnApprove}>
            ✓ Подтвердить оплату
          </button>
          <button onClick={() => setShowReject((v) => !v)} disabled={actionLoading} style={ps.btnReject}>
            ✕ Отклонить
          </button>
          {showReject && (
            <div style={{ display: "flex", gap: 6, width: "100%", marginTop: 4 }}>
              <input
                placeholder="Причина отклонения..."
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                style={ps.input}
              />
              <button onClick={handleReject} disabled={actionLoading} style={ps.btnReject}>
                Отправить
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const ps: Record<string, React.CSSProperties> = {
  wrap: { padding: "14px 20px 16px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb" },
  row:  { display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" },
  label: { fontSize: 12, color: "#94a3b8", fontWeight: 600 },
  val:   { fontSize: 13, color: "#0f172a", fontWeight: 600 },
  proofCard: { display: "flex", flexDirection: "column" },
  fileLink: { fontSize: 13, color: "#1d4ed8", textDecoration: "underline" },
  btnApprove: { padding: "7px 14px", borderRadius: 8, border: "none", background: "#166534", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" },
  btnReject:  { padding: "7px 14px", borderRadius: 8, border: "none", background: "#991b1b", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" },
  input: { border: "1px solid #e5e7eb", borderRadius: 8, padding: "6px 10px", fontSize: 13, outline: "none", minWidth: 220, fontFamily: "inherit" },
};

const PAYMENT_STATUSES = new Set(["payment_under_review", "payment_rejected", "awaiting_payment", "paid"]);

export default function AdminOrdersPage() {
  const [orders, setOrders] = useState<AdminOrderRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editStatus, setEditStatus] = useState("");
  const [saving, setSaving] = useState(false);

  const [paymentOpenId, setPaymentOpenId] = useState<number | null>(null);

  const SIZE = 20;

  const load = useCallback(() => {
    setIsLoading(true);
    listAdminOrders({ page, size: SIZE, status: statusFilter || undefined })
      .then((res) => { setOrders(res.items); setTotal(res.total); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, [page, statusFilter]);

  useEffect(() => { void load(); }, [load]);

  async function saveStatus(orderId: number) {
    setSaving(true);
    try {
      await updateOrderStatus(orderId, editStatus);
      setEditingId(null);
      void load();
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  const totalPages = Math.ceil(total / SIZE);

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0f172a" }}>Заказы</h2>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>Все заказы платформы · {total} всего</p>
        </div>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #e5e7eb", background: "#ffffff", fontSize: 14, cursor: "pointer", fontFamily: "inherit", color: "#0f172a" }}
        >
          <option value="">Все статусы</option>
          {ALL_STATUSES.map((s) => (
            <option key={s} value={s}>{STATUS_LABELS[s]}</option>
          ))}
        </select>
      </div>

      {error && <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 14, marginBottom: 20 }}>{error}</div>}

      <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "70px 160px 1fr 150px 110px 150px 160px", gap: 12, padding: "12px 20px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          <span>№</span>
          <span>Клиент</span>
          <span>Маршрут</span>
          <span>Перевозчик</span>
          <span>Сумма</span>
          <span>Статус</span>
          <span>Действия</span>
        </div>

        {isLoading ? (
          <div style={{ padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>Загружаем…</div>
        ) : orders.length === 0 ? (
          <div style={{ padding: 48, textAlign: "center", color: "#94a3b8", fontSize: 14 }}>Заказов не найдено</div>
        ) : (
          orders.map((order, idx) => {
            const isEditing = editingId === order.id;
            const isPaymentOpen = paymentOpenId === order.id;
            const hasPayment = PAYMENT_STATUSES.has(order.status);
            const isLast = idx === orders.length - 1;

            return (
              <div key={order.id}>
                <div
                  style={{ display: "grid", gridTemplateColumns: "70px 160px 1fr 150px 110px 150px 160px", gap: 12, padding: "14px 20px", borderBottom: isLast && !isEditing && !isPaymentOpen ? "none" : "1px solid #f1f5f9", alignItems: "center", fontSize: 14 }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "#f8fafc"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = ""; }}
                >
                  <span style={{ fontFamily: "monospace", fontSize: 13, color: "#475569", fontWeight: 600 }}>#{order.id}</span>

                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#0f172a", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {order.user_name || order.user_email || "-"}
                    </div>
                    <div style={{ fontSize: 11, color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {order.user_email}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#0f172a" }}>{order.from_city} → {order.to_city}</div>
                    <div style={{ fontSize: 11, color: "#94a3b8" }}>{new Date(order.created_at).toLocaleDateString("ru-RU")}</div>
                    {order.tracking_number && (
                      <div style={{ fontSize: 11, color: "#1d4ed8", fontFamily: "monospace", marginTop: 2 }}>{order.tracking_number}</div>
                    )}
                  </div>

                  <div style={{ fontSize: 13, color: "#475569" }}>{order.carrier_name}</div>

                  <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>{formatPrice(order.price, order.currency)}</div>

                  <StatusBadge status={order.status} />

                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {hasPayment && (
                      <button
                        onClick={() => setPaymentOpenId(isPaymentOpen ? null : order.id)}
                        style={{
                          padding: "6px 10px", borderRadius: 8, border: "none", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
                          background: isPaymentOpen ? "#1d4ed8" : "#dbeafe",
                          color: isPaymentOpen ? "#ffffff" : "#1e40af",
                        }}
                      >
                        {isPaymentOpen ? "Скрыть" : "💳 Чек"}
                      </button>
                    )}
                    <button
                      onClick={() => { setEditingId(isEditing ? null : order.id); setEditStatus(order.status); }}
                      style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#ffffff", color: "#0f172a", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
                    >
                      Статус
                    </button>
                  </div>
                </div>

                {/* Payment panel */}
                {isPaymentOpen && (
                  <PaymentPanel
                    orderId={order.id}
                    onAction={() => { void load(); setPaymentOpenId(null); }}
                  />
                )}

                {/* Status edit panel */}
                {isEditing && (
                  <div style={{ padding: "12px 20px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 13, color: "#64748b", fontWeight: 500 }}>Новый статус:</span>
                    <select
                      value={editStatus}
                      onChange={(e) => setEditStatus(e.target.value)}
                      style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 13, fontFamily: "inherit", background: "#ffffff", color: "#0f172a" }}
                    >
                      {ALL_STATUSES.map((s) => (
                        <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                      ))}
                    </select>
                    <button
                      onClick={() => void saveStatus(order.id)}
                      disabled={saving}
                      style={{ padding: "8px 16px", borderRadius: 8, border: "none", background: "#0f172a", color: "#ffffff", fontSize: 13, fontWeight: 600, cursor: saving ? "not-allowed" : "pointer", opacity: saving ? 0.7 : 1, fontFamily: "inherit" }}
                    >
                      {saving ? "Сохраняем..." : "Сохранить"}
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      style={{ padding: "8px 16px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#ffffff", color: "#64748b", fontSize: 13, cursor: "pointer", fontFamily: "inherit" }}
                    >
                      Отмена
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 24 }}>
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
