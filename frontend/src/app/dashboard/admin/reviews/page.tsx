"use client";

import { useCallback, useEffect, useState } from "react";

import {
  getAdminRatingsSummary,
  listAdminReviews,
  type CarrierRatingSummary,
  type ReviewResponse,
} from "@/lib/api/reviews";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "2-digit", month: "short", year: "numeric" });
}

function Stars({ rating }: { rating: number }) {
  return (
    <span style={{ letterSpacing: 1 }}>
      {"★".repeat(rating)}
      <span style={{ color: "#d1d5db" }}>{"★".repeat(5 - rating)}</span>
    </span>
  );
}

function RatingBar({ avg, count }: { avg: number; count: number }) {
  const pct = (avg / 5) * 100;
  const color = avg >= 4 ? "#16a34a" : avg >= 3 ? "#d97706" : "#dc2626";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{ flex: 1, height: 8, background: "#f1f5f9", borderRadius: 4, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 4, transition: "width 0.4s" }} />
      </div>
      <span style={{ fontSize: 13, fontWeight: 700, color, minWidth: 28 }}>{avg.toFixed(1)}</span>
      <span style={{ fontSize: 12, color: "#94a3b8" }}>{count} отз.</span>
    </div>
  );
}

export default function AdminReviewsPage() {
  const [items, setItems] = useState<ReviewResponse[]>([]);
  const [ratings, setRatings] = useState<CarrierRatingSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterCarrier, setFilterCarrier] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const SIZE = 50;

  const load = useCallback(() => {
    setIsLoading(true);
    Promise.all([
      listAdminReviews({ carrier_code: filterCarrier || undefined, page, size: SIZE }),
      page === 1 ? getAdminRatingsSummary() : Promise.resolve(null),
    ])
      .then(([res, summary]) => {
        setItems(res.items);
        setTotal(res.total);
        if (summary) setRatings(summary);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, [filterCarrier, page]);

  useEffect(() => { load(); }, [load]);

  function handleFilterChange(val: string) {
    setFilterCarrier(val);
    setPage(1);
  }

  const pages = Math.ceil(total / SIZE) || 1;

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28, flexWrap: "wrap", gap: 16 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: "#0B2545" }}>Отзывы</h1>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>
            Оценки клиентов по перевозчикам · {total} отзывов
          </p>
        </div>
        <input
          value={filterCarrier}
          onChange={(e) => handleFilterChange(e.target.value.toUpperCase())}
          placeholder="Фильтр по перевозчику..."
          style={{ padding: "9px 14px", borderRadius: 10, border: "1px solid #E2E8EE", fontSize: 14, width: 220, fontFamily: "inherit" }}
        />
      </div>

      {error && (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 10, padding: "12px 16px", color: "#b91c1c", fontSize: 14, marginBottom: 20 }}>
          {error}
        </div>
      )}

      {/* Ratings summary (only on page 1, no filter) */}
      {ratings.length > 0 && page === 1 && !filterCarrier && (
        <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, padding: "24px 28px", marginBottom: 24 }}>
          <h2 style={{ margin: "0 0 18px", fontSize: 16, fontWeight: 700, color: "#0B2545" }}>Средние оценки</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
            {ratings.map((r) => (
              <div key={r.carrier_code} style={{ border: "1px solid #f1f5f9", borderRadius: 12, padding: "14px 18px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
                  <span style={{ fontSize: 14, fontWeight: 700, color: "#0B2545", fontFamily: "monospace" }}>
                    {r.carrier_code}
                  </span>
                  <span style={{ fontSize: 13, color: "#f59e0b" }}>
                    {"★".repeat(Math.round(r.avg_rating))}
                  </span>
                </div>
                <RatingBar avg={r.avg_rating} count={r.count} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Reviews table */}
      <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "80px 100px 120px 80px 1fr 110px", gap: 12, padding: "12px 24px", background: "#f8fafc", borderBottom: "1px solid #E2E8EE", fontSize: 12, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          <span>ID</span>
          <span>Заказ</span>
          <span>Перевозчик</span>
          <span>Оценка</span>
          <span>Комментарий</span>
          <span>Дата</span>
        </div>

        {isLoading ? (
          <div style={{ padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>Загружаем…</div>
        ) : items.length === 0 ? (
          <div style={{ padding: "48px 24px", textAlign: "center", color: "#64748b", fontSize: 14 }}>
            Отзывов пока нет
          </div>
        ) : (
          items.map((review, idx) => (
            <div
              key={review.id}
              style={{ display: "grid", gridTemplateColumns: "80px 100px 120px 80px 1fr 110px", gap: 12, padding: "14px 24px", borderBottom: idx === items.length - 1 ? "none" : "1px solid #f1f5f9", alignItems: "start" }}
            >
              <span style={{ fontFamily: "monospace", fontSize: 12, color: "#94a3b8" }}>#{review.id}</span>
              <span style={{ fontFamily: "monospace", fontSize: 13, color: "#475569", fontWeight: 600 }}>#{review.order_draft_id}</span>
              <span style={{ fontSize: 13, color: "#0B2545", fontWeight: 500 }}>{review.carrier_code}</span>
              <span style={{ fontSize: 14, color: "#f59e0b" }}>
                <Stars rating={review.rating} />
              </span>
              <span style={{ fontSize: 13, color: "#475569", wordBreak: "break-word" }}>
                {review.comment || <span style={{ color: "#cbd5e1", fontStyle: "italic" }}>без комментария</span>}
              </span>
              <span style={{ fontSize: 12, color: "#94a3b8" }}>{formatDate(review.created_at)}</span>
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 20 }}>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid #E2E8EE", background: "#fff", color: "#475569", fontSize: 13, fontWeight: 500, cursor: page === 1 ? "not-allowed" : "pointer", opacity: page === 1 ? 0.4 : 1, fontFamily: "inherit" }}
          >
            ← Назад
          </button>
          <span style={{ padding: "7px 16px", fontSize: 13, color: "#64748b" }}>{page} / {pages}</span>
          <button
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page === pages}
            style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid #E2E8EE", background: "#fff", color: "#475569", fontSize: 13, fontWeight: 500, cursor: page === pages ? "not-allowed" : "pointer", opacity: page === pages ? 0.4 : 1, fontFamily: "inherit" }}
          >
            Вперёд →
          </button>
        </div>
      )}
    </>
  );
}
