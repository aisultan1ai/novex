"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { downloadOrderLabel, getOrderDraft } from "@/lib/api/orders";
import { getOrderTracking } from "@/lib/api/tracking";
import { createReview, getOrderReview, type ReviewResponse } from "@/lib/api/reviews";
import type { TrackingEvent } from "@/types/tracking";

const STATUS_LABELS: Record<string, string> = {
  draft:                      "Черновик",
  shipment_details_completed: "Детали заполнены",
  ready_for_checkout:         "Готов к оплате",
  awaiting_payment:           "Ожидает оплаты",
  payment_under_review:       "Чек на проверке",
  payment_rejected:           "Чек отклонён",
  paid:                       "Оплата подтверждена",
  dispatch_queued:            "Ожидает отправки",
  dispatch_failed:            "Уточняем детали",
  pending_manual:             "Передаётся перевозчику",
  pending_manual_dispatch:    "Ожидает ручной отправки",
  sent_to_carrier:            "Передан перевозчику",
  picked_up:                  "Забран перевозчиком",
  in_transit:                 "В пути",
  out_for_delivery:           "Выезд на доставку",
  arrived:                    "Прибыл в пункт выдачи",
  delivered:                  "Доставлен",
  delivery_failed:            "Попытка доставки не удалась",
  return_requested:           "Запрос возврата",
  return_in_progress:         "Возврат в пути",
  returned:                   "Возвращён",
  return:                     "Возврат",
  customs_hold:               "Задержан на таможне",
  cancelled:                  "Отменён",
};


const STATUS_COLORS: Record<string, { dot: string; line: string }> = {
  paid:             { dot: "#16a34a", line: "#bbf7d0" },
  sent_to_carrier:  { dot: "#2563eb", line: "#bfdbfe" },
  picked_up:        { dot: "#2563eb", line: "#bfdbfe" },
  in_transit:       { dot: "#7c3aed", line: "#ddd6fe" },
  out_for_delivery: { dot: "#7c3aed", line: "#ddd6fe" },
  arrived:          { dot: "#7c3aed", line: "#ddd6fe" },
  delivered:        { dot: "#16a34a", line: "#bbf7d0" },
  delivery_failed:  { dot: "#dc2626", line: "#fecaca" },
  returned:         { dot: "#dc2626", line: "#fecaca" },
  return:           { dot: "#dc2626", line: "#fecaca" },
  cancelled:        { dot: "#dc2626", line: "#fecaca" },
  customs_hold:     { dot: "#d97706", line: "#fde68a" },
};

const REVIEWABLE_STATUSES = new Set(["delivered", "return", "returned"]);

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function StarRating({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  const [hovered, setHovered] = useState(0);
  return (
    <div style={{ display: "flex", gap: 4 }}>
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onClick={() => onChange(star)}
          onMouseEnter={() => setHovered(star)}
          onMouseLeave={() => setHovered(0)}
          style={{
            background: "none",
            border: "none",
            fontSize: 28,
            cursor: "pointer",
            color: star <= (hovered || value) ? "#f59e0b" : "#d1d5db",
            padding: "0 2px",
            lineHeight: 1,
          }}
        >
          ★
        </button>
      ))}
    </div>
  );
}

function ReviewForm({
  orderId,
  onSubmitted,
}: {
  orderId: number;
  onSubmitted: (review: ReviewResponse) => void;
}) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    if (rating === 0) { setError("Выберите оценку от 1 до 5"); return; }
    setSubmitting(true);
    setError(null);
    try {
      const review = await createReview(orderId, { rating, comment: comment.trim() || null });
      onSubmitted(review);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Не удалось отправить отзыв");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: "28px 32px", maxWidth: 640, marginTop: 24 }}>
      <h3 style={{ margin: "0 0 16px", fontSize: 18, fontWeight: 700, color: "#0f172a" }}>
        Оцените доставку
      </h3>
      <div style={{ marginBottom: 14 }}>
        <StarRating value={rating} onChange={setRating} />
      </div>
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Напишите отзыв (необязательно)..."
        maxLength={1000}
        style={{
          width: "100%",
          minHeight: 90,
          padding: "12px 14px",
          borderRadius: 12,
          border: "1px solid #cbd5e1",
          fontSize: 14,
          resize: "vertical",
          boxSizing: "border-box",
          marginBottom: 12,
          fontFamily: "inherit",
        }}
      />
      {error && (
        <div style={{ color: "#b91c1c", fontSize: 13, marginBottom: 10 }}>{error}</div>
      )}
      <button
        onClick={handleSubmit}
        disabled={submitting || rating === 0}
        style={{
          background: "#0f172a",
          color: "#fff",
          border: "none",
          borderRadius: 10,
          padding: "10px 24px",
          fontSize: 14,
          fontWeight: 600,
          cursor: submitting || rating === 0 ? "not-allowed" : "pointer",
          opacity: submitting || rating === 0 ? 0.6 : 1,
        }}
      >
        {submitting ? "Отправка..." : "Отправить отзыв"}
      </button>
    </div>
  );
}

function IconArrowLeft() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}

function IconPackage() {
  return (
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
      <line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
  );
}

export default function OrderTrackingPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const params = useParams();
  const draftId = Number(params.id);

  const [events, setEvents] = useState<TrackingEvent[]>([]);
  const [orderStatus, setOrderStatus] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push("/login");
  }, [isAuthenticated, authLoading, router]);

  useEffect(() => {
    if (!isAuthenticated || !draftId) return;
    Promise.all([
      getOrderTracking(draftId),
      getOrderDraft(draftId),
      getOrderReview(draftId),
    ])
      .then(([trackingRes, draftRes, existingReview]) => {
        setEvents(trackingRes.events);
        setOrderStatus(draftRes.status);
        if (existingReview) setReview(existingReview);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, [isAuthenticated, draftId]);

  async function handleDownloadLabel() {
    setIsDownloading(true);
    try {
      const blob = await downloadOrderLabel(draftId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `novex_label_${draftId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Не удалось скачать накладную");
    } finally {
      setIsDownloading(false);
    }
  }

  if (authLoading || (!isAuthenticated && !authLoading)) return null;

  const canReview = orderStatus !== null && REVIEWABLE_STATUSES.has(orderStatus);

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <Link
          href={`/dashboard/orders/${draftId}`}
          style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 14, color: "#64748b", textDecoration: "none", fontWeight: 500 }}
        >
          <IconArrowLeft /> Назад к заказу
        </Link>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: "#0f172a" }}>
            Отслеживание заказа
          </h1>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>
            Заказ #{draftId}
          </p>
        </div>
        <button
          onClick={handleDownloadLabel}
          disabled={isDownloading}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "10px 20px",
            borderRadius: 10,
            border: "1px solid #cbd5e1",
            background: "#fff",
            color: "#0f172a",
            fontSize: 14,
            fontWeight: 600,
            cursor: isDownloading ? "not-allowed" : "pointer",
            opacity: isDownloading ? 0.6 : 1,
          }}
        >
          {isDownloading ? "Скачиваем..." : "⬇ Скачать накладную"}
        </button>
      </div>

      {error && (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 12, padding: "14px 20px", color: "#b91c1c", fontSize: 14, marginBottom: 20 }}>
          {error}
        </div>
      )}

      {isLoading ? (
        <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>
          Загружаем историю…
        </div>
      ) : events.length === 0 ? (
        <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: "64px 24px", textAlign: "center" }}>
          <div style={{ marginBottom: 12 }}><IconPackage /></div>
          <p style={{ fontSize: 16, fontWeight: 700, margin: "0 0 8px", color: "#0f172a" }}>
            История отслеживания пуста
          </p>
          <p style={{ margin: 0, fontSize: 14, color: "#64748b" }}>
            События появятся после оплаты и обработки заказа
          </p>
        </div>
      ) : (
        <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: "32px 40px", maxWidth: 640 }}>
          {events.map((event, idx) => {
            const colors = STATUS_COLORS[event.status] ?? { dot: "#94a3b8", line: "#e5e7eb" };
            const isLast = idx === events.length - 1;
            return (
              <div key={event.id} style={{ display: "flex", gap: 16, paddingBottom: isLast ? 0 : 20 }}>
                {/* dot + line */}
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
                  <div style={{ width: 14, height: 14, borderRadius: "50%", background: colors.dot, boxShadow: `0 0 0 4px ${colors.line}`, flexShrink: 0, marginTop: 3 }} />
                  {!isLast && (
                    <div style={{ width: 2, flex: 1, background: "#e5e7eb", marginTop: 6, marginBottom: 6, minHeight: 24 }} />
                  )}
                </div>
                {/* content */}
                <div style={{ flex: 1, paddingBottom: isLast ? 0 : 4 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a", marginBottom: 2 }}>
                    {STATUS_LABELS[event.status] ?? event.status}
                  </div>
                  {event.description && (
                    <div style={{ fontSize: 13, color: "#475569", marginBottom: 2 }}>{event.description}</div>
                  )}
                  {event.location && (
                    <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 2 }}>{event.location}</div>
                  )}
                  <div style={{ fontSize: 12, color: "#94a3b8" }}>{formatDateTime(event.occurred_at)}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {canReview && !review && (
        <ReviewForm orderId={draftId} onSubmitted={(r) => setReview(r)} />
      )}

      {review && (
        <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: "24px 32px", maxWidth: 640, marginTop: 24 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#0f172a" }}>Ваш отзыв</h3>
            <span style={{ fontSize: 11, fontWeight: 600, color: "#16a34a", background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 20, padding: "3px 10px" }}>
              Отправлен
            </span>
          </div>
          <div style={{ display: "flex", gap: 4, marginBottom: review.comment ? 12 : 0 }}>
            {[1,2,3,4,5].map((s) => (
              <span key={s} style={{ fontSize: 26, color: s <= review.rating ? "#f59e0b" : "#e5e7eb" }}>★</span>
            ))}
          </div>
          {review.comment && (
            <p style={{ margin: 0, fontSize: 14, color: "#475569", lineHeight: 1.6, borderTop: "1px solid #f1f5f9", paddingTop: 12 }}>
              {review.comment}
            </p>
          )}
          <div style={{ marginTop: 10, fontSize: 12, color: "#94a3b8" }}>
            {formatDateTime(review.created_at)}
          </div>
        </div>
      )}
    </>
  );
}
