"use client";

import { memo, useCallback, useEffect, useMemo, useState } from "react";

import {
  listAdminOrders,
  updateOrderStatus,
  getAdminOrder,
  getAdminOrderTracking,
  getAdminOrderPayments,
  getAdminPayment,
  approveAdminPayment,
  rejectAdminPayment,
  type AdminTrackingResponse,
} from "@/lib/api/admin";
import { TrackingTimeline } from "@/components/orders/tracking-timeline";
import ExportXlsxButton from "@/components/ui/ExportXlsxButton";
import {
  adminApproveCancellation,
  adminRejectCancellation,
  adminRetryApiCancellation,
} from "@/lib/api/cancellations";
import {
  ORDER_STATUS_LABELS,
  ORDER_STATUSES,
  orderStatusColors,
  orderStatusLabel,
} from "@/lib/status-labels";
import type { AdminOrderRow, AdminOrderDetail, AdminPaymentDetail } from "@/types/admin";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

// Кроме канонического списка используем как есть - админский селект статусов
// должен покрывать все возможные варианты.
const ALL_STATUSES = ORDER_STATUSES;
const STATUS_LABELS = ORDER_STATUS_LABELS;

function StatusBadge({ status, cancellationSource }: { status: string; cancellationSource?: string | null }) {
  const c = orderStatusColors(status);
  let label = orderStatusLabel(status);
  if (status === "cancelled" && cancellationSource) {
    const suffix =
      cancellationSource === "customer_cancel" ? "клиентом"
      : cancellationSource === "admin" ? "администратором"
      : cancellationSource === "system_worker" ? "системой"
      : null;
    if (suffix) label = `Отменён ${suffix}`;
  }
  return (
    <span style={{ display: "inline-block", padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: c.bg, color: c.color, whiteSpace: "nowrap" }}>
      {label}
    </span>
  );
}

function formatPrice(price: number, currency: string) {
  return `${new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(price)} ${currency}`;
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
                        style={{ width: 140, height: 100, objectFit: "cover", borderRadius: 6, display: "block", border: "1px solid #E2E8EE" }}
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

const ROLE_LABELS: Record<string, string> = { sender: "Отправитель", recipient: "Получатель" };
const SHIPMENT_TYPE_LABELS: Record<string, string> = { parcel: "Посылка", document: "Документ" };

function OrderDetailPanel({ orderId, onCancellationResolved }: { orderId: number; onCancellationResolved?: () => void }) {
  const [detail, setDetail] = useState<AdminOrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [cancelBusy, setCancelBusy] = useState<"approve" | "reject" | "retry" | null>(null);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [cancelMsg, setCancelMsg] = useState<string | null>(null);

  const [tracking, setTracking] = useState<AdminTrackingResponse | null>(null);
  const [trackingOpen, setTrackingOpen] = useState(false);

  const reload = useCallback(() => {
    setLoading(true);
    getAdminOrder(orderId)
      .then(setDetail)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
    // Трекинг качаем параллельно — необязателен для отрисовки остальной панели.
    getAdminOrderTracking(orderId).then(setTracking).catch(() => setTracking(null));
  }, [orderId]);

  useEffect(() => { reload(); }, [reload]);

  async function handleApproveCancellation(requestId: number) {
    if (!window.confirm("Подтвердить отмену? Заказ будет переведён в статус «Отменён», комиссия сторнируется, платежи — в refund_pending.")) return;
    setCancelBusy("approve");
    setCancelMsg(null);
    try {
      await adminApproveCancellation(requestId);
      reload();
      onCancellationResolved?.();
    } catch (e) {
      setCancelMsg(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setCancelBusy(null);
    }
  }

  async function handleRejectCancellation(requestId: number) {
    const trimmed = rejectReason.trim();
    if (trimmed.length < 3) {
      setCancelMsg("Причина обязательна (минимум 3 символа)");
      return;
    }
    setCancelBusy("reject");
    setCancelMsg(null);
    try {
      await adminRejectCancellation(requestId, trimmed);
      setRejectOpen(false);
      setRejectReason("");
      reload();
      onCancellationResolved?.();
    } catch (e) {
      setCancelMsg(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setCancelBusy(null);
    }
  }

  async function handleRetryCancellation(requestId: number) {
    setCancelBusy("retry");
    setCancelMsg(null);
    try {
      await adminRetryApiCancellation(requestId);
      reload();
      onCancellationResolved?.();
    } catch (e) {
      setCancelMsg(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setCancelBusy(null);
    }
  }

  if (loading) return <div style={dp.wrap}><span style={{ color: "#64748b", fontSize: 13 }}>Загружаем детали…</span></div>;
  if (error)   return <div style={dp.wrap}><span style={{ color: "#dc2626", fontSize: 13 }}>{error}</span></div>;
  if (!detail) return null;

  const sender    = detail.parties.find((p) => p.role === "sender");
  const recipient = detail.parties.find((p) => p.role === "recipient");
  const cReq      = detail.cancellation_request;
  const canRetry  = cReq && (cReq.carrier_code === "cse" || cReq.carrier_code === "exline");

  const sourceLabel =
    detail.cancellation?.source === "customer_cancel" ? "клиентом"
    : detail.cancellation?.source === "admin" ? "администратором"
    : "системой";

  return (
    <div style={dp.wrap}>
      {/* ── Активная заявка на отмену ───────────────────────────────── */}
      {cReq && cReq.status === "pending" && (
        <div style={{ marginBottom: 16, padding: "14px 18px", background: "#FFFBEB", border: "1px solid #FDE68A", borderRadius: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 10 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#92400E" }}>
              Клиент запросил отмену заказа
            </div>
            <div style={{ fontSize: 12, color: "#B45309" }}>
              {new Date(cReq.created_at).toLocaleString("ru-RU")}
            </div>
          </div>
          <div style={{ fontSize: 13, color: "#78350F", marginBottom: 10 }}>
            <b>Причина:</b> {cReq.reason}
          </div>
          {cReq.api_attempted && cReq.api_error && (
            <div style={{ marginBottom: 10, padding: "8px 12px", background: "#FEF3C7", borderRadius: 8, fontSize: 12, color: "#92400E" }}>
              <b>API-отмена пробовалась:</b>{" "}
              <span style={{ fontFamily: "monospace" }}>{cReq.api_error}</span>
            </div>
          )}
          {cancelMsg && (
            <div style={{ marginBottom: 10, padding: "7px 12px", background: "#FEE2E2", border: "1px solid #FCA5A5", borderRadius: 8, fontSize: 12, color: "#991B1B" }}>
              {cancelMsg}
            </div>
          )}
          {!rejectOpen ? (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button
                onClick={() => handleApproveCancellation(cReq.id)}
                disabled={cancelBusy !== null}
                style={{ padding: "8px 16px", borderRadius: 8, border: "none", background: "#16A34A", color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", opacity: cancelBusy ? 0.6 : 1 }}
              >
                {cancelBusy === "approve" ? "Подтверждаем…" : "Подтвердить отмену"}
              </button>
              {canRetry && (
                <button
                  onClick={() => handleRetryCancellation(cReq.id)}
                  disabled={cancelBusy !== null}
                  style={{ padding: "8px 16px", borderRadius: 8, border: "1px solid #C7D2FE", background: "#EEF2FF", color: "#4338CA", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", opacity: cancelBusy ? 0.6 : 1 }}
                >
                  {cancelBusy === "retry" ? "Пробуем…" : "Повторить API-отмену"}
                </button>
              )}
              <button
                onClick={() => setRejectOpen(true)}
                disabled={cancelBusy !== null}
                style={{ padding: "8px 16px", borderRadius: 8, border: "1px solid #FECACA", background: "#fff", color: "#DC2626", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", opacity: cancelBusy ? 0.6 : 1 }}
              >
                Отклонить
              </button>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Причина отклонения (клиент увидит этот текст) — минимум 3 символа"
                rows={2}
                style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #E2E8EE", fontSize: 13, fontFamily: "inherit", outline: "none", resize: "vertical" }}
              />
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => handleRejectCancellation(cReq.id)}
                  disabled={cancelBusy !== null}
                  style={{ padding: "8px 16px", borderRadius: 8, border: "none", background: "#DC2626", color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", opacity: cancelBusy ? 0.6 : 1 }}
                >
                  {cancelBusy === "reject" ? "Отправляем…" : "Отправить отказ"}
                </button>
                <button
                  onClick={() => { setRejectOpen(false); setRejectReason(""); setCancelMsg(null); }}
                  disabled={cancelBusy !== null}
                  style={{ padding: "8px 16px", borderRadius: 8, border: "1px solid #E2E8EE", background: "#fff", color: "#64748B", fontSize: 13, fontWeight: 500, cursor: "pointer", fontFamily: "inherit" }}
                >
                  Отмена
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Отмена (показываем сразу вверху, если есть) ─────────────── */}
      {detail.cancellation && (
        <div style={{ marginBottom: 16, padding: "14px 18px", background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, marginBottom: 6 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#991B1B" }}>
              Заказ отменён {sourceLabel}
            </div>
            <div style={{ fontSize: 12, color: "#7F1D1D" }}>
              {new Date(detail.cancellation.cancelled_at).toLocaleString("ru-RU")}
            </div>
          </div>
          <div style={{ fontSize: 13, color: "#7F1D1D", lineHeight: 1.5 }}>
            <b>Причина:</b> {detail.cancellation.reason}
          </div>
          {detail.cancellation.cancelled_by_email && (
            <div style={{ fontSize: 12, color: "#7F1D1D", marginTop: 4 }}>
              Инициатор: {detail.cancellation.cancelled_by_name || detail.cancellation.cancelled_by_email}
            </div>
          )}
          {detail.refund_status === "refunded" && (
            <div style={{ marginTop: 10, padding: "6px 12px", background: "#DCFCE7", borderRadius: 6, fontSize: 12, fontWeight: 600, color: "#166534", display: "inline-block" }}>
              ✓ Возврат оформлен
            </div>
          )}
        </div>
      )}

      {/* ── Метаданные ──────────────────────────────────────────────── */}
      <div style={dp.section}>
        <div style={dp.sectionTitle}>Информация о заказе</div>
        <div style={dp.grid3}>
          <dp.Field label="Тип отправления"  value={SHIPMENT_TYPE_LABELS[detail.shipment_type] ?? detail.shipment_type} />
          <dp.Field label="Перевозчик"        value={detail.carrier_name} />
          <dp.Field label="Тариф"             value={detail.tariff_name} />
          <dp.Field label="Срок доставки"     value={`${detail.eta_days_min}-${detail.eta_days_max} раб. дней`} />
          <dp.Field label="Создан"            value={new Date(detail.created_at).toLocaleString("ru-RU")} />
          <dp.Field label="Обновлён"          value={new Date(detail.updated_at).toLocaleString("ru-RU")} />
        </div>
      </div>

      {/* ── Трекинг ─────────────────────────────────────────────────── */}
      {(detail.tracking_number || detail.carrier_tracking_number) && (
        <div style={dp.section}>
          <div style={dp.sectionTitle}>Трекинг</div>
          <div style={dp.grid3}>
            {detail.tracking_number && (
              <dp.Field label="Внутренний трек-номер" value={detail.tracking_number} mono />
            )}
            {detail.carrier_tracking_number && (
              <dp.Field label="Трек-номер перевозчика" value={detail.carrier_tracking_number} mono />
            )}
          </div>
        </div>
      )}

      {/* ── Данные перевозчика ───────────────────────────────────────── */}
      {(detail.carrier_barcode || detail.carrier_tracking_number) && (
        <div style={dp.section}>
          <div style={dp.sectionTitle}>Данные перевозчика (ответ API)</div>
          <div style={dp.grid3}>
            {detail.carrier_code && (
              <dp.Field label="Перевозчик" value={detail.carrier_code} />
            )}
            {detail.carrier_tracking_number && (
              <dp.Field label="Номер заказа (наш orderno)" value={detail.carrier_tracking_number} mono />
            )}
            {detail.carrier_barcode && (
              <dp.Field label="Штрих-код (barcode)" value={detail.carrier_barcode} mono />
            )}
          </div>
        </div>
      )}

      {/* ── Финансовая разбивка ─────────────────────────────────────── */}
      <div style={dp.section}>
        <div style={dp.sectionTitle}>Финансовая разбивка</div>
        <div style={dp.grid3}>
          <dp.Field label="Оплатил клиент" value={formatPrice(detail.price, detail.currency)} />
          <dp.Field label="Перевозчику" value={formatPrice(detail.carrier_price, detail.currency)} />
          <dp.Field
            label="Прибыль Novex"
            value={formatPrice(detail.markup_amount, detail.currency)}
          />
        </div>
      </div>

      {/* ── Маршрут ─────────────────────────────────────────────────── */}
      <div style={dp.section}>
        <div style={dp.sectionTitle}>Маршрут</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {[sender, recipient].map((party) => {
            if (!party) return null;
            return (
              <div key={party.role} style={dp.partyCard}>
                <div style={dp.partyRole}>{ROLE_LABELS[party.role] ?? party.role}</div>
                <div style={dp.partyName}>{party.full_name}</div>
                <div style={dp.partyLine}>{party.phone}</div>
                <div style={dp.partyLine}>{party.city}</div>
                <div style={dp.partyLine}>{party.address_line1}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Посылки ─────────────────────────────────────────────────── */}
      {detail.packages.length > 0 && (
        <div style={dp.section}>
          <div style={dp.sectionTitle}>Посылки ({detail.packages.length})</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {detail.packages.map((pkg, i) => (
              <div key={i} style={dp.packageRow}>
                <span style={{ fontSize: 13, color: "#0B2545", fontWeight: 500, flex: 1 }}>{pkg.description}</span>
                <span style={dp.pkgBadge}>{pkg.quantity} шт</span>
                <span style={dp.pkgBadge}>{pkg.weight_kg} кг</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── История статусов (аккордеон) ─────────────────────────────── */}
      {tracking && tracking.events.length > 0 && (
        <div style={{ ...dp.section, borderBottom: "none" }}>
          <button
            type="button"
            onClick={() => setTrackingOpen((v) => !v)}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 8,
              padding: "10px 14px",
              background: "#ffffff",
              border: "1px solid #E2E8EE",
              borderRadius: 10,
              cursor: "pointer",
              fontFamily: "inherit",
              textAlign: "left",
            }}
          >
            <span style={{ fontSize: 13, fontWeight: 700, color: "#0B2545" }}>
              История статусов ({tracking.events.length})
            </span>
            <span style={{ fontSize: 14, color: "#94a3b8", transform: trackingOpen ? "rotate(180deg)" : "rotate(0)", transition: "transform 0.15s" }}>
              ▾
            </span>
          </button>
          {trackingOpen && (
            <div style={{ padding: "16px 4px 4px" }}>
              <TrackingTimeline events={tracking.events} carrierCode={tracking.carrier_code} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Helpers inside OrderDetailPanel namespace ──────────────────────────────
const dp = {
  wrap:        { padding: "16px 20px 4px", background: "#f8fafc", borderBottom: "1px solid #E2E8EE" } as React.CSSProperties,
  section:     { borderBottom: "1px solid #f1f5f9", paddingBottom: 16, marginBottom: 16 } as React.CSSProperties,
  sectionTitle:{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase" as const, letterSpacing: "0.05em", marginBottom: 10 },
  grid3:       { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "10px 24px" } as React.CSSProperties,
  partyCard:   { background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 10, padding: "12px 14px" } as React.CSSProperties,
  partyRole:   { fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase" as const, letterSpacing: "0.06em", marginBottom: 6 },
  partyName:   { fontSize: 14, fontWeight: 700, color: "#0B2545", marginBottom: 4 },
  partyLine:   { fontSize: 13, color: "#475569" },
  packageRow:  { display: "flex", alignItems: "center", gap: 10, background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 8, padding: "10px 14px" } as React.CSSProperties,
  pkgBadge:   { fontSize: 12, fontWeight: 600, color: "#1e40af", background: "#E6EEF7", padding: "2px 9px", borderRadius: 999 },
  Field: function({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
    return (
      <div>
        <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600, marginBottom: 2 }}>{label}</div>
        <div style={{ fontSize: 13, color: "#0B2545", fontWeight: 600, fontFamily: mono ? "monospace" : "inherit" }}>{value}</div>
      </div>
    );
  },
};

const ps: Record<string, React.CSSProperties> = {
  wrap: { padding: "14px 20px 16px", background: "#f8fafc", borderBottom: "1px solid #E2E8EE" },
  row:  { display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" },
  label: { fontSize: 12, color: "#94a3b8", fontWeight: 600 },
  val:   { fontSize: 13, color: "#0B2545", fontWeight: 600 },
  proofCard: { display: "flex", flexDirection: "column" },
  fileLink: { fontSize: 13, color: "#0E2E5C", textDecoration: "underline" },
  btnApprove: { padding: "7px 14px", borderRadius: 8, border: "none", background: "#166534", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" },
  btnReject:  { padding: "7px 14px", borderRadius: 8, border: "none", background: "#991b1b", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" },
  input: { border: "1px solid #E2E8EE", borderRadius: 8, padding: "6px 10px", fontSize: 13, outline: "none", minWidth: 220, fontFamily: "inherit" },
};

const PAYMENT_STATUSES = new Set(["payment_under_review", "payment_rejected", "awaiting_payment", "paid"]);

// ── Row component (memoised) ────────────────────────────────────────────────
// Extracted so a click on one row's panel-toggle only re-renders that row.
// Previously every state change (editing/payment/detail toggled on any row)
// re-rendered all N rows because the whole list was inlined in the parent.
//
// Edit-related props are passed as `undefined` when the row is not being
// edited so React.memo's shallow compare treats them as stable across
// typing/selection on the currently-edited row.
type OrderRowProps = {
  order: AdminOrderRow;
  isLast: boolean;
  isEditing: boolean;
  isPaymentOpen: boolean;
  isDetailOpen: boolean;
  hasPayment: boolean;
  editStatus?: string;
  saving?: boolean;
  onOpenPayment: (id: number) => void;
  onOpenDetail: (id: number) => void;
  onStartEdit: (id: number, currentStatus: string) => void;
  onCancelEdit: () => void;
  onChangeEditStatus?: (status: string) => void;
  onSaveStatus?: (id: number) => void;
  onPaymentAction: () => void;
};

const OrderRow = memo(function OrderRow({
  order,
  isLast,
  isEditing,
  isPaymentOpen,
  isDetailOpen,
  hasPayment,
  editStatus,
  saving,
  onOpenPayment,
  onOpenDetail,
  onStartEdit,
  onCancelEdit,
  onChangeEditStatus,
  onSaveStatus,
  onPaymentAction,
}: OrderRowProps) {
  return (
    <div>
      <div
        style={{ display: "grid", gridTemplateColumns: "70px 160px 1fr 150px 110px 150px 160px", gap: 12, padding: "14px 20px", borderBottom: isLast && !isEditing && !isPaymentOpen && !isDetailOpen ? "none" : "1px solid #f1f5f9", alignItems: "center", fontSize: 14 }}
        onMouseEnter={(e) => { e.currentTarget.style.background = "#f8fafc"; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = ""; }}
      >
        <span style={{ fontFamily: "monospace", fontSize: 13, color: "#475569", fontWeight: 600 }}>#{order.id}</span>

        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#0B2545", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {order.user_name || order.user_email || "-"}
          </div>
          <div style={{ fontSize: 11, color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {order.user_email}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#0B2545" }}>{order.from_city} → {order.to_city}</div>
          <div style={{ fontSize: 11, color: "#94a3b8" }}>{new Date(order.created_at).toLocaleDateString("ru-RU")}</div>
          {order.tracking_number && (
            <div style={{ fontSize: 11, color: "#0E2E5C", fontFamily: "monospace", marginTop: 2 }}>{order.tracking_number}</div>
          )}
          {order.carrier_barcode && order.carrier_barcode !== order.carrier_tracking_number && (
            <div style={{ fontSize: 11, color: "#94a3b8", fontFamily: "monospace" }} title="Штрих-код перевозчика">ШК: {order.carrier_barcode}</div>
          )}
        </div>

        <div style={{ fontSize: 13, color: "#475569" }}>{order.carrier_name}</div>

        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#0B2545" }} title="Оплатил клиент">{formatPrice(order.price, order.currency)}</div>
          {order.markup_amount > 0 && (
            <div style={{ fontSize: 11, color: "#94a3b8" }} title={`Перевозчику ${formatPrice(order.carrier_price, order.currency)} · Наценка ${formatPrice(order.markup_amount, order.currency)}`}>
              {formatPrice(order.carrier_price, order.currency)} + {formatPrice(order.markup_amount, order.currency)}
            </div>
          )}
        </div>

        <div
          style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 4 }}
          title={order.cancellation?.reason ? `Причина: ${order.cancellation.reason}` : undefined}
        >
          <StatusBadge status={order.status} cancellationSource={order.cancellation?.source} />
          {order.has_pending_cancellation && (
            <span
              title="Клиент запросил отмену — откройте детали"
              style={{
                fontSize: 10, fontWeight: 700, letterSpacing: "0.03em",
                padding: "2px 8px", borderRadius: 999,
                background: "#FEF3C7", color: "#92400E",
                textTransform: "uppercase",
              }}
            >
              Заявка на отмену
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {hasPayment && (
            <button
              onClick={() => onOpenPayment(order.id)}
              style={{
                padding: "6px 10px", borderRadius: 8, border: "none", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
                background: isPaymentOpen ? "#0E2E5C" : "#E6EEF7",
                color: isPaymentOpen ? "#ffffff" : "#1e40af",
              }}
            >
              {isPaymentOpen ? "Скрыть" : "💳 Чек"}
            </button>
          )}
          <button
            onClick={() => onOpenDetail(order.id)}
            style={{
              padding: "6px 10px", borderRadius: 8, border: "none", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
              background: isDetailOpen ? "#0B2545" : "#f1f5f9",
              color: isDetailOpen ? "#ffffff" : "#0B2545",
            }}
          >
            {isDetailOpen ? "Скрыть" : "Детали"}
          </button>
          <button
            onClick={() => onStartEdit(order.id, order.status)}
            style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #E2E8EE", background: "#ffffff", color: "#0B2545", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
          >
            Статус
          </button>
        </div>
      </div>

      {isPaymentOpen && (
        <PaymentPanel orderId={order.id} onAction={onPaymentAction} />
      )}

      {isDetailOpen && <OrderDetailPanel orderId={order.id} onCancellationResolved={onPaymentAction} />}

      {isEditing && (
        <div style={{ padding: "12px 20px", background: "#f8fafc", borderBottom: "1px solid #E2E8EE", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, color: "#64748b", fontWeight: 500 }}>Новый статус:</span>
          <select
            value={editStatus ?? order.status}
            onChange={(e) => onChangeEditStatus?.(e.target.value)}
            style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #E2E8EE", fontSize: 13, fontFamily: "inherit", background: "#ffffff", color: "#0B2545" }}
          >
            {ALL_STATUSES.map((s) => (
              <option key={s} value={s}>{STATUS_LABELS[s]}</option>
            ))}
          </select>
          <button
            onClick={() => onSaveStatus?.(order.id)}
            disabled={saving}
            style={{ padding: "8px 16px", borderRadius: 8, border: "none", background: "#0B2545", color: "#ffffff", fontSize: 13, fontWeight: 600, cursor: saving ? "not-allowed" : "pointer", opacity: saving ? 0.7 : 1, fontFamily: "inherit" }}
          >
            {saving ? "Сохраняем..." : "Сохранить"}
          </button>
          <button
            onClick={onCancelEdit}
            style={{ padding: "8px 16px", borderRadius: 8, border: "1px solid #E2E8EE", background: "#ffffff", color: "#64748b", fontSize: 13, cursor: "pointer", fontFamily: "inherit" }}
          >
            Отмена
          </button>
        </div>
      )}
    </div>
  );
});

export default function AdminOrdersPage() {
  const [orders, setOrders] = useState<AdminOrderRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [barcodeQuery, setBarcodeQuery] = useState("");
  const [barcodeInput, setBarcodeInput] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editStatus, setEditStatus] = useState("");
  const [saving, setSaving] = useState(false);

  const [paymentOpenId, setPaymentOpenId] = useState<number | null>(null);
  const [detailOpenId, setDetailOpenId] = useState<number | null>(null);

  const SIZE = 20;

  const load = useCallback(() => {
    setIsLoading(true);
    listAdminOrders({
      page,
      size: SIZE,
      status: statusFilter || undefined,
      barcode: barcodeQuery.trim() || undefined,
    })
      .then((res) => { setOrders(res.items); setTotal(res.total); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, [page, statusFilter, barcodeQuery]);

  useEffect(() => { void load(); }, [load]);

  // Stable callbacks for row-level actions so React.memo on OrderRow can
  // skip re-render of untouched rows. All setters returned by useState are
  // already stable; the wrappers below only depend on `load` / `editStatus`
  // where needed.
  const togglePayment = useCallback((id: number) => {
    setPaymentOpenId((cur) => (cur === id ? null : id));
  }, []);
  const toggleDetail = useCallback((id: number) => {
    setDetailOpenId((cur) => (cur === id ? null : id));
  }, []);
  const startEdit = useCallback((id: number, currentStatus: string) => {
    setEditingId((cur) => (cur === id ? null : id));
    setEditStatus(currentStatus);
  }, []);
  const cancelEdit = useCallback(() => setEditingId(null), []);
  const changeEditStatus = useCallback((s: string) => setEditStatus(s), []);
  const saveStatus = useCallback(async (orderId: number) => {
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
  }, [editStatus, load]);
  const paymentAction = useCallback(() => {
    void load();
    setPaymentOpenId(null);
  }, [load]);

  const totalPages = useMemo(() => Math.ceil(total / SIZE), [total]);

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0B2545" }}>Заказы</h2>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>Все заказы платформы · {total} всего</p>
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <form
            onSubmit={(e) => { e.preventDefault(); setBarcodeQuery(barcodeInput); setPage(1); }}
            style={{ display: "flex", gap: 6 }}
          >
            <input
              type="text"
              placeholder="Поиск по ШК / трек-номеру"
              value={barcodeInput}
              onChange={(e) => setBarcodeInput(e.target.value)}
              style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #E2E8EE", background: "#ffffff", fontSize: 14, fontFamily: "inherit", color: "#0B2545", minWidth: 240, outline: "none" }}
            />
            {barcodeQuery && (
              <button
                type="button"
                onClick={() => { setBarcodeInput(""); setBarcodeQuery(""); setPage(1); }}
                style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #E2E8EE", background: "#ffffff", fontSize: 14, cursor: "pointer", fontFamily: "inherit", color: "#64748b" }}
                title="Сбросить поиск"
              >
                ×
              </button>
            )}
          </form>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #E2E8EE", background: "#ffffff", fontSize: 14, cursor: "pointer", fontFamily: "inherit", color: "#0B2545" }}
          >
            <option value="">Все статусы</option>
            {ALL_STATUSES.map((s) => (
              <option key={s} value={s}>{STATUS_LABELS[s]}</option>
            ))}
          </select>
          <ExportXlsxButton
            endpoint="/admin/orders/export"
            query={new URLSearchParams({
              ...(statusFilter ? { status: statusFilter } : {}),
              ...(barcodeQuery.trim() ? { barcode: barcodeQuery.trim() } : {}),
            }).toString()}
          />
        </div>
      </div>

      {error && <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 14, marginBottom: 20 }}>{error}</div>}

      <div style={{ background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 16, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "70px 160px 1fr 150px 110px 150px 160px", gap: 12, padding: "12px 20px", background: "#f8fafc", borderBottom: "1px solid #E2E8EE", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
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
            return (
              <OrderRow
                key={order.id}
                order={order}
                isLast={idx === orders.length - 1}
                isEditing={isEditing}
                isPaymentOpen={paymentOpenId === order.id}
                isDetailOpen={detailOpenId === order.id}
                hasPayment={PAYMENT_STATUSES.has(order.status)}
                editStatus={isEditing ? editStatus : undefined}
                saving={isEditing ? saving : undefined}
                onOpenPayment={togglePayment}
                onOpenDetail={toggleDetail}
                onStartEdit={startEdit}
                onCancelEdit={cancelEdit}
                onChangeEditStatus={isEditing ? changeEditStatus : undefined}
                onSaveStatus={isEditing ? saveStatus : undefined}
                onPaymentAction={paymentAction}
              />
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
              style={{ width: 36, height: 36, borderRadius: 8, border: "1px solid #E2E8EE", background: p === page ? "#0B2545" : "#ffffff", color: p === page ? "#ffffff" : "#0B2545", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
            >
              {p}
            </button>
          ))}
        </div>
      )}
    </>
  );
}
