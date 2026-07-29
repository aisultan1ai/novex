"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Package, FileText, Clock, MapPin, Star, ChevronDown, ChevronUp } from "lucide-react";

import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import { CONTACTS } from "@/lib/config/contacts";
import { LANDING_STATS, SUPPORTED_CARRIERS } from "@/lib/config/landing";
import CitySelect from "@/components/ui/CitySelect";
import { ApiError, calculateShippingQuote, selectShippingQuote } from "@/lib/api/shipping";
import type { RateQuoteItem, ShipmentType, ShippingQuoteResponse } from "@/types/quote";

/* ─── Types & helpers ────────────────────────────────────────────────────── */

type FormState = {
  fromCity: string;
  toCity: string;
  shipmentType: ShipmentType;
  weightKg: string;
  quantity: string;
  widthCm: string;
  heightCm: string;
  depthCm: string;
};

const initialForm: FormState = {
  fromCity: "",
  toCity: "",
  shipmentType: "parcel",
  weightKg: "",
  quantity: "1",
  widthCm: "10",
  heightCm: "10",
  depthCm: "10",
};

function validateQuoteForm(form: FormState): string | null {
  const weight = Number(form.weightKg);
  const qty = Number(form.quantity);

  if (!form.weightKg.trim() || isNaN(weight) || weight <= 0)
    return "Введите корректный вес (> 0).";
  if (weight > 1000) return "Вес не может превышать 1000 кг.";
  if (!form.quantity.trim() || isNaN(qty) || qty <= 0)
    return "Введите корректное количество (> 0).";
  if (!Number.isInteger(qty)) return "Количество должно быть целым числом.";
  if (qty > 999) return "Количество не может превышать 999.";

  if (form.shipmentType !== "document") {
    // Dimensions are required for parcels - used for volumetric weight (Azimuth
    // tariff table) and mandatory in CSE SaveWaybillOffice (Length/Width/Height).
    // Making them required here avoids a surprise validation error at the order
    // step where they are always required.
    const width = Number(form.widthCm);
    const height = Number(form.heightCm);
    const depth = Number(form.depthCm);
    if (!form.widthCm.trim() || isNaN(width) || width <= 0)
      return "Введите корректную ширину (> 0).";
    if (!form.heightCm.trim() || isNaN(height) || height <= 0)
      return "Введите корректную высоту (> 0).";
    if (!form.depthCm.trim() || isNaN(depth) || depth <= 0)
      return "Введите корректную глубину (> 0).";
    if (width > 500 || height > 500 || depth > 500)
      return "Размеры не могут превышать 500 см.";
  }
  return null;
}

const BADGE_LABELS: Record<string, string> = {
  fastest: "Быстрее всего",
  recommended: "Рекомендуем",
  best_value: "Лучшая цена",
};

function formatPrice(price: number, currency: string): string {
  return `${new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(price)} ${currency}`;
}

function calcChargeable(
  weightKg: number,
  widthCm: number,
  heightCm: number,
  depthCm: number,
  qty: number,
): number {
  const vol = (widthCm * heightCm * depthCm) / 6000;
  return Math.max(weightKg, vol) * qty;
}


/* ─── Sub-components ─────────────────────────────────────────────────────── */

function SkeletonCard() {
  return (
    <div
      className="skeleton"
      style={{ height: 90, borderRadius: 16 }}
    />
  );
}

function TariffBadge({ name }: { name: string }) {
  const lower = name.toLowerCase();
  let bg: string, color: string;
  if (lower.includes("экспресс") || lower.includes("express")) {
    bg = "#FEF3C7"; color = "#92400E";
  } else if (lower.includes("эконом") || lower.includes("econom")) {
    bg = "#D1FAE5"; color = "#065F46";
  } else {
    bg = "#F3F4F6"; color = "#374151";
  }
  return (
    <span style={{ background: bg, color, padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600 }}>
      {name}
    </span>
  );
}

function DetailRow({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span style={{ fontSize: 13, color: "#6B7280" }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 600, color: muted ? "#9CA3AF" : "#111827" }}>{value}</span>
    </div>
  );
}

function InputField({
  label,
  value,
  onChange,
  placeholder,
  required = true,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  required?: boolean;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <div>
      <label style={{ display: "block", font: "500 13px/1 Inter Variable, sans-serif", color: "#374151", marginBottom: 6 }}>
        {label}
      </label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        inputMode="decimal"
        required={required}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          width: "100%",
          border: focused ? "1.5px solid #2563EB" : "1.5px solid #E5E7EB",
          borderRadius: 10,
          padding: "12px 14px",
          font: "400 15px/1 Inter Variable, sans-serif",
          color: "#111827",
          background: "#fff",
          outline: "none",
          boxShadow: focused ? "0 0 0 3px rgba(37,99,235,0.15)" : "none",
          transition: "border-color 0.15s, box-shadow 0.15s",
          boxSizing: "border-box",
        }}
      />
    </div>
  );
}

/* ─── Carrier logos ──────────────────────────────────────────────────────── */

// Two-letter aliases still map to full carrier codes; keep in sync with the
// canonical list in @/lib/config/landing.ts (SUPPORTED_CARRIERS).
const _CARRIER_LOGO_ALIASES: Record<string, string> = {
  az:  "azimuth",
  ex:  "exline",
  kse: "cse",
};

function getCarrierLogo(carrierCode: string): string | null {
  const code = carrierCode.toLowerCase();
  const canonical = _CARRIER_LOGO_ALIASES[code] ?? code;
  return SUPPORTED_CARRIERS.find((c) => c.code === canonical)?.logo ?? null;
}

/* ─── Static sections ────────────────────────────────────────────────────── */

const HOW_IT_WORKS = [
  { step: 1, title: "Заполни форму", desc: "Укажи маршрут, вес и габариты посылки" },
  { step: 2, title: "Выбери тариф", desc: "Сравни предложения курьерских служб" },
  { step: 3, title: "Оплати онлайн", desc: "Безопасная оплата картой Казахстана" },
  { step: 4, title: "Отслеживай", desc: "Следи за посылкой в реальном времени" },
];

const WHY_NOVEX = [
  {
    icon: <Star size={24} color="#2563EB" />,
    title: "Выгодные цены",
    desc: "Сравниваем тарифы ведущих курьерских служб и показываем лучшие предложения",
  },
  {
    icon: <Clock size={24} color="#2563EB" />,
    title: "Быстрое оформление",
    desc: "От расчёта до оформления - 2 минуты. Без лишних звонков и визитов",
  },
  {
    icon: <MapPin size={24} color="#2563EB" />,
    title: "Надёжное отслеживание",
    desc: "Актуальный статус посылки в одном окне, уведомления о каждом этапе",
  },
];

const FAQ_ITEMS = [
  {
    q: "Как рассчитать стоимость доставки?",
    a: "Введите город отправления и назначения, укажите вес и габариты посылки, нажмите «Рассчитать» - система покажет тарифы доступных служб.",
  },
  {
    q: "Какие курьерские службы поддерживаются?",
    a: "Сейчас доступны основные курьерские службы Казахстана. Список постоянно расширяется.",
  },
  {
    q: "Как отследить посылку?",
    a: "Перейдите в раздел «Отслеживание» и введите трек-номер, который вы получили при оформлении заказа.",
  },
  {
    q: "Можно ли оформить доставку без регистрации?",
    a: "Рассчитать тариф можно без регистрации. Для оформления заказа потребуется создать аккаунт - это займёт меньше минуты.",
  },
];

/* ─── Main page ──────────────────────────────────────────────────────────── */

export default function HomePage() {
  const router = useRouter();
  const isMobile = useIsMobile();

  const [form, setForm] = useState<FormState>(initialForm);

  const [results, setResults] = useState<ShippingQuoteResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRate, setSelectedRate] = useState<RateQuoteItem | null>(null);
  const [isSelectingRate, setIsSelectingRate] = useState(false);
  const [openFaq, setOpenFaq] = useState<number | null>(0);

  const resultsRef = useRef<HTMLDivElement>(null);

  // Fields that carry a decimal number typed by the user. Russian keyboards
  // put "," on the decimal key by default, so both "0,5" and "0.5" must work.
  // We normalize the comma to a dot at write time so parsing/validation stays
  // dot-only downstream.
  const _NUMERIC_FIELDS: ReadonlySet<keyof FormState> = new Set([
    "weightKg", "quantity", "widthCm", "heightCm", "depthCm",
  ] as (keyof FormState)[]);
  function setField<K extends keyof FormState>(key: K, val: FormState[K]) {
    const normalized: FormState[K] =
      typeof val === "string" && _NUMERIC_FIELDS.has(key)
        ? (val.replace(",", ".") as FormState[K])
        : val;
    setForm((prev) => ({ ...prev, [key]: normalized }));
  }

  useEffect(() => {
    if (results) {
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    }
  }, [results]);

  useEffect(() => {
    const handler = () => {
      setResults(null);
      setSelectedRate(null);
      setError(null);
    };
    window.addEventListener("novex:resetHome", handler);
    return () => window.removeEventListener("novex:resetHome", handler);
  }, []);

  useEffect(() => {
    if (!selectedRate) return;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, [selectedRate]);

  useEffect(() => {
    if (!selectedRate) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setSelectedRate(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedRate]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    // Intracity delivery is supported (zone 0 in tariff_engine) - do not block
    // same-city quotes here.
    const numericError = validateQuoteForm(form);
    if (numericError) { setError(numericError); return; }

    setIsLoading(true);
    setResults(null);
    setSelectedRate(null);
    try {
      const isDoc = form.shipmentType === "document";
      const res = await calculateShippingQuote({
        from_country: "KZ",
        from_city: form.fromCity.trim(),
        to_country: "KZ",
        to_city: form.toCity.trim(),
        shipment_type: form.shipmentType,
        weight_kg: Number(form.weightKg),
        quantity: Number(form.quantity),
        width_cm: isDoc ? 0 : (Number(form.widthCm) || 0),
        height_cm: isDoc ? 0 : (Number(form.heightCm) || 0),
        depth_cm: isDoc ? 0 : (Number(form.depthCm) || 0),
      });
      setResults(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось рассчитать тарифы.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSelectRate(rate: RateQuoteItem) {
    if (!results || rate.id === null) return;
    setIsSelectingRate(true);
    setError(null);
    try {
      await selectShippingQuote(
        results.quote_session_id,
        { rate_quote_id: rate.id as number },
        results.public_token,
      );
      setSelectedRate(rate);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось выбрать тариф.");
    } finally {
      setIsSelectingRate(false);
    }
  }

  function handleProceed() {
    if (!selectedRate || !results) return;
    const token = results.public_token;
    router.push(
      `/quote/shipment?quoteSessionId=${results.quote_session_id}${token ? `&token=${token}` : ""}`,
    );
  }

  const hasResults = results !== null;
  const minPrice = results ? Math.min(...results.quotes.map((q) => q.price)) : null;
  const chargeable = form.shipmentType === "document"
    ? Number(form.weightKg) * Number(form.quantity)
    : calcChargeable(
        Number(form.weightKg),
        Number(form.widthCm),
        Number(form.heightCm),
        Number(form.depthCm),
        Number(form.quantity),
      );

  return (
    <div style={{ minHeight: "100vh", background: "#FAFAFA" }}>
      <Navbar />

      <main>
        {/* ── HERO ──────────────────────────────────────────────────────── */}
        <section
          style={{
            background: "linear-gradient(160deg, #EFF6FF 0%, #F8FAFF 45%, #F0FDF4 100%)",
            padding: isMobile ? "56px 20px 64px" : "88px 48px 96px",
            textAlign: "center",
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* Decorative background blobs */}
          <div style={{ position: "absolute", top: -60, left: -80, width: 320, height: 320, borderRadius: "50%", background: "rgba(37,99,235,0.06)", pointerEvents: "none" }} />
          <div style={{ position: "absolute", bottom: -80, right: -60, width: 280, height: 280, borderRadius: "50%", background: "rgba(16,185,129,0.05)", pointerEvents: "none" }} />
          <div
            style={{
              font: "500 13px/1 Inter Variable, sans-serif",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "#2563EB",
              marginBottom: 16,
            }}
          >
            Агрегатор курьерских служб
          </div>
          <h1
            style={{
              font: `700 ${isMobile ? "32px" : "48px"}/1.12 Inter Variable, sans-serif`,
              letterSpacing: "-0.02em",
              color: "#111827",
              margin: "0 auto 16px",
              maxWidth: 640,
            }}
          >
            Доставка по Казахстану
          </h1>
          <p
            style={{
              font: "400 18px/1.6 Inter Variable, sans-serif",
              color: "#6B7280",
              margin: "0 auto 40px",
              maxWidth: 520,
            }}
          >
            Сравните тарифы курьерских служб и оформите отправление за 2&nbsp;минуты.
          </p>

          {/* ── FORM CARD ────────────────────────────────────────────── */}
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #E5E7EB",
              borderRadius: 24,
              boxShadow: "0 20px 60px rgba(37,99,235,0.10), 0 4px 16px rgba(0,0,0,0.06)",
              padding: isMobile ? "24px 20px" : "36px 36px",
              maxWidth: 940,
              margin: "0 auto",
              textAlign: "left",
              position: "relative",
              zIndex: 10,
            }}
          >
            <form onSubmit={handleSubmit}>
              {/* Row 1: route + shipment type */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr 220px",
                  gap: 14,
                  alignItems: "end",
                  marginBottom: 18,
                }}
              >
                <div>
                  <label style={{ display: "block", font: "500 13px/1 Inter Variable, sans-serif", color: "#374151", marginBottom: 6 }}>
                    Откуда
                  </label>
                  <CitySelect
                    value={form.fromCity}
                    onChange={(v) => setField("fromCity", v)}
                    placeholder="Город отправки"
                  />
                </div>
                <div>
                  <label style={{ display: "block", font: "500 13px/1 Inter Variable, sans-serif", color: "#374151", marginBottom: 6 }}>
                    Куда
                  </label>
                  <CitySelect
                    value={form.toCity}
                    onChange={(v) => setField("toCity", v)}
                    placeholder="Город доставки"
                  />
                </div>
                <div>
                  <label style={{ display: "block", font: "500 13px/1 Inter Variable, sans-serif", color: "#374151", marginBottom: 6 }}>
                    Что отправляете
                  </label>
                  <div style={{ display: "flex", gap: 6 }}>
                    {(["parcel", "document"] as ShipmentType[]).map((t) => {
                      const active = form.shipmentType === t;
                      return (
                        <button
                          key={t}
                          type="button"
                          onClick={() => setField("shipmentType", t)}
                          style={{
                            flex: 1,
                            border: active ? "1.5px solid #2563EB" : "1.5px solid #E5E7EB",
                            background: active ? "#EFF6FF" : "#ffffff",
                            color: active ? "#2563EB" : "#6B7280",
                            borderRadius: 10,
                            padding: "12px 0",
                            font: "600 14px/1 Inter Variable, sans-serif",
                            cursor: "pointer",
                            transition: "all 0.15s",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 6,
                          }}
                        >
                          {t === "parcel" ? <Package size={14} /> : <FileText size={14} />}
                          {t === "parcel" ? "Посылка" : "Документ"}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Row 2: dimensions + submit */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: isMobile
                    ? "repeat(2,1fr)"
                    : form.shipmentType === "document"
                      ? "1fr 1fr auto"
                      : "1fr 1fr 1fr 1fr 1fr auto",
                  gap: 14,
                  alignItems: "end",
                }}
              >
                <InputField label="Вес, кг" value={form.weightKg} onChange={(v) => setField("weightKg", v)} placeholder="2.5" />
                <InputField label="Кол-во" value={form.quantity} onChange={(v) => setField("quantity", v)} placeholder="1" />
                {form.shipmentType !== "document" && (
                  <>
                    <InputField label="Ширина, см" value={form.widthCm} onChange={(v) => setField("widthCm", v)} placeholder="20" required />
                    <InputField label="Высота, см" value={form.heightCm} onChange={(v) => setField("heightCm", v)} placeholder="15" required />
                    <InputField label="Глубина, см" value={form.depthCm} onChange={(v) => setField("depthCm", v)} placeholder="10" required />
                  </>
                )}

                <button
                  type="submit"
                  disabled={isLoading}
                  style={{
                    background: isLoading ? "#93C5FD" : "#2563EB",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: 10,
                    padding: "13px 24px",
                    font: "600 15px/1 Inter Variable, sans-serif",
                    cursor: isLoading ? "not-allowed" : "pointer",
                    whiteSpace: "nowrap",
                    transition: "background 0.15s",
                    ...(isMobile ? { gridColumn: "1 / -1", padding: "14px" } : {}),
                  }}
                  onMouseEnter={(e) => {
                    if (!isLoading) e.currentTarget.style.background = "#1D4ED8";
                  }}
                  onMouseLeave={(e) => {
                    if (!isLoading) e.currentTarget.style.background = "#2563EB";
                  }}
                >
                  {isLoading ? "Рассчитываем..." : "Рассчитать"}
                </button>
              </div>

              {error && (
                <div
                  style={{
                    marginTop: 16,
                    padding: "12px 14px",
                    borderRadius: 10,
                    background: "#FEF2F2",
                    border: "1px solid #FECACA",
                    color: "#B91C1C",
                    font: "400 13px/1.5 Inter Variable, sans-serif",
                  }}
                >
                  {error}
                </div>
              )}
            </form>
          </div>

          {/* Social proof. Numbers come from NEXT_PUBLIC_STAT_* env vars so ops
              can bump them without a code push. Carrier count falls back to the
              length of SUPPORTED_CARRIERS so it can never claim more services
              than we actually show in the partners strip below. Optional stats
              (shipments/rating) render only when their env var is set — hides
              placeholders in fresh envs. */}
          {(() => {
            const carriersLabel = LANDING_STATS.carriersLabel || `${SUPPORTED_CARRIERS.length}+`;
            return (
              <div
                style={{
                  display: "flex",
                  gap: 32,
                  justifyContent: "center",
                  flexWrap: "wrap",
                  marginTop: 24,
                  font: "500 13px/1 Inter Variable, sans-serif",
                  color: "#6B7280",
                }}
              >
                <span><b style={{ color: "#111827" }}>{carriersLabel}</b> служб доставки</span>
                {LANDING_STATS.shipmentsLabel && (
                  <>
                    <span style={{ color: "#D1D5DB" }}>|</span>
                    <span><b style={{ color: "#111827" }}>{LANDING_STATS.shipmentsLabel}</b> отправлений</span>
                  </>
                )}
                {LANDING_STATS.ratingLabel && (
                  <>
                    <span style={{ color: "#D1D5DB" }}>|</span>
                    <span><b style={{ color: "#10B981" }}>{LANDING_STATS.ratingLabel}</b> средний рейтинг</span>
                  </>
                )}
              </div>
            );
          })()}

          {/* Mini how-it-works - shown only before results */}
        </section>

        {/* ── RESULTS (inline, appears below form) ──────────────────────── */}
        {hasResults && (
          <section
            ref={resultsRef}
            style={{
              maxWidth: 900,
              margin: "0 auto",
              padding: "0 20px 80px",
            }}
          >
            {/* Summary bar */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: 12,
                marginBottom: 24,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ font: "600 18px/1 Inter Variable, sans-serif", color: "#111827" }}>
                  {form.fromCity} → {form.toCity}
                </span>
                <span
                  style={{
                    background: "#F3F4F6",
                    color: "#374151",
                    font: "500 13px/1 Inter Variable, sans-serif",
                    padding: "4px 12px",
                    borderRadius: 999,
                  }}
                >
                  {form.weightKg} кг · {form.shipmentType === "parcel" ? "Посылка" : "Документ"}
                </span>
              </div>
              <button
                onClick={() => { setResults(null); setSelectedRate(null); }}
                style={{
                  background: "none",
                  border: "none",
                  color: "#2563EB",
                  font: "500 14px/1 Inter Variable, sans-serif",
                  cursor: "pointer",
                  textDecoration: "underline",
                  fontFamily: "inherit",
                  padding: 0,
                }}
              >
                Изменить
              </button>
            </div>

            {isLoading ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <SkeletonCard /><SkeletonCard /><SkeletonCard />
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {results.quotes.map((rate) => {
                  const isBest = rate.price === minPrice;
                  const isSelected = selectedRate === rate;
                  const showBestBadge =
                    isBest && !rate.badge
                      ? { label: "Лучшая цена", bg: "#EFF6FF", color: "#1D4ED8" }
                      : null;
                  const badgeInfo = rate.badge
                    ? { label: BADGE_LABELS[rate.badge] ?? rate.badge, bg: "#EFF6FF", color: "#1D4ED8" }
                    : showBestBadge;

                  return (
                    <div
                      key={rate.id ?? rate.carrier_code + rate.tariff_name}
                      className="result-card"
                      onClick={() => handleSelectRate(rate)}
                      style={{
                        background: isSelected ? "#EFF6FF" : "#ffffff",
                        borderRadius: 16,
                        border: `1.5px solid ${isSelected ? "#2563EB" : isBest ? "#2563EB" : "#E5E7EB"}`,
                        padding: "20px 24px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 16,
                        cursor: "pointer",
                        boxShadow: isBest ? "0 4px 16px rgba(37,99,235,0.10)" : "0 1px 3px rgba(0,0,0,0.08)",
                        transition: "all 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.boxShadow = "0 4px 16px rgba(37,99,235,0.10)";
                        e.currentTarget.style.transform = "translateY(-2px)";
                        e.currentTarget.style.borderColor = "#2563EB";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.boxShadow = isBest
                          ? "0 4px 16px rgba(37,99,235,0.10)"
                          : "0 1px 3px rgba(0,0,0,0.08)";
                        e.currentTarget.style.transform = "translateY(0)";
                        e.currentTarget.style.borderColor = isSelected || isBest
                          ? "#2563EB"
                          : "#E5E7EB";
                      }}
                    >
                      {/* Carrier info */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
                          <div
                            style={{
                              width: 48,
                              height: 48,
                              borderRadius: 10,
                              background: "#EFF6FF",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              font: "700 20px/1 Inter Variable, sans-serif",
                              color: "#2563EB",
                              flexShrink: 0,
                              overflow: "hidden",
                            }}
                          >
                            {getCarrierLogo(rate.carrier_code) ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img src={getCarrierLogo(rate.carrier_code)!} alt={rate.carrier_name} style={{ width: 40, height: 40, objectFit: "contain" }} />
                            ) : (
                              rate.carrier_name[0]
                            )}
                          </div>
                          <div>
                            <span style={{ font: "600 16px/1 Inter Variable, sans-serif", color: "#111827", marginRight: 8 }}>
                              {rate.carrier_name}
                            </span>
                            <TariffBadge name={rate.tariff_name} />
                            {badgeInfo && (
                              <span
                                style={{
                                  background: badgeInfo.bg,
                                  color: badgeInfo.color,
                                  padding: "3px 10px",
                                  borderRadius: 999,
                                  font: "600 12px/1 Inter Variable, sans-serif",
                                  marginLeft: 6,
                                }}
                              >
                                {badgeInfo.label}
                              </span>
                            )}
                          </div>
                        </div>
                        <div
                          style={{
                            font: "400 13px/1 Inter Variable, sans-serif",
                            color: "#6B7280",
                            display: "flex",
                            gap: 16,
                            alignItems: "center",
                            flexWrap: "wrap",
                          }}
                        >
                          <span>Срок: {rate.eta_days_min}-{rate.eta_days_max} дн.</span>
                          <span>Сбор: по будням</span>
                        </div>
                      </div>

                      {/* Price + CTA */}
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8, flexShrink: 0 }}>
                        <div>
                          <div style={{ font: "700 24px/1 Inter Variable, sans-serif", color: "#111827", textAlign: "right" }}>
                            {formatPrice(rate.price, rate.currency)}
                          </div>
                          <div style={{ font: "400 12px/1 Inter Variable, sans-serif", color: "#9CA3AF", textAlign: "right", marginTop: 4 }}>
                            с НДС
                          </div>
                        </div>
                        <button
                          onClick={(e) => { e.stopPropagation(); void handleSelectRate(rate); }}
                          style={{
                            border: isSelected ? "none" : "1.5px solid #E5E7EB",
                            background: isSelected ? "#2563EB" : "#ffffff",
                            color: isSelected ? "#ffffff" : "#111827",
                            borderRadius: 10,
                            padding: "8px 20px",
                            font: "600 14px/1 Inter Variable, sans-serif",
                            cursor: "pointer",
                            fontFamily: "inherit",
                            transition: "all 0.15s",
                          }}
                          onMouseEnter={(e) => {
                            if (!isSelected) {
                              e.currentTarget.style.background = "#2563EB";
                              e.currentTarget.style.color = "#ffffff";
                              e.currentTarget.style.borderColor = "#2563EB";
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!isSelected) {
                              e.currentTarget.style.background = "#ffffff";
                              e.currentTarget.style.color = "#111827";
                              e.currentTarget.style.borderColor = "#E5E7EB";
                            }
                          }}
                        >
                          {isSelected ? "Выбрано ✓" : "Выбрать"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            {hasResults && (
              <p style={{ font: "400 12px/1.5 Inter Variable, sans-serif", color: "#9CA3AF", margin: "8px 0 0", padding: "0 4px" }}>
                * Расчёт носит предварительный характер и может измениться после контрольного измерения отправления.
              </p>
            )}
          </section>
        )}

        {/* ── STATIC SECTIONS (hidden when results shown) ─────────────── */}
        {!hasResults && (
          <>
            {/* How it works */}
            <section style={{ background: "#ffffff", padding: isMobile ? "56px 20px" : "80px 48px" }}>
              <div style={{ maxWidth: 1200, margin: "0 auto" }}>
                <h2
                  style={{
                    font: "600 32px/1.25 Inter Variable, sans-serif",
                    color: "#111827",
                    textAlign: "center",
                    margin: "0 0 48px",
                  }}
                >
                  Как это работает
                </h2>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(4,1fr)",
                    gap: 24,
                  }}
                >
                  {HOW_IT_WORKS.map(({ step, title, desc }) => (
                    <div key={step} style={{ textAlign: "center" }}>
                      <div
                        style={{
                          width: 48,
                          height: 48,
                          borderRadius: 12,
                          background: "#EFF6FF",
                          color: "#2563EB",
                          font: "700 20px/1 Inter Variable, sans-serif",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          margin: "0 auto 16px",
                        }}
                      >
                        {step}
                      </div>
                      <div style={{ font: "600 18px/1.3 Inter Variable, sans-serif", color: "#111827", marginBottom: 8 }}>
                        {title}
                      </div>
                      <div style={{ font: "400 15px/1.5 Inter Variable, sans-serif", color: "#6B7280" }}>
                        {desc}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            {/* Partners / carriers. Rendered from SUPPORTED_CARRIERS so the strip
                always matches the "N+ служб доставки" claim in the hero — one
                source of truth. */}
            <section style={{ background: "#FAFAFA", borderTop: "1px solid #E5E7EB", padding: isMobile ? "48px 20px" : "56px 48px", textAlign: "center" }}>
              <p style={{ font: "400 15px/1 Inter Variable, sans-serif", color: "#6B7280", margin: "0 0 28px" }}>
                Сравниваем цены ведущих служб в реальном времени
              </p>
              <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap", alignItems: "center" }}>
                {SUPPORTED_CARRIERS.map((c) => (
                  <div
                    key={c.code}
                    style={{
                      background: "#ffffff",
                      border: "1px solid #E5E7EB",
                      borderRadius: 10,
                      padding: "12px 28px",
                      font: "700 16px/1 Inter Variable, sans-serif",
                      color: "#374151",
                      letterSpacing: "0.01em",
                    }}
                  >
                    {c.name}
                  </div>
                ))}
              </div>
            </section>

            {/* Why Novex */}
            <section style={{ background: "#FAFAFA", borderTop: "1px solid #E5E7EB", padding: isMobile ? "56px 20px" : "80px 48px" }}>
              <div style={{ maxWidth: 1200, margin: "0 auto" }}>
                <h2
                  style={{
                    font: "600 32px/1.25 Inter Variable, sans-serif",
                    color: "#111827",
                    textAlign: "center",
                    margin: "0 0 48px",
                  }}
                >
                  Почему Novex
                </h2>
                <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(3,1fr)", gap: 24 }}>
                  {WHY_NOVEX.map(({ icon, title, desc }) => (
                    <div
                      key={title}
                      style={{
                        background: "#ffffff",
                        borderRadius: 16,
                        border: "1px solid #E5E7EB",
                        padding: "28px 24px",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                      }}
                    >
                      <div
                        style={{
                          width: 44,
                          height: 44,
                          borderRadius: 10,
                          background: "#EFF6FF",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          marginBottom: 16,
                        }}
                      >
                        {icon}
                      </div>
                      <div style={{ font: "600 20px/1.3 Inter Variable, sans-serif", color: "#111827", marginBottom: 8 }}>
                        {title}
                      </div>
                      <div style={{ font: "400 15px/1.6 Inter Variable, sans-serif", color: "#6B7280" }}>
                        {desc}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            {/* FAQ */}
            <section id="help" style={{ background: "#ffffff", padding: isMobile ? "56px 20px" : "80px 48px" }}>
              <div style={{ maxWidth: 1200, margin: "0 auto", display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1.5fr", gap: 64 }}>
                <div>
                  <h2 style={{ font: "600 32px/1.25 Inter Variable, sans-serif", color: "#111827", margin: "0 0 16px" }}>
                    Часто задаваемые вопросы
                  </h2>
                  <p style={{ font: "400 16px/1.6 Inter Variable, sans-serif", color: "#6B7280", margin: "0 0 28px" }}>
                    Не нашли ответ? Напишите нам.
                  </p>
                  <a
                    href={`mailto:${CONTACTS.supportEmail}`}
                    style={{
                      display: "inline-block",
                      border: "1.5px solid #E5E7EB",
                      background: "#ffffff",
                      color: "#111827",
                      borderRadius: 10,
                      padding: "12px 24px",
                      font: "600 15px/1 Inter Variable, sans-serif",
                      textDecoration: "none",
                      transition: "background 0.15s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#F9FAFB")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "#ffffff")}
                  >
                    Написать в поддержку
                  </a>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                  {FAQ_ITEMS.map((item, i) => {
                    const isOpen = openFaq === i;
                    return (
                      <div
                        key={i}
                        style={{ borderBottom: "1px solid #E5E7EB" }}
                      >
                        <button
                          onClick={() => setOpenFaq(isOpen ? null : i)}
                          style={{
                            width: "100%",
                            background: "none",
                            border: "none",
                            padding: "20px 0",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            cursor: "pointer",
                            font: "500 16px/1.4 Inter Variable, sans-serif",
                            color: "#111827",
                            textAlign: "left",
                            gap: 16,
                            fontFamily: "inherit",
                          }}
                        >
                          {item.q}
                          {isOpen
                            ? <ChevronUp size={18} color="#2563EB" style={{ flexShrink: 0 }} />
                            : <ChevronDown size={18} color="#9CA3AF" style={{ flexShrink: 0 }} />
                          }
                        </button>
                        {isOpen && (
                          <div
                            style={{
                              padding: "0 0 20px",
                              font: "400 15px/1.6 Inter Variable, sans-serif",
                              color: "#6B7280",
                            }}
                          >
                            {item.a}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </section>
          </>
        )}
      </main>

      <Footer />

      {/* ── SIDE PANEL (rate details) ──────────────────────────────────── */}
      {selectedRate && (
        <>
          <div
            style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.3)", zIndex: 199 }}
            onClick={() => setSelectedRate(null)}
          />
          <div
            style={{
              position: "fixed",
              right: 0,
              top: 0,
              bottom: 0,
              width: isMobile ? "100%" : 420,
              background: "#ffffff",
              boxShadow: "-4px 0 32px rgba(0,0,0,0.12)",
              overflowY: "auto",
              padding: isMobile ? "24px 20px" : 32,
              zIndex: 200,
              animation: "slideInRight 0.2s ease",
            }}
          >
            <button
              onClick={() => setSelectedRate(null)}
              style={{
                position: "absolute",
                top: 20,
                right: 20,
                width: 36,
                height: 36,
                borderRadius: "50%",
                border: "1px solid #E5E7EB",
                background: "#ffffff",
                cursor: "pointer",
                fontSize: 18,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#6B7280",
                fontFamily: "inherit",
              }}
            >
              ×
            </button>

            <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 20 }}>
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 12,
                  background: "#EFF6FF",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  font: "700 24px/1 Inter Variable, sans-serif",
                  color: "#2563EB",
                  overflow: "hidden",
                }}
              >
                {getCarrierLogo(selectedRate.carrier_code) ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={getCarrierLogo(selectedRate.carrier_code)!} alt={selectedRate.carrier_name} style={{ width: 48, height: 48, objectFit: "contain" }} />
                ) : (
                  selectedRate.carrier_name[0]
                )}
              </div>
              <div>
                <div style={{ font: "700 18px/1 Inter Variable, sans-serif", color: "#111827" }}>
                  {selectedRate.carrier_name}
                </div>
                <span style={{ background: "#D1FAE5", color: "#065F46", padding: "3px 10px", borderRadius: 999, font: "600 12px/1 Inter Variable, sans-serif" }}>
                  Активен
                </span>
              </div>
            </div>

            <hr style={{ border: "none", borderTop: "1px solid #E5E7EB", margin: "0 0 20px" }} />

            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 20 }}>
              <DetailRow label="Тариф" value={selectedRate.tariff_name} />
              <DetailRow label="Срок доставки" value={`${selectedRate.eta_days_min}-${selectedRate.eta_days_max} рабочих дней`} />
              {/* Доп. услуги (страхование, хрупкий груз, звонок перед доставкой) — все
                  три интегрированных перевозчика их поддерживают, конкретный набор и
                  цена уточняются на шаге оформления. Раньше здесь был хардкод
                  "Страховка: Нет" и "Ограничения: 30 кг · 150×150×150 см", что не
                  соответствовало реальности ни одного из перевозчиков. */}
              <DetailRow label="Доп. услуги" value="Страхование, хрупкий груз — на след. шаге" muted />
            </div>

            <hr style={{ border: "none", borderTop: "1px solid #E5E7EB", margin: "0 0 20px" }} />

            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 24 }}>
              <DetailRow label="Маршрут" value={`${form.fromCity} → ${form.toCity}`} />
              <DetailRow label="Груз" value={`${form.weightKg} кг × ${form.quantity} шт · ${form.shipmentType === "parcel" ? "Посылка" : "Документ"}`} />
              <DetailRow label="Расчётный вес" value={`${chargeable.toFixed(2)} кг`} />
            </div>

            <div style={{ textAlign: "center", marginBottom: 24 }}>
              <div style={{ font: "700 32px/1 Inter Variable, sans-serif", color: "#111827" }}>
                {formatPrice(selectedRate.price, selectedRate.currency)}
              </div>
              <div style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#9CA3AF", marginTop: 4 }}>
                с НДС · тенге
              </div>
            </div>

            <button
              onClick={handleProceed}
              disabled={isSelectingRate}
              style={{
                width: "100%",
                height: 52,
                background: isSelectingRate ? "#93C5FD" : "#2563EB",
                color: "#ffffff",
                borderRadius: 10,
                font: "600 16px/1 Inter Variable, sans-serif",
                border: "none",
                cursor: isSelectingRate ? "not-allowed" : "pointer",
                fontFamily: "inherit",
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => {
                if (!isSelectingRate) e.currentTarget.style.background = "#1D4ED8";
              }}
              onMouseLeave={(e) => {
                if (!isSelectingRate) e.currentTarget.style.background = "#2563EB";
              }}
            >
              {isSelectingRate ? "Оформляем..." : "Оформить доставку →"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
