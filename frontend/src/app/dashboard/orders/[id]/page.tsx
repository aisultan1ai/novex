"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";
import {
  ApiError,
  CANCELLABLE_STATUSES,
  cancelOrder,
  deleteOrderDraft,
  downloadOrderLabel,
  getOrderDraft,
} from "@/lib/api/orders";
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
  out_for_delivery:           "Выезд на доставку",
  in_transit:                 "В пути",
  arrived:                    "Прибыл",
  delivery_failed:            "Попытка не удалась",
  customs_hold:               "Таможня",
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
  out_for_delivery:           { bg: "#dbeafe", color: "#1e40af" },
  in_transit:                 { bg: "#ede9fe", color: "#5b21b6" },
  arrived:                    { bg: "#ede9fe", color: "#5b21b6" },
  delivery_failed:            { bg: "#fef3c7", color: "#92400e" },
  customs_hold:               { bg: "#fef3c7", color: "#92400e" },
  delivered:                  { bg: "#dcfce7", color: "#166534" },
  return_requested:           { bg: "#fee2e2", color: "#991b1b" },
  return_in_progress:         { bg: "#fee2e2", color: "#991b1b" },
  returned:                   { bg: "#f1f5f9", color: "#475569" },
  cancelled:                  { bg: "#fee2e2", color: "#991b1b" },
  return:                     { bg: "#fee2e2", color: "#991b1b" },
};

const CHECKOUT_STATUSES = new Set(["shipment_details_completed", "ready_for_checkout"]);
const PAYMENT_PENDING_STATUSES = new Set(["awaiting_payment", "payment_rejected"]);
const TRACKABLE_STATUSES = new Set(["paid", "sent_to_carrier", "picked_up", "out_for_delivery", "in_transit", "arrived", "delivery_failed", "customs_hold", "delivered"]);
// Label can be downloaded from the point the shipment is registered with the carrier,
// even before tracking events exist (covers manual/queued dispatch states).
const LABEL_STATUSES = new Set([
  "paid", "dispatch_queued", "dispatch_failed", "pending_manual", "pending_manual_dispatch",
  "sent_to_carrier", "picked_up", "in_transit", "arrived", "delivered",
]);

function parseUTC(iso: string): Date {
  return new Date(/[Z+]/.test(iso) ? iso : iso + "Z");
}

function formatDate(iso: string): string {
  return parseUTC(iso).toLocaleDateString("ru-RU", { day: "2-digit", month: "long", year: "numeric" });
}

function formatPrice(price: number, currency: string): string {
  return `${new Intl.NumberFormat("ru-RU").format(price)} ${currency}`;
}

function StatusBadge({ status }: { status: string }) {
  const colors = STATUS_COLORS[status] ?? { bg: "#f1f5f9", color: "#475569" };
  return (
    <span style={{ display: "inline-block", padding: "5px 14px", borderRadius: 999, fontSize: 13, fontWeight: 600, background: colors.bg, color: colors.color }}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function IconArrowLeft() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}

const card = { background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, padding: "20px 24px" };

export default function OrderDetailPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const isMobile = useIsMobile();
  const router = useRouter();
  const params = useParams();
  const draftId = Number(params.id);

  const [order, setOrder] = useState<OrderDraftResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [isCancelling, setIsCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const undoTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push("/login");
  }, [isAuthenticated, authLoading, router]);

  useEffect(() => {
    if (!isAuthenticated || !draftId) return;
    getOrderDraft(draftId)
      .then(setOrder)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.detail : "Не удалось загрузить заказ."))
      .finally(() => setIsLoading(false));
  }, [isAuthenticated, draftId]);

  useEffect(() => {
    return () => { if (undoTimerRef.current) clearTimeout(undoTimerRef.current); };
  }, []);

  const commitDelete = useCallback(async () => {
    setIsDeleting(true);
    try {
      await deleteOrderDraft(draftId);
      router.push("/dashboard/orders");
    } catch {
      setPendingDelete(false);
      setIsDeleting(false);
      setError("Не удалось удалить черновик.");
    }
  }, [draftId, router]);

  function handleDelete() {
    setPendingDelete(true);
    if (undoTimerRef.current) clearTimeout(undoTimerRef.current);
    undoTimerRef.current = setTimeout(() => void commitDelete(), 5000);
  }

  function handleUndoDelete() {
    if (undoTimerRef.current) clearTimeout(undoTimerRef.current);
    setPendingDelete(false);
  }

  async function handleDownloadLabel() {
    setIsDownloading(true);
    setError(null);
    try {
      const blob = await downloadOrderLabel(draftId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `waybill_${draftId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось скачать накладную.");
    } finally {
      setIsDownloading(false);
    }
  }

  async function handleConfirmCancel() {
    const trimmed = cancelReason.trim();
    if (trimmed.length < 3) {
      setCancelError("Укажите причину (минимум 3 символа)");
      return;
    }
    setIsCancelling(true);
    setCancelError(null);
    try {
      const updated = await cancelOrder(draftId, trimmed);
      setOrder(updated);
      setShowCancelModal(false);
      setCancelReason("");
    } catch (err) {
      setCancelError(err instanceof ApiError ? err.detail : "Не удалось отменить заказ.");
    } finally {
      setIsCancelling(false);
    }
  }

  if (authLoading || (!isAuthenticated && !authLoading)) return null;

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <Link href="/dashboard/orders" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 14, color: "#64748b", textDecoration: "none", fontWeight: 500 }}>
          <IconArrowLeft /> Мои заказы
        </Link>
      </div>

      {pendingDelete && (
        <div style={{ marginBottom: 20, padding: "12px 20px", background: "#1e293b", borderRadius: 12, fontSize: 14, color: "#f1f5f9", display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ flex: 1 }}>Черновик #{draftId} будет удалён через 5 секунд…</span>
          <button onClick={handleUndoDelete} style={{ padding: "6px 14px", borderRadius: 8, border: "1px solid #475569", background: "transparent", color: "#f1f5f9", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
            Отменить
          </button>
        </div>
      )}

      {error && (
        <div style={{ marginBottom: 20, background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 12, padding: "14px 20px", color: "#b91c1c", fontSize: 14 }}>
          {error}
        </div>
      )}

      {isLoading ? (
        <>
          <style>{`@keyframes skeleton-pulse { 0%,100%{opacity:1} 50%{opacity:.4} }`}</style>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {[120, 100, 180, 120].map((h, i) => (
              <div key={i} style={{ height: h, borderRadius: 16, background: "#e5e7eb", animation: "skeleton-pulse 1.5s ease infinite", animationDelay: `${i * 0.15}s` }} />
            ))}
          </div>
        </>
      ) : order ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
                <h1 style={{ margin: 0, fontSize: isMobile ? 20 : 28, fontWeight: 800, color: "#111827" }}>Заказ #{order.draft_id}</h1>
                <StatusBadge status={order.status} />
              </div>
              <div style={{ fontSize: 13, color: "#94a3b8" }}>Создан {formatDate(order.created_at)}</div>
            </div>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {CHECKOUT_STATUSES.has(order.status) && (
                <Link href={`/checkout?draftId=${order.draft_id}`} style={{ padding: "10px 20px", borderRadius: 10, background: "#2563EB", color: "#fff", fontSize: 14, fontWeight: 600, textDecoration: "none" }}>
                  Оплатить
                </Link>
              )}
              {PAYMENT_PENDING_STATUSES.has(order.status) && (
                <Link href={`/checkout?draftId=${order.draft_id}`} style={{ padding: "10px 20px", borderRadius: 10, background: "#2563EB", color: "#fff", fontSize: 14, fontWeight: 600, textDecoration: "none" }}>
                  Оплатить
                </Link>
              )}
              {TRACKABLE_STATUSES.has(order.status) && (
                <Link href={`/dashboard/orders/${order.draft_id}/tracking`} style={{ padding: "10px 20px", borderRadius: 10, background: "#ede9fe", color: "#5b21b6", fontSize: 14, fontWeight: 600, textDecoration: "none" }}>
                  Отследить
                </Link>
              )}
              {LABEL_STATUSES.has(order.status) && (
                <button
                  onClick={() => void handleDownloadLabel()}
                  disabled={isDownloading}
                  style={{ padding: "10px 20px", borderRadius: 10, border: "1px solid #e5e7eb", background: "#fff", color: "#111827", fontSize: 14, fontWeight: 600, cursor: isDownloading ? "not-allowed" : "pointer", opacity: isDownloading ? 0.6 : 1, fontFamily: "inherit" }}
                >
                  {isDownloading ? "Скачиваем…" : "Скачать накладную"}
                </button>
              )}
              {order.status === "draft" && !pendingDelete && (
                <button
                  onClick={handleDelete}
                  disabled={isDeleting}
                  style={{ padding: "10px 20px", borderRadius: 10, border: "1px solid #fecaca", background: "#fff", color: "#ef4444", fontSize: 14, fontWeight: 600, cursor: isDeleting ? "not-allowed" : "pointer", opacity: isDeleting ? 0.5 : 1, fontFamily: "inherit" }}
                >
                  Удалить черновик
                </button>
              )}
              {CANCELLABLE_STATUSES.includes(order.status) && (
                <button
                  onClick={() => { setCancelError(null); setShowCancelModal(true); }}
                  style={{ padding: "10px 20px", borderRadius: 10, border: "1px solid #fecaca", background: "#fff", color: "#ef4444", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
                >
                  Отменить заявку
                </button>
              )}
            </div>
          </div>

          {/* Tracking number */}
          {order.tracking_number && (
            <div style={{ ...card, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>Трекинг-номер</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#111827", fontFamily: "monospace", letterSpacing: "0.05em" }}>{order.tracking_number}</div>
              </div>
              <button
                onClick={() => {
                  void navigator.clipboard.writeText(order.tracking_number!);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
                style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 16px", borderRadius: 8, border: "1px solid #e5e7eb", background: copied ? "#f0fdf4" : "#fff", color: copied ? "#16a34a" : "#374151", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", transition: "all 0.15s", whiteSpace: "nowrap" }}
              >
                {copied ? (
                  <>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                    Скопировано
                  </>
                ) : (
                  <>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                    Копировать
                  </>
                )}
              </button>
            </div>
          )}

          {/* Route + carrier */}
          <div style={{ ...card }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 14 }}>Маршрут и тариф</div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 18 }}>
              <span style={{ fontSize: 22, fontWeight: 800, color: "#111827" }}>{order.from_city_snapshot}</span>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
              </svg>
              <span style={{ fontSize: 22, fontWeight: 800, color: "#111827" }}>{order.to_city_snapshot}</span>
            </div>
            <div style={{ display: "flex", gap: 32, flexWrap: "wrap" }}>
              <div>
                <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>Перевозчик</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>{order.carrier_name_snapshot}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>Тариф</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>{order.tariff_name_snapshot}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>Срок доставки</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>{order.eta_days_min_snapshot}-{order.eta_days_max_snapshot} дн.</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>Стоимость</div>
                <div style={{ fontSize: 20, fontWeight: 800, color: "#111827" }}>{formatPrice(order.price_snapshot, order.currency_snapshot)}</div>
              </div>
            </div>
          </div>

          {/* Sender + Recipient */}
          {(order.sender ?? order.recipient) && (
            <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: 16 }}>
              {order.sender && (
                <div style={{ ...card }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>Отправитель</div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: "#111827", marginBottom: 4 }}>{order.sender.full_name}</div>
                  {order.sender.company_name && <div style={{ fontSize: 13, color: "#64748b", marginBottom: 2 }}>{order.sender.company_name}</div>}
                  <div style={{ fontSize: 13, color: "#64748b", marginBottom: 2 }}>{order.sender.phone}</div>
                  {order.sender.email && <div style={{ fontSize: 13, color: "#64748b", marginBottom: 8 }}>{order.sender.email}</div>}
                  <div style={{ borderTop: "1px solid #f1f5f9", paddingTop: 10, marginTop: 8 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: "#475569" }}>{order.sender.city}, {order.sender.country}</div>
                    <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 2 }}>{order.sender.address_line1}</div>
                    {order.sender.address_line2 && <div style={{ fontSize: 13, color: "#94a3b8" }}>{order.sender.address_line2}</div>}
                    {order.sender.postal_code && <div style={{ fontSize: 13, color: "#94a3b8" }}>{order.sender.postal_code}</div>}
                    {order.sender.comment && <div style={{ fontSize: 12, color: "#94a3b8", fontStyle: "italic", marginTop: 4 }}>{order.sender.comment}</div>}
                  </div>
                </div>
              )}
              {order.recipient && (
                <div style={{ ...card }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>Получатель</div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: "#111827", marginBottom: 4 }}>{order.recipient.full_name}</div>
                  {order.recipient.company_name && <div style={{ fontSize: 13, color: "#64748b", marginBottom: 2 }}>{order.recipient.company_name}</div>}
                  <div style={{ fontSize: 13, color: "#64748b", marginBottom: 2 }}>{order.recipient.phone}</div>
                  {order.recipient.email && <div style={{ fontSize: 13, color: "#64748b", marginBottom: 8 }}>{order.recipient.email}</div>}
                  <div style={{ borderTop: "1px solid #f1f5f9", paddingTop: 10, marginTop: 8 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: "#475569" }}>{order.recipient.city}, {order.recipient.country}</div>
                    <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 2 }}>{order.recipient.address_line1}</div>
                    {order.recipient.address_line2 && <div style={{ fontSize: 13, color: "#94a3b8" }}>{order.recipient.address_line2}</div>}
                    {order.recipient.postal_code && <div style={{ fontSize: 13, color: "#94a3b8" }}>{order.recipient.postal_code}</div>}
                    {order.recipient.comment && <div style={{ fontSize: 12, color: "#94a3b8", fontStyle: "italic", marginTop: 4 }}>{order.recipient.comment}</div>}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Packages */}
          {order.packages.length > 0 && (
            <div style={{ ...card }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>
                Посылки · {order.packages.length} шт.
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {order.packages.map((pkg) => (
                  <div key={pkg.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", background: "#f8fafc", borderRadius: 12 }}>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: "#111827", marginBottom: 2 }}>{pkg.description}</div>
                      <div style={{ fontSize: 12, color: "#94a3b8" }}>
                        {pkg.quantity} шт. · {pkg.weight_kg} кг · {pkg.width_cm}×{pkg.height_cm}×{pkg.depth_cm} см
                      </div>
                    </div>
                    {pkg.declared_value != null && (
                      <div style={{ fontSize: 13, color: "#64748b", fontWeight: 500 }}>
                        {formatPrice(pkg.declared_value, pkg.declared_value_currency ?? "")}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Additional services */}
          {(order.call_before_delivery || order.insurance || order.fragile) && (
            <div style={{ ...card }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>Дополнительные услуги</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {order.call_before_delivery && (
                  <span style={{ fontSize: 13, fontWeight: 600, background: "#dbeafe", color: "#1e40af", borderRadius: 999, padding: "5px 14px" }}>Звонок перед доставкой</span>
                )}
                {order.insurance && (
                  <span style={{ fontSize: 13, fontWeight: 600, background: "#dbeafe", color: "#1e40af", borderRadius: 999, padding: "5px 14px" }}>Страховка</span>
                )}
                {order.fragile && (
                  <span style={{ fontSize: 13, fontWeight: 600, background: "#fef3c7", color: "#92400e", borderRadius: 999, padding: "5px 14px" }}>Хрупкий груз</span>
                )}
              </div>
            </div>
          )}
        </div>
      ) : null}

      {showCancelModal && order && (
        <div
          onClick={() => { if (!isCancelling) setShowCancelModal(false); }}
          style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.55)", display: "flex", alignItems: "center", justifyContent: "center", padding: 20, zIndex: 100 }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ background: "#fff", borderRadius: 16, width: "100%", maxWidth: 480, padding: "24px 28px", boxShadow: "0 20px 40px rgba(15,23,42,0.25)" }}
          >
            <h2 style={{ margin: "0 0 8px", fontSize: 20, fontWeight: 800, color: "#111827" }}>
              Отменить заказ #{order.draft_id}?
            </h2>
            {order.status !== "sent_to_carrier" && (
              <p style={{ margin: "0 0 16px", fontSize: 13, color: "#64748b", lineHeight: 1.5 }}>
                Заказ будет отменён. Возврат средств оформит администратор — обычно 3–5 рабочих дней.
              </p>
            )}

            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 6 }}>
              Причина отмены <span style={{ color: "#ef4444" }}>*</span>
            </label>
            <textarea
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              rows={4}
              maxLength={500}
              disabled={isCancelling}
              style={{ width: "100%", padding: "10px 12px", border: "1px solid #e5e7eb", borderRadius: 10, fontSize: 14, fontFamily: "inherit", outline: "none", resize: "vertical", boxSizing: "border-box", color: "#111827", background: "#fff" }}
            />
            <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4, textAlign: "right" }}>
              {cancelReason.length} / 500
            </div>

            {cancelError && (
              <div style={{ marginTop: 12, padding: "10px 14px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 10, fontSize: 13, color: "#b91c1c" }}>
                {cancelError}
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
              <button
                onClick={() => { setShowCancelModal(false); setCancelReason(""); setCancelError(null); }}
                disabled={isCancelling}
                style={{ padding: "10px 20px", borderRadius: 10, border: "1px solid #e5e7eb", background: "#fff", color: "#374151", fontSize: 14, fontWeight: 600, cursor: isCancelling ? "not-allowed" : "pointer", fontFamily: "inherit" }}
              >
                Не отменять
              </button>
              <button
                onClick={() => void handleConfirmCancel()}
                disabled={isCancelling || cancelReason.trim().length < 3}
                style={{ padding: "10px 20px", borderRadius: 10, border: "none", background: "#ef4444", color: "#fff", fontSize: 14, fontWeight: 600, cursor: (isCancelling || cancelReason.trim().length < 3) ? "not-allowed" : "pointer", opacity: (isCancelling || cancelReason.trim().length < 3) ? 0.6 : 1, fontFamily: "inherit" }}
              >
                {isCancelling ? "Отменяем…" : "Отменить заявку"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
