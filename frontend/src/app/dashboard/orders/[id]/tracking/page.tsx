"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { getOrderTracking } from "@/lib/api/tracking";
import type { TrackingEvent } from "@/types/tracking";

const STATUS_LABELS: Record<string, string> = {
  paid:             "Оплата подтверждена",
  awaiting_payment: "Ожидание оплаты",
  sent_to_carrier:  "Передан перевозчику",
  picked_up:        "Забран перевозчиком",
  in_transit:       "В пути",
  out_for_delivery: "Выезд на доставку",
  arrived:          "Прибыл в пункт выдачи",
  delivered:        "Доставлен",
  delivery_failed:  "Попытка доставки не удалась",
  returned:         "Возврат",
  customs_hold:     "Задержан на таможне",
  cancelled:        "Отменён",
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
  cancelled:        { dot: "#dc2626", line: "#fecaca" },
  customs_hold:     { dot: "#d97706", line: "#fde68a" },
};

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
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
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push("/login");
  }, [isAuthenticated, authLoading, router]);

  useEffect(() => {
    if (!isAuthenticated || !draftId) return;
    getOrderTracking(draftId)
      .then((res) => setEvents(res.events))
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, [isAuthenticated, draftId]);

  if (authLoading || (!isAuthenticated && !authLoading)) return null;

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <Link
          href="/dashboard/orders"
          style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 14, color: "#64748b", textDecoration: "none", fontWeight: 500 }}
        >
          <IconArrowLeft /> Назад к заказам
        </Link>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: "#0f172a" }}>
            Отслеживание заказа
          </h1>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>
            Заказ #{draftId}
          </p>
        </div>
      </div>

      {isLoading ? (
        <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>
          Загружаем историю…
        </div>
      ) : error ? (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 16, padding: "20px 24px", color: "#b91c1c", fontSize: 14 }}>
          {error}
        </div>
      ) : events.length === 0 ? (
        <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: "64px 24px", textAlign: "center" }}>
          <div style={{ marginBottom: 12 }}><IconPackage /></div>
          <p style={{ fontSize: 16, fontWeight: 700, margin: "0 0 8px", color: "#0f172a" }}>
            История отслеживания пуста
          </p>
          <p style={{ margin: 0, fontSize: 14, color: "#64748b" }}>
            Событий пока нет — они появятся после оплаты и обработки заказа
          </p>
        </div>
      ) : (
        <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: "32px 40px", maxWidth: 640 }}>
          <div style={{ position: "relative" }}>
            {events.slice().reverse().map((event, idx) => {
              const colors = STATUS_COLORS[event.status] ?? { dot: "#94a3b8", line: "#e5e7eb" };
              const isLast = idx === events.length - 1;
              return (
                <div key={event.id} style={{ display: "flex", gap: 20, position: "relative" }}>
                  {/* Timeline line + dot */}
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
                    <div
                      style={{
                        width: 14,
                        height: 14,
                        borderRadius: "50%",
                        background: colors.dot,
                        boxShadow: `0 0 0 4px ${colors.line}`,
                        flexShrink: 0,
                        marginTop: 3,
                      }}
                    />
                    {!isLast && (
                      <div style={{ width: 2, flex: 1, background: "#e5e7eb", marginTop: 6, marginBottom: 6, minHeight: 24 }} />
                    )}
                  </div>

                  {/* Content */}
                  <div style={{ paddingBottom: isLast ? 0 : 28, flex: 1 }}>
                    <div style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", marginBottom: 4 }}>
                      {STATUS_LABELS[event.status] ?? event.status}
                    </div>
                    {event.description && (
                      <div style={{ fontSize: 13, color: "#475569", marginBottom: 4 }}>
                        {event.description}
                      </div>
                    )}
                    {event.location && (
                      <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 4 }}>
                        📍 {event.location}
                      </div>
                    )}
                    <div style={{ fontSize: 12, color: "#94a3b8" }}>
                      {formatDateTime(event.occurred_at)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}
