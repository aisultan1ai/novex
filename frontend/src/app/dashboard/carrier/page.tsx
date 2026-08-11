"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { getCarrierMe, getCarrierReviewsSummary, type CarrierReviewsSummary } from "@/lib/api/carrier";
import type { CarrierMeResponse } from "@/types/carrier";

export default function CarrierOverviewPage() {
  const [data, setData] = useState<CarrierMeResponse | null>(null);
  const [reviews, setReviews] = useState<CarrierReviewsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCarrierMe()
      .then(setData)
      .catch((e: Error) => setError(e.message));
    // Отзывы - некритичная секция; ошибка не должна ломать всю страницу.
    getCarrierReviewsSummary()
      .then(setReviews)
      .catch(() => setReviews({ carrier_code: "", avg_rating: null, count: 0 }));
  }, []);

  if (error) {
    return (
      <div style={{ padding: "16px 20px", borderRadius: 12, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 14 }}>
        {error}
      </div>
    );
  }

  if (!data) {
    return <div style={{ padding: 48, textAlign: "center", color: "#94a3b8" }}>Загружаем...</div>;
  }

  const { carrier, integration } = data;

  return (
    <>
      {/* Status banner */}
      <div style={{ background: integration.is_active ? "#f0fdf4" : "#fffbeb", border: `1px solid ${integration.is_active ? "#bbf7d0" : "#fde68a"}`, borderRadius: 12, padding: "14px 20px", marginBottom: 24, display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 10, height: 10, borderRadius: "50%", background: integration.is_active ? "#16a34a" : "#d97706", flexShrink: 0 }} />
        <span style={{ fontSize: 14, fontWeight: 600, color: integration.is_active ? "#166534" : "#92400e" }}>
          {integration.is_active ? "Интеграция активна" : "Интеграция не настроена - обратитесь к администратору Novex"}
        </span>
      </div>

      {/* Carrier info card */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
        <div style={{ background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 14, padding: "20px 24px" }}>
          <p style={{ margin: "0 0 12px", fontSize: 12, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>Перевозчик</p>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{ width: 48, height: 48, borderRadius: 10, background: "#eef2ff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22, fontWeight: 800, color: "#4338ca", flexShrink: 0 }}>
              {carrier.name[0]}
            </div>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: "#0E1826" }}>{carrier.name}</div>
              <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                <span style={{ fontFamily: "monospace", fontSize: 12, color: "#94a3b8", background: "#f1f5f9", padding: "2px 8px", borderRadius: 6 }}>{carrier.code}</span>
                <span style={{ fontSize: 12, padding: "2px 8px", borderRadius: 999, background: carrier.is_active ? "#dcfce7" : "#f1f5f9", color: carrier.is_active ? "#166534" : "#94a3b8", fontWeight: 600 }}>
                  {carrier.is_active ? "Активен" : "Неактивен"}
                </span>
              </div>
            </div>
          </div>
          {reviews && (
            <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid #f1f5f9", display: "flex", alignItems: "center", gap: 10 }}>
              {reviews.count > 0 && reviews.avg_rating != null ? (
                <>
                  <div style={{ display: "flex", gap: 2 }}>
                    {[1, 2, 3, 4, 5].map((s) => (
                      <span key={s} style={{ fontSize: 16, color: s <= Math.round(reviews.avg_rating!) ? "#f59e0b" : "#E2E8EE", lineHeight: 1 }}>★</span>
                    ))}
                  </div>
                  <span style={{ fontSize: 15, fontWeight: 700, color: "#0B2545" }}>{reviews.avg_rating.toFixed(1)}</span>
                  <span style={{ fontSize: 12, color: "#94a3b8" }}>· {reviews.count} {reviews.count === 1 ? "отзыв" : reviews.count < 5 ? "отзыва" : "отзывов"}</span>
                </>
              ) : (
                <span style={{ fontSize: 12, color: "#94a3b8" }}>Отзывов пока нет</span>
              )}
            </div>
          )}
          {carrier.description && <p style={{ margin: "14px 0 0", fontSize: 13, color: "#64748b" }}>{carrier.description}</p>}
        </div>

        <div style={{ background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 14, padding: "20px 24px" }}>
          <p style={{ margin: "0 0 12px", fontSize: 12, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>Статус подключения</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <Row label="Push URL (ваш)" value={integration.push_url || "не задан"} mono missing={!integration.push_url} />
            <Row label="Webhook secret" value={integration.webhook_secret ? "••••••••••••" : "не задан"} missing={!integration.webhook_secret} />
            <Row label="Retry" value={`${integration.retry_count} раз`} />
            <Row label="Timeout" value={`${integration.timeout_seconds} сек`} />
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
        {[
          { href: "/dashboard/carrier/integration", title: "Настройка интеграции", desc: "Методы подключения, ключи HMAC, тесты", color: "#4338ca" },
          { href: "/dashboard/carrier/docs", title: "API Документация", desc: "Форматы запросов, примеры кода, трекинг", color: "#0891b2" },
        ].map(({ href, title, desc, color }) => (
          <Link
            key={href}
            href={href}
            style={{ background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 14, padding: "20px 22px", textDecoration: "none", display: "block", transition: "border-color 0.15s" }}
          >
            <div style={{ width: 36, height: 36, borderRadius: 8, background: `${color}18`, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 12 }}>
              <div style={{ width: 10, height: 10, borderRadius: "50%", background: color }} />
            </div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#0E1826", marginBottom: 4 }}>{title}</div>
            <div style={{ fontSize: 13, color: "#64748b" }}>{desc}</div>
          </Link>
        ))}
      </div>
    </>
  );
}

function Row({ label, value, mono, missing }: { label: string; value: string; mono?: boolean; missing?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
      <span style={{ fontSize: 13, color: "#64748b", flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: 13, fontFamily: mono ? "monospace" : "inherit", color: missing ? "#f97316" : "#0E1826", fontWeight: 500, wordBreak: "break-all", textAlign: "right" }}>
        {value}
      </span>
    </div>
  );
}
