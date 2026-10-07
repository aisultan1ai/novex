"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { getOrderDraft } from "@/lib/api/orders";
import { getOrderTracking } from "@/lib/api/tracking";
import { createReview, getOrderReview, type ReviewResponse } from "@/lib/api/reviews";
import { TrackingTimeline } from "@/components/orders/tracking-timeline";
import type { TrackingEvent } from "@/types/tracking";
import { errorMessage } from "@/lib/api/client";

const REVIEWABLE_STATUSES = new Set(["delivered", "returned"]);

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
      setError(errorMessage(e, "Не удалось отправить отзыв"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, padding: "28px 32px", maxWidth: 640, marginTop: 24, boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
      <h3 style={{ margin: "0 0 16px", fontSize: 18, fontWeight: 700, color: "#0E1826" }}>
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
          borderRadius: 10,
          border: "1.5px solid #E2E8EE",
          font: "400 14px/1.5 Inter Variable, sans-serif",
          resize: "vertical",
          boxSizing: "border-box",
          marginBottom: 12,
          fontFamily: "inherit",
          outline: "none",
          color: "#0E1826",
        }}
      />
      {error && (
        <div style={{ color: "#B91C1C", font: "400 13px/1.4 Inter Variable, sans-serif", marginBottom: 10 }}>{error}</div>
      )}
      <button
        onClick={handleSubmit}
        disabled={submitting || rating === 0}
        style={{
          background: submitting || rating === 0 ? "#E2E8EE" : "#0B2545",
          color: submitting || rating === 0 ? "#9CA3AF" : "#fff",
          border: "none",
          borderRadius: 10,
          padding: "10px 24px",
          font: "600 14px/1 Inter Variable, sans-serif",
          cursor: submitting || rating === 0 ? "not-allowed" : "pointer",
          fontFamily: "inherit",
          transition: "background 0.15s",
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
  const [carrierCode, setCarrierCode] = useState<string | null>(null);
  const [orderStatus, setOrderStatus] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState<ReviewResponse | null>(null);

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
        setCarrierCode(trackingRes.carrier_code);
        setOrderStatus(draftRes.status);
        if (existingReview) setReview(existingReview);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, [isAuthenticated, draftId]);

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

      <div style={{ marginBottom: 28 }}>
        <h1 style={{ margin: 0, font: "700 28px/1.2 'Space Grotesk Variable', 'Inter Variable', sans-serif", color: "#0E1826", letterSpacing: "-0.02em" }}>
          Отслеживание заказа
        </h1>
        <p style={{ margin: "4px 0 0", font: "400 14px/1 Inter Variable, sans-serif", color: "#5F6E7E" }}>
          Заказ #{draftId}
        </p>
      </div>

      {error && (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 12, padding: "14px 20px", color: "#b91c1c", fontSize: 14, marginBottom: 20 }}>
          {error}
        </div>
      )}

      {isLoading ? (
        <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>
          Загружаем историю…
        </div>
      ) : events.length === 0 ? (
        <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, padding: "64px 24px", textAlign: "center" }}>
          <div style={{ marginBottom: 12 }}><IconPackage /></div>
          <p style={{ fontSize: 16, fontWeight: 700, margin: "0 0 8px", color: "#0E1826" }}>
            История отслеживания пуста
          </p>
          <p style={{ margin: 0, fontSize: 14, color: "#64748b" }}>
            События появятся после оплаты и обработки заказа
          </p>
        </div>
      ) : (
        <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, padding: "32px 40px", maxWidth: 640, boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
          <TrackingTimeline events={events} carrierCode={carrierCode} />
        </div>
      )}

      {canReview && !review && (
        <ReviewForm orderId={draftId} onSubmitted={(r) => setReview(r)} />
      )}

      {review && (
        <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, padding: "24px 32px", maxWidth: 640, marginTop: 24, boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <h3 style={{ margin: 0, font: "700 16px/1 Inter Variable, sans-serif", color: "#0E1826" }}>Ваш отзыв</h3>
            <span style={{ font: "600 11px/1 Inter Variable, sans-serif", color: "#065F46", background: "#D1FAE5", border: "1px solid #A7F3D0", borderRadius: 999, padding: "3px 10px" }}>
              Отправлен
            </span>
          </div>
          <div style={{ display: "flex", gap: 4, marginBottom: review.comment ? 12 : 0 }}>
            {[1,2,3,4,5].map((s) => (
              <span key={s} style={{ fontSize: 26, color: s <= review.rating ? "#f59e0b" : "#E2E8EE" }}>★</span>
            ))}
          </div>
          {review.comment && (
            <p style={{ margin: 0, fontSize: 14, color: "#475569", lineHeight: 1.6, borderTop: "1px solid #f1f5f9", paddingTop: 12 }}>
              {review.comment}
            </p>
          )}
          <div style={{ marginTop: 10, fontSize: 12, color: "#94a3b8" }}>
            {new Date(review.created_at).toLocaleString("ru-RU", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })}
          </div>
        </div>
      )}
    </>
  );
}
