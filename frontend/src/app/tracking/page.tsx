"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { getPublicTracking } from "@/lib/api/tracking";
import type { PublicTrackingResponse } from "@/types/tracking";
import { ApiError } from "@/lib/api/client";

/* ─── Status badge config ──────────────────────────────────────────────────── */

const STATUS_BADGE: Record<string, { bg: string; color: string; label: string }> = {
  draft:                      { bg: "#F3F4F6", color: "#6B7280", label: "Черновик" },
  awaiting_payment:           { bg: "#EFF6FF", color: "#1D4ED8", label: "Ожидает оплаты" },
  paid:                       { bg: "#D1FAE5", color: "#065F46", label: "Оплата подтверждена" },
  dispatch_queued:            { bg: "#EFF6FF", color: "#1D4ED8", label: "Готовится к отправке" },
  sent_to_carrier:            { bg: "#EFF6FF", color: "#1D4ED8", label: "Передан перевозчику" },
  picked_up:                  { bg: "#EDE9FE", color: "#5B21B6", label: "Забран курьером" },
  in_transit:                 { bg: "#FEF3C7", color: "#92400E", label: "В пути" },
  out_for_delivery:           { bg: "#EDE9FE", color: "#5B21B6", label: "Выезд на доставку" },
  arrived:                    { bg: "#EDE9FE", color: "#5B21B6", label: "Прибыл в пункт выдачи" },
  delivered:                  { bg: "#D1FAE5", color: "#065F46", label: "Доставлен" },
  delivery_failed:            { bg: "#FEE2E2", color: "#991B1B", label: "Попытка не удалась" },
  return_in_progress:         { bg: "#FEF3C7", color: "#92400E", label: "Возврат в пути" },
  returned:                   { bg: "#FEE2E2", color: "#991B1B", label: "Возвращён" },
  cancelled:                  { bg: "#FEE2E2", color: "#991B1B", label: "Отменён" },
  customs_hold:               { bg: "#FEF3C7", color: "#92400E", label: "Задержан на таможне" },
};

const STATUS_LABELS: Record<string, string> = {
  paid:             "Оплата подтверждена",
  sent_to_carrier:  "Передан перевозчику",
  picked_up:        "Забран курьером",
  in_transit:       "В пути",
  out_for_delivery: "Выезд на доставку",
  arrived:          "Прибыл в пункт выдачи",
  delivered:        "Доставлен",
  delivery_failed:  "Попытка доставки не удалась",
  return_in_progress: "Возврат в пути",
  returned:         "Возвращён",
  cancelled:        "Отменён",
  customs_hold:     "Задержан на таможне",
};

const RECENT_KEY = "novex_recent_tracking";
const MAX_RECENT = 3;

/* ─── Helpers ──────────────────────────────────────────────────────────────── */

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "numeric", month: "long",
    hour: "2-digit", minute: "2-digit",
  });
}

function formatEta(createdAt: string, etaDaysMin: number) {
  const d = new Date(createdAt);
  d.setDate(d.getDate() + etaDaysMin);
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);

  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();

  if (sameDay(d, today)) return "Сегодня";
  if (sameDay(d, tomorrow)) return "Завтра";
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
}

function loadRecent(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveRecent(trackingNumber: string) {
  const prev = loadRecent().filter((n) => n !== trackingNumber);
  const next = [trackingNumber, ...prev].slice(0, MAX_RECENT);
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(next)); } catch {}
}

/* ─── Timeline ─────────────────────────────────────────────────────────────── */

function Timeline({ data }: { data: PublicTrackingResponse }) {
  const events = data.events;
  if (events.length === 0) {
    return (
      <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 16, padding: "28px 30px", boxShadow: "0 1px 3px rgba(0,0,0,.08)" }}>
        <div style={{ font: "600 16px/1 Inter Variable, sans-serif", color: "#111827", marginBottom: 12 }}>
          История перемещений
        </div>
        <p style={{ font: "400 14px/1.5 Inter Variable, sans-serif", color: "#9CA3AF", margin: 0 }}>
          События появятся после передачи перевозчику
        </p>
      </div>
    );
  }

  return (
    <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 16, boxShadow: "0 1px 3px rgba(0,0,0,.08)", padding: "28px 30px" }}>
      <div style={{ font: "600 16px/1 Inter Variable, sans-serif", color: "#111827", marginBottom: 22 }}>
        История перемещений
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
        {events.map((event, idx) => {
          const isLast = idx === events.length - 1;
          const isCurrent = isLast;
          const isDone = !isCurrent;

          return (
            <div key={idx} style={{ display: "flex", gap: 16 }}>
              {/* dot + line */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
                {isCurrent ? (
                  <div style={{
                    width: 26, height: 26, borderRadius: "50%",
                    background: "#2563EB",
                    boxShadow: "0 0 0 4px rgba(37,99,235,.18)",
                    color: "#fff",
                    font: "700 11px/1 Inter Variable, sans-serif",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    flexShrink: 0,
                  }}>●</div>
                ) : (
                  <div style={{
                    width: 26, height: 26, borderRadius: "50%",
                    background: "#10B981",
                    color: "#fff",
                    font: "700 13px/1 Inter Variable, sans-serif",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    flexShrink: 0,
                  }}>✓</div>
                )}
                {!isLast && (
                  <div style={{ width: 2, flex: 1, minHeight: 34, background: isDone ? "#10B981" : "#E5E7EB", marginTop: 4, marginBottom: 4 }} />
                )}
              </div>
              {/* content */}
              <div style={{ paddingBottom: isLast ? 0 : 24, flex: 1 }}>
                <div style={{ font: `600 15px/1.3 Inter Variable, sans-serif`, color: isCurrent ? "#2563EB" : "#111827" }}>
                  {STATUS_LABELS[event.status] ?? event.status}
                </div>
                {event.description && (
                  <div style={{ font: "400 13px/1.4 Inter Variable, sans-serif", color: "#6B7280", marginTop: 2 }}>
                    {event.description}
                  </div>
                )}
                {event.location && (
                  <div style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#6B7280", marginTop: 2 }}>
                    {event.location}
                  </div>
                )}
                <div style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#9CA3AF", marginTop: 2 }}>
                  {formatDate(event.occurred_at)}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Results ──────────────────────────────────────────────────────────────── */

function TrackingResults({
  data,
  onReset,
  isMobile,
}: {
  data: PublicTrackingResponse;
  onReset: () => void;
  isMobile: boolean;
}) {
  const badge = STATUS_BADGE[data.order_status] ?? { bg: "#F3F4F6", color: "#6B7280", label: data.order_status };
  const lastLocation = [...data.events].reverse().find((e) => e.location)?.location;
  const etaLabel = formatEta(data.created_at, data.eta_days_min);
  const initials = data.carrier_name
    .split(" ")
    .map((w) => w[0] ?? "")
    .join("")
    .toUpperCase()
    .slice(0, 4);

  const [copied, setCopied] = useState(false);

  function handleCopyLink() {
    const url = `${window.location.origin}/tracking?track=${encodeURIComponent(data.tracking_number)}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div style={{ display: "flex", flexDirection: isMobile ? "column" : "row", gap: isMobile ? 16 : 32, padding: isMobile ? "20px 16px 40px" : "40px 48px 56px", background: "#FAFAFA" }}>
      {/* Left: status card + timeline */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Status card */}
        <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 16, boxShadow: "0 1px 3px rgba(0,0,0,.08)", padding: "28px 30px", marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div style={{
                width: 48, height: 48, borderRadius: 12,
                background: "#FAFAFA", border: "1px solid #E5E7EB",
                display: "flex", alignItems: "center", justifyContent: "center",
                font: "700 11px/1 Inter Variable, sans-serif", color: "#6B7280",
                textAlign: "center", flexShrink: 0,
              }}>{initials}</div>
              <div>
                <div style={{ font: "600 18px/1.2 Inter Variable, sans-serif", color: "#111827" }}>
                  Заказ {data.tracking_number}
                </div>
                <div style={{ font: "500 14px/1 Inter Variable, sans-serif", color: "#6B7280", marginTop: 4 }}>
                  {data.from_city} → {data.to_city} · {data.carrier_name}
                </div>
              </div>
            </div>
            <span style={{
              font: "600 13px/1 Inter Variable, sans-serif",
              color: badge.color,
              background: badge.bg,
              padding: "7px 15px",
              borderRadius: 999,
              whiteSpace: "nowrap",
            }}>{badge.label}</span>
          </div>

          <div style={{ display: "flex", gap: 40, marginTop: 24, paddingTop: 22, borderTop: "1px solid #E5E7EB", flexWrap: "wrap" }}>
            <div>
              <div style={{ font: "500 12px/1 Inter Variable, sans-serif", textTransform: "uppercase", letterSpacing: "0.05em", color: "#6B7280", marginBottom: 6 }}>
                Прибудет
              </div>
              <div style={{ font: "600 16px/1 Inter Variable, sans-serif", color: "#111827" }}>
                {etaLabel}
              </div>
            </div>
            {lastLocation && (
              <div>
                <div style={{ font: "500 12px/1 Inter Variable, sans-serif", textTransform: "uppercase", letterSpacing: "0.05em", color: "#6B7280", marginBottom: 6 }}>
                  Текущий пункт
                </div>
                <div style={{ font: "600 16px/1 Inter Variable, sans-serif", color: "#111827" }}>
                  {lastLocation}
                </div>
              </div>
            )}
            <div>
              <div style={{ font: "500 12px/1 Inter Variable, sans-serif", textTransform: "uppercase", letterSpacing: "0.05em", color: "#6B7280", marginBottom: 6 }}>
                Срок доставки
              </div>
              <div style={{ font: "600 16px/1 Inter Variable, sans-serif", color: "#111827" }}>
                {data.eta_days_min === data.eta_days_max
                  ? `${data.eta_days_min} дн.`
                  : `${data.eta_days_min}-${data.eta_days_max} дн.`}
              </div>
            </div>
          </div>
        </div>

        {/* Timeline */}
        <Timeline data={data} />

        <button
          onClick={onReset}
          style={{
            marginTop: 20,
            background: "none",
            border: "1.5px solid #E5E7EB",
            borderRadius: 10,
            padding: "10px 20px",
            font: "500 14px/1 Inter Variable, sans-serif",
            color: "#6B7280",
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          ← Новый поиск
        </button>
      </div>

      {/* Right: actions */}
      <div style={{ flexShrink: 0, width: isMobile ? "100%" : 340 }}>
        <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 16, boxShadow: "0 1px 3px rgba(0,0,0,.08)", padding: 24 }}>
          <div style={{ font: "600 15px/1 Inter Variable, sans-serif", color: "#111827", marginBottom: 8 }}>
            Уведомления о статусе
          </div>
          <p style={{ font: "400 14px/1.5 Inter Variable, sans-serif", color: "#6B7280", margin: "0 0 16px" }}>
            Войдите в аккаунт, чтобы получать уведомления о каждом этапе доставки.
          </p>
          <Link
            href="/login"
            style={{
              display: "block",
              background: "#2563EB",
              color: "#fff",
              font: "600 14px/1 Inter Variable, sans-serif",
              padding: 12,
              borderRadius: 10,
              textAlign: "center",
              textDecoration: "none",
              marginBottom: 10,
              fontFamily: "inherit",
            }}
          >
            Войти в аккаунт
          </Link>
          <button
            onClick={handleCopyLink}
            style={{
              width: "100%",
              border: "1.5px solid #E5E7EB",
              background: "#fff",
              color: "#111827",
              font: "600 14px/1 Inter Variable, sans-serif",
              padding: 12,
              borderRadius: 10,
              textAlign: "center",
              cursor: "pointer",
              fontFamily: "inherit",
              transition: "border-color 0.15s",
            }}
          >
            {copied ? "Ссылка скопирована!" : "Поделиться отслеживанием"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Main page inner ──────────────────────────────────────────────────────── */

function TrackingPageInner() {
  const searchParams = useSearchParams();
  const isMobile = useIsMobile();
  const initialTrack = searchParams.get("track") ?? "";

  const [input, setInput] = useState(initialTrack);
  const [result, setResult] = useState<PublicTrackingResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<string[]>([]);
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setRecent(loadRecent());
  }, []);

  useEffect(() => {
    if (initialTrack) {
      handleSearch(initialTrack);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSearch(trackingNumber: string) {
    const num = trackingNumber.trim();
    if (!num) {
      setError("Введите трек-номер");
      return;
    }
    setIsLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await getPublicTracking(num);
      setResult(data);
      saveRecent(num);
      setRecent(loadRecent());
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setError("Трек-номер не найден. Проверьте правильность ввода.");
      } else {
        setError(e instanceof Error ? e.message : "Не удалось получить данные");
      }
    } finally {
      setIsLoading(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    handleSearch(input);
  }

  function handleReset() {
    setResult(null);
    setError(null);
    setInput("");
    setTimeout(() => inputRef.current?.focus(), 50);
  }

  return (
    <>
      <Navbar />
      <main style={{ minHeight: "100vh", background: "#FAFAFA" }}>
        {/* Search hero */}
        <div style={{ padding: isMobile ? "40px 20px 32px" : "56px 48px 44px", background: "#FAFAFA", textAlign: "center", borderBottom: "1px solid #E5E7EB" }}>
          <div style={{ font: "500 13px/1 Inter Variable, sans-serif", textTransform: "uppercase", letterSpacing: "0.05em", color: "#2563EB", marginBottom: 14 }}>
            Отслеживание посылки
          </div>
          <h1 style={{ font: `700 ${isMobile ? "28px" : "40px"}/1.12 Inter Variable, sans-serif`, letterSpacing: "-0.02em", color: "#111827", margin: "0 auto 14px", maxWidth: 560 }}>
            Где моя посылка?
          </h1>
          <p style={{ font: "400 17px/1.55 Inter Variable, sans-serif", color: "#6B7280", margin: "0 auto 28px", maxWidth: 480 }}>
            Введите трек-номер - покажем статус и текущий пункт по всем службам сразу.
          </p>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: isMobile ? "column" : "row", gap: 12, maxWidth: 560, margin: "0 auto" }}>
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="NX-0001-KZ"
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              style={{
                flex: 1,
                border: focused ? "1.5px solid #2563EB" : "1.5px solid #E5E7EB",
                borderRadius: 10,
                padding: "15px 18px",
                font: "400 16px/1 Inter Variable, sans-serif",
                color: "#111827",
                background: "#fff",
                outline: "none",
                boxShadow: focused ? "0 0 0 3px rgba(37,99,235,.15)" : "none",
                transition: "border-color 0.15s, box-shadow 0.15s",
                fontFamily: "inherit",
              }}
            />
            <button
              type="submit"
              disabled={isLoading}
              style={{
                background: isLoading ? "#93C5FD" : "#2563EB",
                color: "#fff",
                font: "600 15px/1 Inter Variable, sans-serif",
                padding: "15px 32px",
                borderRadius: 10,
                border: "none",
                cursor: isLoading ? "not-allowed" : "pointer",
                whiteSpace: "nowrap",
                fontFamily: "inherit",
                transition: "background 0.15s",
              }}
            >
              {isLoading ? "Поиск..." : "Отследить"}
            </button>
          </form>

          {recent.length > 0 && !result && (
            <div style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#9CA3AF", marginTop: 14 }}>
              Недавние:{" "}
              {recent.map((num, i) => (
                <span key={num}>
                  {i > 0 && " · "}
                  <button
                    onClick={() => { setInput(num); handleSearch(num); }}
                    style={{
                      background: "none", border: "none", cursor: "pointer",
                      font: "400 13px/1 Inter Variable, sans-serif",
                      color: "#6B7280", padding: 0, fontFamily: "inherit",
                    }}
                  >
                    {num}
                  </button>
                </span>
              ))}
            </div>
          )}

          {error && (
            <div style={{
              marginTop: 16,
              maxWidth: 560,
              margin: "16px auto 0",
              background: "#FEF2F2",
              border: "1px solid #FECACA",
              borderRadius: 10,
              padding: "12px 16px",
              font: "400 14px/1.4 Inter Variable, sans-serif",
              color: "#B91C1C",
            }}>{error}</div>
          )}
        </div>

        {/* Results */}
        {result && <TrackingResults data={result} onReset={handleReset} isMobile={isMobile} />}

        {/* Empty state hint */}
        {!result && !isLoading && !error && (
          <div style={{ padding: isMobile ? "40px 20px" : "64px 48px", textAlign: "center" }}>
            <div style={{ marginBottom: 16, fontSize: 48 }}>📦</div>
            <p style={{ font: "500 16px/1.5 Inter Variable, sans-serif", color: "#6B7280", margin: 0 }}>
              Введите трек-номер выше, чтобы узнать статус посылки
            </p>
            <p style={{ font: "400 14px/1.5 Inter Variable, sans-serif", color: "#9CA3AF", margin: "8px 0 0" }}>
              Трек-номер можно найти в письме подтверждения заказа
            </p>
          </div>
        )}
      </main>
      <Footer />
    </>
  );
}

/* ─── Export (Suspense required for useSearchParams) ───────────────────────── */

export default function TrackingPage() {
  return (
    <Suspense>
      <TrackingPageInner />
    </Suspense>
  );
}
