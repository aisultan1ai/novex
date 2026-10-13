"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { getPublicTracking } from "@/lib/api/tracking";
import type { PublicTrackingResponse } from "@/types/tracking";
import { ApiError } from "@/lib/api/client";
import { errorMessage } from "@/lib/api/client";
import { Link } from "@/i18n/navigation";
import { localePrefix } from "@/i18n/routing";
import { toIntlLocale as intlLocale } from "@/i18n/runtime";
import { cityLabel } from "@/lib/cities";

type T = (key: string, values?: Record<string, string | number>) => string;

/* ─── Status badge config ──────────────────────────────────────────────────── */

// Подписи - в messages: tracking.badge.<status> и tracking.event.<status>.
const STATUS_BADGE: Record<string, { bg: string; color: string }> = {
  draft:                      { bg: "#F3F4F6", color: "#5F6E7E" },
  awaiting_payment:           { bg: "#F1F5F9", color: "#0E2E5C" },
  paid:                       { bg: "#D1FAE5", color: "#065F46" },
  dispatch_queued:            { bg: "#F1F5F9", color: "#0E2E5C" },
  sent_to_carrier:            { bg: "#F1F5F9", color: "#0E2E5C" },
  picked_up:                  { bg: "#EDE9FE", color: "#5B21B6" },
  in_transit:                 { bg: "#FEF3C7", color: "#92400E" },
  out_for_delivery:           { bg: "#EDE9FE", color: "#5B21B6" },
  arrived:                    { bg: "#EDE9FE", color: "#5B21B6" },
  delivered:                  { bg: "#D1FAE5", color: "#065F46" },
  delivery_failed:            { bg: "#FEE2E2", color: "#991B1B" },
  return_in_progress:         { bg: "#FEF3C7", color: "#92400E" },
  returned:                   { bg: "#FEE2E2", color: "#991B1B" },
  cancelled:                  { bg: "#FEE2E2", color: "#991B1B" },
  customs_hold:               { bg: "#FEF3C7", color: "#92400E" },
};

// Статусы событий, для которых есть нормализованная подпись tracking.event.<status>.
const EVENT_STATUSES = new Set([
  "paid", "sent_to_carrier", "picked_up", "in_transit", "out_for_delivery", "arrived",
  "delivered", "delivery_failed", "return_in_progress", "returned", "cancelled", "customs_hold",
]);

const RECENT_KEY = "novex_recent_tracking";
const MAX_RECENT = 3;

// Carriers whose native status text is more informative than our normalized
// labels (e.g. Azimuth returns "Распределено на маршрут" - nuance we would
// otherwise flatten into `in_transit`). For these, the timeline prefers the
// raw carrier description, falling back to STATUS_LABELS only when empty.
const RAW_DESCRIPTION_CARRIERS = new Set(["azimuth"]);

/* ─── Helpers ──────────────────────────────────────────────────────────────── */

function formatDate(iso: string, locale: string) {
  return new Date(iso).toLocaleString(intlLocale(locale), {
    day: "numeric", month: "long",
    hour: "2-digit", minute: "2-digit",
  });
}

function eventLabel(
  event: { status: string; description: string | null },
  carrierCode: string,
  t: T,
): string {
  const raw = event.description?.trim();
  if (RAW_DESCRIPTION_CARRIERS.has(carrierCode) && raw) return raw;
  if (EVENT_STATUSES.has(event.status)) return t(`event.${event.status}`);
  // carrier_unknown / any other unmapped status: never leak the internal code.
  return raw || t("statusUpdate");
}

function formatEta(createdAt: string, etaDaysMin: number, t: T, locale: string) {
  const d = new Date(createdAt);
  d.setDate(d.getDate() + etaDaysMin);
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);

  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();

  if (sameDay(d, today)) return t("today");
  if (sameDay(d, tomorrow)) return t("tomorrow");
  return d.toLocaleDateString(intlLocale(locale), { day: "numeric", month: "long" });
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
  const t = useTranslations("tracking");
  const locale = useLocale();
  const events = data.events;
  const carrierCode = data.carrier_code;
  const delivery = data.delivery;
  // Индекс ПОСЛЕДНЕГО delivered-события: под ним рисуем зелёный блок с
  // временем доставки. Без этого блок дублировался бы под каждым событием
  // со статусом "delivered" (например если в timeline два маркера).
  const lastDeliveredIdx = (() => {
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i].status === "delivered") return i;
    }
    return -1;
  })();
  if (events.length === 0) {
    return (
      <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, padding: "28px 30px", boxShadow: "0 1px 3px rgba(0,0,0,.08)" }}>
        <div style={{ font: "600 16px/1 Inter Variable, sans-serif", color: "#0E1826", marginBottom: 12 }}>
          {t("history")}
        </div>
        <p style={{ font: "400 14px/1.5 Inter Variable, sans-serif", color: "#9CA3AF", margin: 0 }}>
          {t("historyEmpty")}
        </p>
      </div>
    );
  }

  return (
    <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, boxShadow: "0 1px 3px rgba(0,0,0,.08)", padding: "28px 30px" }}>
      <div style={{ font: "600 16px/1 Inter Variable, sans-serif", color: "#0E1826", marginBottom: 22 }}>
        {t("history")}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
        {events.map((event, idx) => {
          const isLast = idx === events.length - 1;
          const isCurrent = isLast;
          const isDone = !isCurrent;

          const label = eventLabel(event, carrierCode, t);
          const subtitle = event.description && event.description.trim() !== label
            ? event.description
            : null;

          return (
            <div key={idx} style={{ display: "flex", gap: 16 }}>
              {/* dot + line */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
                {isCurrent ? (
                  <div style={{
                    width: 26, height: 26, borderRadius: "50%",
                    background: "#0B2545",
                    boxShadow: "0 0 0 4px rgba(11,37,69,.18)",
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
                  <div style={{ width: 2, flex: 1, minHeight: 34, background: isDone ? "#10B981" : "#E2E8EE", marginTop: 4, marginBottom: 4 }} />
                )}
              </div>
              {/* content */}
              <div style={{ paddingBottom: isLast ? 0 : 24, flex: 1 }}>
                <div style={{ font: `600 15px/1.3 Inter Variable, sans-serif`, color: isCurrent ? "#0B2545" : "#0E1826" }}>
                  {label}
                </div>
                {subtitle && (
                  <div style={{ font: "400 13px/1.4 Inter Variable, sans-serif", color: "#5F6E7E", marginTop: 2 }}>
                    {subtitle}
                  </div>
                )}
                {event.location && (
                  <div style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#5F6E7E", marginTop: 2 }}>
                    {event.location}
                  </div>
                )}
                <div style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#9CA3AF", marginTop: 2 }}>
                  {formatDate(event.occurred_at, locale)}
                </div>
                {idx === lastDeliveredIdx && delivery && (
                  <div style={{
                    marginTop: 12,
                    padding: "12px 14px",
                    background: "#F0FDF4",
                    border: "1px solid #BBF7D0",
                    borderRadius: 10,
                  }}>
                    <div style={{ font: "600 12px/1 Inter Variable, sans-serif", textTransform: "uppercase", letterSpacing: "0.05em", color: "#065F46", marginBottom: 6 }}>
                      {t("deliveredOk")}
                    </div>
                    <div style={{ font: "500 13px/1.4 Inter Variable, sans-serif", color: "#065F46" }}>
                      {formatDate(delivery.delivered_at, locale)}
                    </div>
                  </div>
                )}
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
  const t = useTranslations("tracking");
  const locale = useLocale();
  const badge = {
    ...(STATUS_BADGE[data.order_status] ?? { bg: "#F3F4F6", color: "#5F6E7E" }),
    label: t.has(`badge.${data.order_status}`) ? t(`badge.${data.order_status}`) : data.order_status,
  };
  const lastLocation = [...data.events].reverse().find((e) => e.location)?.location;
  const etaLabel = formatEta(data.created_at, data.eta_days_min, t, locale);
  const initials = data.carrier_name
    .split(" ")
    .map((w) => w[0] ?? "")
    .join("")
    .toUpperCase()
    .slice(0, 4);

  const [copied, setCopied] = useState(false);

  function handleCopyLink() {
    const url = `${window.location.origin}${localePrefix(locale)}/tracking?track=${encodeURIComponent(data.tracking_number)}`;
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
        <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, boxShadow: "0 1px 3px rgba(0,0,0,.08)", padding: "28px 30px", marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div style={{
                width: 48, height: 48, borderRadius: 12,
                background: "#FAFAFA", border: "1px solid #E2E8EE",
                display: "flex", alignItems: "center", justifyContent: "center",
                font: "700 11px/1 Inter Variable, sans-serif", color: "#5F6E7E",
                textAlign: "center", flexShrink: 0,
              }}>{initials}</div>
              <div>
                <div style={{ font: "600 18px/1.2 Inter Variable, sans-serif", color: "#0E1826" }}>
                  {t("order", { number: data.tracking_number })}
                </div>
                <div style={{ font: "500 14px/1 Inter Variable, sans-serif", color: "#5F6E7E", marginTop: 4 }}>
                  {cityLabel(data.from_city, locale)} → {cityLabel(data.to_city, locale)} · {data.carrier_name}
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

          <div style={{ display: "flex", gap: 40, marginTop: 24, paddingTop: 22, borderTop: "1px solid #E2E8EE", flexWrap: "wrap" }}>
            <div>
              <div style={{ font: "500 12px/1 Inter Variable, sans-serif", textTransform: "uppercase", letterSpacing: "0.05em", color: "#5F6E7E", marginBottom: 6 }}>
                {t("arrives")}
              </div>
              <div style={{ font: "600 16px/1 Inter Variable, sans-serif", color: "#0E1826" }}>
                {etaLabel}
              </div>
            </div>
            {lastLocation && (
              <div>
                <div style={{ font: "500 12px/1 Inter Variable, sans-serif", textTransform: "uppercase", letterSpacing: "0.05em", color: "#5F6E7E", marginBottom: 6 }}>
                  {t("currentPoint")}
                </div>
                <div style={{ font: "600 16px/1 Inter Variable, sans-serif", color: "#0E1826" }}>
                  {lastLocation}
                </div>
              </div>
            )}
            <div>
              <div style={{ font: "500 12px/1 Inter Variable, sans-serif", textTransform: "uppercase", letterSpacing: "0.05em", color: "#5F6E7E", marginBottom: 6 }}>
                {t("eta")}
              </div>
              <div style={{ font: "600 16px/1 Inter Variable, sans-serif", color: "#0E1826" }}>
                {data.eta_days_min === data.eta_days_max
                  ? t("days", { n: data.eta_days_min })
                  : t("daysRange", { min: data.eta_days_min, max: data.eta_days_max })}
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
            border: "1.5px solid #E2E8EE",
            borderRadius: 10,
            padding: "10px 20px",
            font: "500 14px/1 Inter Variable, sans-serif",
            color: "#5F6E7E",
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          {t("newSearch")}
        </button>
      </div>

      {/* Right: actions */}
      <div style={{ flexShrink: 0, width: isMobile ? "100%" : 340 }}>
        <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, boxShadow: "0 1px 3px rgba(0,0,0,.08)", padding: 24 }}>
          <div style={{ font: "600 15px/1 Inter Variable, sans-serif", color: "#0E1826", marginBottom: 8 }}>
            {t("notifyTitle")}
          </div>
          <p style={{ font: "400 14px/1.5 Inter Variable, sans-serif", color: "#5F6E7E", margin: "0 0 16px" }}>
            {t("notifyText")}
          </p>
          <Link
            href="/login"
            style={{
              display: "block",
              background: "#0B2545",
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
            {t("login")}
          </Link>
          <button
            onClick={handleCopyLink}
            style={{
              width: "100%",
              border: "1.5px solid #E2E8EE",
              background: "#fff",
              color: "#0E1826",
              font: "600 14px/1 Inter Variable, sans-serif",
              padding: 12,
              borderRadius: 10,
              textAlign: "center",
              cursor: "pointer",
              fontFamily: "inherit",
              transition: "border-color 0.15s",
            }}
          >
            {copied ? t("copied") : t("share")}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Main page inner ──────────────────────────────────────────────────────── */

function TrackingPageInner() {
  const t = useTranslations("tracking");
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
      setError(t("errors.empty"));
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
        setError(t("errors.notFound"));
      } else {
        setError(errorMessage(e, t("errors.failed")));
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
        <div style={{ padding: isMobile ? "40px 20px 32px" : "56px 48px 44px", background: "#FAFAFA", textAlign: "center", borderBottom: "1px solid #E2E8EE" }}>
          <div style={{ font: "500 13px/1 Inter Variable, sans-serif", textTransform: "uppercase", letterSpacing: "0.05em", color: "#0B2545", marginBottom: 14 }}>
            {t("eyebrow")}
          </div>
          <h1 style={{ font: `700 ${isMobile ? "28px" : "40px"}/1.12 'Space Grotesk Variable', 'Inter Variable', sans-serif`, letterSpacing: "-0.02em", color: "#0E1826", margin: "0 auto 14px", maxWidth: 560 }}>
            {t("title")}
          </h1>
          <p style={{ font: "400 17px/1.55 Inter Variable, sans-serif", color: "#5F6E7E", margin: "0 auto 28px", maxWidth: 480 }}>
            {t("subtitle")}
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
                border: focused ? "1.5px solid #0B2545" : "1.5px solid #E2E8EE",
                borderRadius: 10,
                padding: "15px 18px",
                font: "400 16px/1 Inter Variable, sans-serif",
                color: "#0E1826",
                background: "#fff",
                outline: "none",
                boxShadow: focused ? "0 0 0 3px rgba(11,37,69,.15)" : "none",
                transition: "border-color 0.15s, box-shadow 0.15s",
                fontFamily: "inherit",
              }}
            />
            <button
              type="submit"
              disabled={isLoading}
              style={{
                background: isLoading ? "#94A6C0" : "#0B2545",
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
              {isLoading ? t("searching") : t("track")}
            </button>
          </form>

          {recent.length > 0 && !result && (
            <div style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#9CA3AF", marginTop: 14 }}>
              {t("recent")}{" "}
              {recent.map((num, i) => (
                <span key={num}>
                  {i > 0 && " · "}
                  <button
                    onClick={() => { setInput(num); handleSearch(num); }}
                    style={{
                      background: "none", border: "none", cursor: "pointer",
                      font: "400 13px/1 Inter Variable, sans-serif",
                      color: "#5F6E7E", padding: 0, fontFamily: "inherit",
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
            <p style={{ font: "500 16px/1.5 Inter Variable, sans-serif", color: "#5F6E7E", margin: 0 }}>
              {t("emptyHint")}
            </p>
            <p style={{ font: "400 14px/1.5 Inter Variable, sans-serif", color: "#9CA3AF", margin: "8px 0 0" }}>
              {t("emptyHint2")}
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
