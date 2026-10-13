"use client";

import { useEffect, useRef, useState } from "react";
import { Package, FileText, Clock, MapPin, Star, ChevronDown, ChevronUp } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import { CONTACTS } from "@/lib/config/contacts";
import { getCarrierLogo, LANDING_STATS, SUPPORTED_CARRIERS } from "@/lib/config/landing";
import { clearHomeQuote, loadHomeQuote, saveHomeQuote } from "@/lib/home-quote-store";
import CitySelect from "@/components/ui/CitySelect";
import { cityLabel } from "@/lib/cities";
import { ApiError, calculateShippingQuote, getShippingQuote, selectShippingQuote } from "@/lib/api/shipping";
import type { RateQuoteItem, ShipmentType, ShippingQuoteResponse } from "@/types/quote";
import { Link, useRouter } from "@/i18n/navigation";

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

// True once HomePage has mounted in this document (page load). Distinguishes
// "the page was just (re)loaded" from "the customer came back here inside the app".
let homeMountedInDocument = false;

/** Do two forms describe the same calculation? (Dimensions only matter for parcels.) */
function sameCalcParams(a: FormState, b: FormState): boolean {
  if (a.fromCity.trim() !== b.fromCity.trim() || a.toCity.trim() !== b.toCity.trim()) return false;
  if (a.shipmentType !== b.shipmentType) return false;
  if (Number(a.weightKg) !== Number(b.weightKg) || Number(a.quantity) !== Number(b.quantity)) return false;
  if (a.shipmentType !== "document") {
    return (
      Number(a.widthCm) === Number(b.widthCm) &&
      Number(a.heightCm) === Number(b.heightCm) &&
      Number(a.depthCm) === Number(b.depthCm)
    );
  }
  return true;
}

/** One shipping calculation for the given form (no React state touched). */
async function requestQuote(f: FormState): Promise<ShippingQuoteResponse> {
  const isDoc = f.shipmentType === "document";
  return calculateShippingQuote({
    from_country: "KZ",
    from_city: f.fromCity.trim(),
    to_country: "KZ",
    to_city: f.toCity.trim(),
    shipment_type: f.shipmentType,
    weight_kg: Number(f.weightKg),
    quantity: Number(f.quantity),
    width_cm: isDoc ? 0 : (Number(f.widthCm) || 0),
    height_cm: isDoc ? 0 : (Number(f.heightCm) || 0),
    depth_cm: isDoc ? 0 : (Number(f.depthCm) || 0),
  });
}

/** Поле формы → ключ перевода его ошибки (namespace "home"). */
type FieldErrors = Partial<Record<keyof FormState, string>>;

// Порядок полей на экране: фокус уходит на первое поле с ошибкой.
const FIELD_ORDER: (keyof FormState)[] = [
  "fromCity", "toCity", "weightKg", "quantity", "widthCm", "heightCm", "depthCm",
];

const fieldId = (key: keyof FormState) => `quote-${key}`;

/** Проверяет все поля сразу. Пустой объект - форма в порядке. */
function validateQuoteForm(form: FormState): FieldErrors {
  const errors: FieldErrors = {};
  if (!form.fromCity.trim()) errors.fromCity = "errors.fromCity";
  if (!form.toCity.trim()) errors.toCity = "errors.toCity";

  const weight = Number(form.weightKg);
  const qty = Number(form.quantity);

  if (!form.weightKg.trim() || isNaN(weight) || weight <= 0) errors.weightKg = "errors.weight";
  else if (weight > 1000) errors.weightKg = "errors.weightMax";

  if (!form.quantity.trim() || isNaN(qty) || qty <= 0) errors.quantity = "errors.quantity";
  else if (!Number.isInteger(qty)) errors.quantity = "errors.quantityInt";
  else if (qty > 999) errors.quantity = "errors.quantityMax";

  if (form.shipmentType !== "document") {
    // Dimensions are required for parcels - used for volumetric weight (Azimuth
    // tariff table) and mandatory in CSE SaveWaybillOffice (Length/Width/Height).
    // Making them required here avoids a surprise validation error at the order
    // step where they are always required.
    const dims = [
      ["widthCm", "errors.width"],
      ["heightCm", "errors.height"],
      ["depthCm", "errors.depth"],
    ] as const;
    for (const [key, emptyError] of dims) {
      const v = Number(form[key]);
      if (!form[key].trim() || isNaN(v) || v <= 0) errors[key] = emptyError;
      else if (v > 500) errors[key] = "errors.dimsMax";
    }
  }
  return errors;
}

const hasErrors = (errors: FieldErrors) => Object.keys(errors).length > 0;

// Значения - ключи перевода (namespace "home").
const BADGE_LABELS: Record<string, string> = {
  fastest: "badges.fastest",
  recommended: "badges.recommended",
  best_value: "badges.bestValue",
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
    <span style={{ background: bg, color, padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, lineHeight: 1.25, whiteSpace: "nowrap" }}>
      {name}
    </span>
  );
}

function DetailRow({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span style={{ fontSize: 13, color: "#5F6E7E" }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 600, color: muted ? "#9CA3AF" : "#0E1826" }}>{value}</span>
    </div>
  );
}

const LABEL_STYLE: React.CSSProperties = {
  display: "block",
  font: "500 13px/1 Inter Variable, sans-serif",
  color: "#374151",
  marginBottom: 6,
};

/** Текст ошибки под полем; связан с полем через aria-describedby. */
function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <div id={id} style={{ marginTop: 6, font: "400 12px/1.35 Inter Variable, sans-serif", color: "#B91C1C" }}>
      {message}
    </div>
  );
}

function InputField({
  id,
  label,
  value,
  onChange,
  placeholder,
  error,
  required = true,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  error?: string;
  required?: boolean;
}) {
  const [focused, setFocused] = useState(false);
  const errorId = `${id}-error`;
  return (
    <div>
      <label htmlFor={id} style={LABEL_STYLE}>
        {label}
      </label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        inputMode="decimal"
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          width: "100%",
          border: error ? "1.5px solid #DC2626" : focused ? "1.5px solid #0B2545" : "1.5px solid #E2E8EE",
          borderRadius: 10,
          padding: "12px 14px",
          font: "400 15px/1 Inter Variable, sans-serif",
          color: "#0E1826",
          background: "#fff",
          outline: "none",
          boxShadow: focused
            ? error ? "0 0 0 3px rgba(220,38,38,0.15)" : "0 0 0 3px rgba(11,37,69,0.15)"
            : "none",
          transition: "border-color 0.15s, box-shadow 0.15s",
          boxSizing: "border-box",
        }}
      />
      <FieldError id={errorId} message={error} />
    </div>
  );
}

/* ─── Static sections ────────────────────────────────────────────────────── */

const HOW_IT_WORKS = [
  { step: 1, title: "how.s1.title", desc: "how.s1.desc" },
  { step: 2, title: "how.s2.title", desc: "how.s2.desc" },
  { step: 3, title: "how.s3.title", desc: "how.s3.desc" },
  { step: 4, title: "how.s4.title", desc: "how.s4.desc" },
];

const WHY_NOVEX = [
  {
    icon: <Star size={24} color="#0B2545" />,
    title: "why.prices.title",
    desc: "why.prices.desc",
  },
  {
    icon: <Clock size={24} color="#0B2545" />,
    title: "why.fast.title",
    desc: "why.fast.desc",
  },
  {
    icon: <MapPin size={24} color="#0B2545" />,
    title: "why.tracking.title",
    desc: "why.tracking.desc",
  },
];

const FAQ_ITEMS = [
  {
    q: "faq.q1.q",
    a: "faq.q1.a",
  },
  {
    q: "faq.q2.q",
    a: "faq.q2.a",
  },
  {
    q: "faq.q3.q",
    a: "faq.q3.a",
  },
  {
    q: "faq.q4.q",
    a: "faq.q4.a",
  },
];

/* ─── Main page ──────────────────────────────────────────────────────────── */

export default function HomePage() {
  const router = useRouter();
  const t = useTranslations("home");
  const locale = useLocale();
  const isMobile = useIsMobile();

  const [form, setForm] = useState<FormState>(initialForm);

  const [results, setResults] = useState<ShippingQuoteResponse | null>(null);
  // The form the prices in `results` were calculated for. The summary, the
  // price card and the saved snapshot must show THESE values — never the live
  // form, which the customer may have edited since pressing «Рассчитать».
  const [calcForm, setCalcForm] = useState<FormState | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Ошибки проверки формы - показываются под своими полями после «Рассчитать».
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
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
    // Поле исправляют - его ошибка больше не актуальна (проверим снова при отправке).
    setFieldErrors((prev) => {
      if (!(key in prev)) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  useEffect(() => {
    if (results) {
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    }
  }, [results]);

  // Coming back from the order form (browser «Назад», «На главную», «Изменить
  // тариф»): restore the calculation the customer left, so cities, parcel
  // parameters and the tariff list are all still there.
  useEffect(() => {
    // First mount after a page load: restore ONLY when the document itself came
    // from history (back / forward). A refresh, a typed address or a link must
    // start from a clean form — sessionStorage survives a reload, so without
    // this check «обновить страницу» never reset anything.
    if (!homeMountedInDocument) {
      homeMountedInDocument = true;
      const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
      if (nav?.type !== "back_forward") {
        clearHomeQuote();
        return;
      }
    }
    // Later mounts in the same document are in-app navigation («К тарифам»,
    // «Изменить», browser back inside the app) — those restore the calculation.
    const snapshot = loadHomeQuote();
    if (!snapshot) return;
    setForm((prev) => ({ ...prev, ...snapshot.form }));
    const saved = snapshot.results;
    if (!saved) return;
    setResults(saved);
    setCalcForm({ ...initialForm, ...snapshot.form });
    // The quote session may have expired meanwhile — re-check it. On success
    // use the fresh data; on failure keep the form and ask for a new calculation.
    getShippingQuote(saved.quote_session_id, saved.public_token)
      .then((fresh) => {
        // The GET response has NO public_token — keep ours, otherwise every
        // «Выбрать» fails with «Расчёт недоступен».
        const merged = { ...fresh, public_token: saved.public_token };
        if (JSON.stringify(merged.quotes) !== JSON.stringify(saved.quotes)) setResults(merged);
      })
      .catch(() => {
        // Session expired / gone: recalculate by ourselves from the saved form
        // so the customer does not have to press «Рассчитать» again.
        requestQuote(snapshot.form)
          .then((res) => { setResults(res); setCalcForm({ ...initialForm, ...snapshot.form }); saveHomeQuote(snapshot.form, res); })
          .catch(() => { setResults(null); setCalcForm(null); clearHomeQuote(); });
      });
  }, []);

  useEffect(() => {
    const handler = () => {
      setResults(null);
      setCalcForm(null);
      setSelectedRate(null);
      setError(null);
      setFieldErrors({});
      clearHomeQuote();
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
    const errors = validateQuoteForm(form);
    setFieldErrors(errors);
    if (hasErrors(errors)) {
      const first = FIELD_ORDER.find((k) => errors[k]);
      if (first) document.getElementById(fieldId(first))?.focus();
      return;
    }

    setIsLoading(true);
    setResults(null);
    setSelectedRate(null);
    try {
      const res = await requestQuote(form);
      setResults(res);
      setCalcForm(form);
      saveHomeQuote(form, res);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : t("errors.calcFailed"));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSelectRate(rate: RateQuoteItem) {
    if (!results || rate.id === null) return;
    if (isStale) {
      setError(t("errors.paramsChanged"));
      return;
    }
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
      // 403 / 404 / 410 = the calculation is gone or its token is invalid. Don't
      // make the customer start over: recalculate with the same form and pick
      // the same carrier + tariff in the fresh results.
      const base = calcForm ?? form;
      if (err instanceof ApiError && [403, 404, 410].includes(err.status) && !hasErrors(validateQuoteForm(base))) {
        try {
          const fresh = await requestQuote(base);
          setResults(fresh);
          setCalcForm(base);
          saveHomeQuote(base, fresh);
          const same = fresh.quotes.find(
            (q) => q.carrier_code === rate.carrier_code && q.tariff_name === rate.tariff_name && q.id !== null,
          );
          if (same) {
            await selectShippingQuote(fresh.quote_session_id, { rate_quote_id: same.id as number }, fresh.public_token);
            setSelectedRate(same);
          } else {
            setError(t("errors.ratesUpdated"));
          }
          return;
        } catch {
          /* fall through to the generic message below */
        }
      }
      setError(err instanceof ApiError ? err.detail : t("errors.selectFailed"));
    } finally {
      setIsSelectingRate(false);
    }
  }

  function handleProceed() {
    if (!selectedRate || !results) return;
    // Remember the calculation for «Назад» — the form it was calculated for, not
    // whatever is typed in the fields now.
    saveHomeQuote(calcForm ?? form, results);
    const token = results.public_token;
    router.push(
      `/quote/shipment?quoteSessionId=${results.quote_session_id}${token ? `&token=${token}` : ""}`,
    );
  }

  /** Переведённый текст ошибки поля или undefined. */
  const fieldError = (key: keyof FormState) => {
    const k = fieldErrors[key];
    return k ? t(k) : undefined;
  };

  const hasResults = results !== null;
  const minPrice = results ? Math.min(...results.quotes.map((q) => q.price)) : null;
  // Everything below the form describes the CALCULATED parameters.
  const shown = calcForm ?? form;
  const isStale = hasResults && calcForm !== null && !sameCalcParams(form, calcForm);
  const chargeable = shown.shipmentType === "document"
    ? Number(shown.weightKg) * Number(shown.quantity)
    : calcChargeable(
        Number(shown.weightKg),
        Number(shown.widthCm),
        Number(shown.heightCm),
        Number(shown.depthCm),
        Number(shown.quantity),
      );

  return (
    <div style={{ minHeight: "100vh", background: "#FAFAFA" }}>
      <Navbar />

      <main>
        {/* ── HERO ──────────────────────────────────────────────────────── */}
        <section
          style={{
            background: "linear-gradient(160deg, #F1F5F9 0%, #F8FAFF 45%, #F0FDF4 100%)",
            padding: isMobile ? "56px 20px 64px" : "88px 48px 96px",
            textAlign: "center",
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* Decorative background blobs */}
          <div style={{ position: "absolute", top: -60, left: -80, width: 320, height: 320, borderRadius: "50%", background: "rgba(11,37,69,0.06)", pointerEvents: "none" }} />
          <div style={{ position: "absolute", bottom: -80, right: -60, width: 280, height: 280, borderRadius: "50%", background: "rgba(16,185,129,0.05)", pointerEvents: "none" }} />
          <div
            style={{
              font: "500 13px/1 Inter Variable, sans-serif",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "#0B2545",
              marginBottom: 16,
            }}
          >
            {t("hero.eyebrow")}
          </div>
          <h1
            style={{
              font: `700 ${isMobile ? "32px" : "48px"}/1.12 'Space Grotesk Variable', 'Inter Variable', sans-serif`,
              letterSpacing: "-0.02em",
              color: "#0E1826",
              margin: "0 auto 16px",
              maxWidth: 640,
            }}
          >
            {t("hero.title")}
          </h1>
          <p
            style={{
              font: "400 18px/1.6 Inter Variable, sans-serif",
              color: "#5F6E7E",
              margin: "0 auto 40px",
              maxWidth: 520,
            }}
          >
            {t("hero.subtitle")}
          </p>

          {/* ── FORM CARD ────────────────────────────────────────────── */}
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #E2E8EE",
              borderRadius: 24,
              boxShadow: "0 20px 60px rgba(11,37,69,0.10), 0 4px 16px rgba(0,0,0,0.06)",
              padding: isMobile ? "24px 20px" : "36px 36px",
              maxWidth: 940,
              margin: "0 auto",
              textAlign: "left",
              position: "relative",
              zIndex: 10,
            }}
          >
            {/* noValidate: пустые поля проверяем сами и пишем ошибку под полем,
                а не всплывающей подсказкой браузера. */}
            <form onSubmit={handleSubmit} noValidate>
              {/* Row 1: route + shipment type */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr 220px",
                  gap: 14,
                  // По верху: текст ошибки под одним полем не сдвигает соседние.
                  alignItems: "start",
                  marginBottom: 18,
                }}
              >
                <div>
                  <label htmlFor={fieldId("fromCity")} style={LABEL_STYLE}>
                    {t("form.from")}
                  </label>
                  <CitySelect
                    id={fieldId("fromCity")}
                    value={form.fromCity}
                    onChange={(v) => setField("fromCity", v)}
                    placeholder={t("form.fromPlaceholder")}
                    invalid={!!fieldErrors.fromCity}
                    describedBy={fieldErrors.fromCity ? `${fieldId("fromCity")}-error` : undefined}
                  />
                  <FieldError id={`${fieldId("fromCity")}-error`} message={fieldError("fromCity")} />
                </div>
                <div>
                  <label htmlFor={fieldId("toCity")} style={LABEL_STYLE}>
                    {t("form.to")}
                  </label>
                  <CitySelect
                    id={fieldId("toCity")}
                    value={form.toCity}
                    onChange={(v) => setField("toCity", v)}
                    placeholder={t("form.toPlaceholder")}
                    invalid={!!fieldErrors.toCity}
                    describedBy={fieldErrors.toCity ? `${fieldId("toCity")}-error` : undefined}
                  />
                  <FieldError id={`${fieldId("toCity")}-error`} message={fieldError("toCity")} />
                </div>
                <div>
                  <div style={LABEL_STYLE}>
                    {t("form.what")}
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    {(["parcel", "document"] as ShipmentType[]).map((type) => {
                      const active = form.shipmentType === type;
                      return (
                        <button
                          key={type}
                          type="button"
                          onClick={() => setField("shipmentType", type)}
                          style={{
                            flex: 1,
                            border: active ? "1.5px solid #0B2545" : "1.5px solid #E2E8EE",
                            background: active ? "#F1F5F9" : "#ffffff",
                            color: active ? "#0B2545" : "#5F6E7E",
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
                          {type === "parcel" ? <Package size={14} /> : <FileText size={14} />}
                          {type === "parcel" ? t("form.parcel") : t("form.document")}
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
                  alignItems: "start",
                }}
              >
                <InputField id={fieldId("weightKg")} label={t("form.weight")} value={form.weightKg} onChange={(v) => setField("weightKg", v)} placeholder="2.5" error={fieldError("weightKg")} />
                <InputField id={fieldId("quantity")} label={t("form.quantity")} value={form.quantity} onChange={(v) => setField("quantity", v)} placeholder="1" error={fieldError("quantity")} />
                {form.shipmentType !== "document" && (
                  <>
                    <InputField id={fieldId("widthCm")} label={t("form.width")} value={form.widthCm} onChange={(v) => setField("widthCm", v)} placeholder="20" error={fieldError("widthCm")} />
                    <InputField id={fieldId("heightCm")} label={t("form.height")} value={form.heightCm} onChange={(v) => setField("heightCm", v)} placeholder="15" error={fieldError("heightCm")} />
                    <InputField id={fieldId("depthCm")} label={t("form.depth")} value={form.depthCm} onChange={(v) => setField("depthCm", v)} placeholder="10" error={fieldError("depthCm")} />
                  </>
                )}

                <button
                  type="submit"
                  disabled={isLoading}
                  style={{
                    // Ряд выровнен по верху - кнопку опускаем на высоту подписи
                    // (13px + отступ 6px) и ещё на 2px: кнопка 41px по центру поля 45px.
                    marginTop: isMobile ? 0 : 21,
                    background: isLoading ? "#94A6C0" : "#0B2545",
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
                    if (!isLoading) e.currentTarget.style.background = "#0E2E5C";
                  }}
                  onMouseLeave={(e) => {
                    if (!isLoading) e.currentTarget.style.background = "#0B2545";
                  }}
                >
                  {isLoading ? t("form.calculating") : isStale ? t("form.recalculate") : t("form.calculate")}
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
              (shipments/rating) render only when their env var is set - hides
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
                  color: "#5F6E7E",
                }}
              >
                <span><b style={{ color: "#0E1826" }}>{carriersLabel}</b> {t("stats.carriers")}</span>
                {LANDING_STATS.shipmentsLabel && (
                  <>
                    <span style={{ color: "#D1D5DB" }}>|</span>
                    <span><b style={{ color: "#0E1826" }}>{LANDING_STATS.shipmentsLabel}</b> {t("stats.shipments")}</span>
                  </>
                )}
                {LANDING_STATS.ratingLabel && (
                  <>
                    <span style={{ color: "#D1D5DB" }}>|</span>
                    <span><b style={{ color: "#10B981" }}>{LANDING_STATS.ratingLabel}</b> {t("stats.rating")}</span>
                  </>
                )}
              </div>
            );
          })()}

          {/* Mini how-it-works - shown only before results */}
        </section>

        {/* ── RESULTS (inline, appears below form) ──────────────────────── */}
        {/* Во время расчёта прошлые результаты уже сброшены - секция показывает скелетоны. */}
        {(hasResults || isLoading) && (
          <section
            ref={resultsRef}
            aria-busy={isLoading}
            style={{
              maxWidth: 900,
              margin: "0 auto",
              padding: "0 20px 80px",
            }}
          >
            {/* Summary bar */}
            {hasResults && (
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
                <span style={{ font: "600 18px/1 Inter Variable, sans-serif", color: "#0E1826" }}>
                  {cityLabel(shown.fromCity, locale)} → {cityLabel(shown.toCity, locale)}
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
                  {shown.weightKg} {t("units.kg")} · {shown.shipmentType === "parcel" ? t("form.parcel") : t("form.document")}
                </span>
              </div>
              <button
                onClick={() => { setResults(null); setCalcForm(null); setSelectedRate(null); }}
                style={{
                  background: "none",
                  border: "none",
                  color: "#0B2545",
                  font: "500 14px/1 Inter Variable, sans-serif",
                  cursor: "pointer",
                  textDecoration: "underline",
                  fontFamily: "inherit",
                  padding: 0,
                }}
              >
                {t("results.edit")}
              </button>
            </div>
            )}

            {isStale && !isLoading && (
              <div
                role="status"
                style={{
                  marginBottom: 16,
                  padding: "12px 16px",
                  borderRadius: 12,
                  background: "#F8FAFC",
                  border: "1px solid #E2E8EE",
                  color: "#0B2545",
                  font: "500 14px/1.5 Inter Variable, sans-serif",
                }}
              >
                {t.rich("results.staleNotice", {
                  route: `${cityLabel(shown.fromCity, locale)} → ${cityLabel(shown.toCity, locale)}, ${shown.weightKg} ${t("units.kg")}`,
                  b: (chunks) => <b>{chunks}</b>,
                })}
              </div>
            )}

            {isLoading ? (
              <div className="skeleton-group" style={{ display: "flex", flexDirection: "column", gap: 12, paddingTop: 8 }}>
                <SkeletonCard /><SkeletonCard /><SkeletonCard />
              </div>
            ) : results && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12, opacity: isStale ? 0.5 : 1, transition: "opacity 0.15s" }}>
                {results.quotes.map((rate) => {
                  const isBest = rate.price === minPrice;
                  const isSelected = selectedRate === rate;
                  const showBestBadge =
                    isBest && !rate.badge
                      ? { label: t("badges.bestValue"), bg: "#F1F5F9", color: "#0E2E5C" }
                      : null;
                  const badgeInfo = rate.badge
                    ? { label: BADGE_LABELS[rate.badge] ? t(BADGE_LABELS[rate.badge]) : rate.badge, bg: "#F1F5F9", color: "#0E2E5C" }
                    : showBestBadge;

                  return (
                    <div
                      key={rate.id ?? rate.carrier_code + rate.tariff_name}
                      className="result-card"
                      onClick={() => handleSelectRate(rate)}
                      style={{
                        background: isSelected ? "#F1F5F9" : "#ffffff",
                        borderRadius: 16,
                        border: `1.5px solid ${isSelected ? "#22C9E0" : isBest ? "#0B2545" : "#E2E8EE"}`,
                        padding: isMobile ? "16px" : "20px 24px",
                        display: "flex",
                        flexDirection: isMobile ? "column" : "row",
                        alignItems: isMobile ? "stretch" : "center",
                        justifyContent: "space-between",
                        gap: isMobile ? 14 : 16,
                        cursor: "pointer",
                        boxShadow: isSelected
                          ? "0 0 0 4px rgba(34,201,224,0.18)"
                          : isBest
                            ? "0 4px 16px rgba(11,37,69,0.10)"
                            : "0 1px 3px rgba(0,0,0,0.08)",
                        transition: "all 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        if (isSelected) return;
                        e.currentTarget.style.boxShadow = "0 4px 16px rgba(11,37,69,0.10)";
                        e.currentTarget.style.transform = "translateY(-2px)";
                        e.currentTarget.style.borderColor = "#0B2545";
                      }}
                      onMouseLeave={(e) => {
                        if (isSelected) return;
                        e.currentTarget.style.boxShadow = isBest
                          ? "0 4px 16px rgba(11,37,69,0.10)"
                          : "0 1px 3px rgba(0,0,0,0.08)";
                        e.currentTarget.style.transform = "translateY(0)";
                        e.currentTarget.style.borderColor = isBest ? "#0B2545" : "#E2E8EE";
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
                              background: "#F1F5F9",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              font: "700 20px/1 Inter Variable, sans-serif",
                              color: "#0B2545",
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
                          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6, minWidth: 0 }}>
                            <span style={{ font: "600 16px/1.25 Inter Variable, sans-serif", color: "#0E1826", marginRight: 2 }}>
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
                                  font: "600 12px/1.25 Inter Variable, sans-serif",
                                  whiteSpace: "nowrap",
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
                            color: "#5F6E7E",
                            display: "flex",
                            gap: 16,
                            alignItems: "center",
                            flexWrap: "wrap",
                          }}
                        >
                          <span>{t("results.eta", { min: rate.eta_days_min, max: rate.eta_days_max })}</span>
                          <span>{t("results.pickup")}</span>
                        </div>
                      </div>

                      {/* Price + CTA */}
                      <div
                        style={isMobile ? {
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: 12,
                          paddingTop: 14,
                          borderTop: "1px solid #EEF2F6",
                        } : {
                          display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8, flexShrink: 0,
                        }}
                      >
                        <div style={{ minWidth: 0 }}>
                          <div style={{ font: `700 ${isMobile ? 22 : 24}px/1 'Space Grotesk Variable', 'Inter Variable', sans-serif`, color: "#0E1826", textAlign: isMobile ? "left" : "right", whiteSpace: "nowrap" }}>
                            {formatPrice(rate.price, rate.currency)}
                          </div>
                          <div style={{ font: "400 12px/1 Inter Variable, sans-serif", color: "#9CA3AF", textAlign: isMobile ? "left" : "right", marginTop: 4 }}>
                            {t("results.withVat")}
                          </div>
                        </div>
                        <button
                          onClick={(e) => { e.stopPropagation(); void handleSelectRate(rate); }}
                          disabled={isStale}
                          title={isStale ? t("results.staleTitle") : undefined}
                          style={{
                            border: isSelected ? "none" : "1.5px solid #E2E8EE",
                            background: isSelected ? "#0B2545" : "#ffffff",
                            color: isSelected ? "#ffffff" : "#0E1826",
                            borderRadius: 10,
                            padding: isMobile ? "10px 20px" : "8px 20px",
                            font: "600 14px/1 Inter Variable, sans-serif",
                            cursor: isStale ? "not-allowed" : "pointer",
                            fontFamily: "inherit",
                            transition: "all 0.15s",
                            flexShrink: 0,
                          }}
                          onMouseEnter={(e) => {
                            if (!isSelected) {
                              e.currentTarget.style.background = "#0B2545";
                              e.currentTarget.style.color = "#ffffff";
                              e.currentTarget.style.borderColor = "#0B2545";
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!isSelected) {
                              e.currentTarget.style.background = "#ffffff";
                              e.currentTarget.style.color = "#0E1826";
                              e.currentTarget.style.borderColor = "#E2E8EE";
                            }
                          }}
                        >
                          {isSelected ? t("results.selected") : t("results.select")}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            {hasResults && (
              <p style={{ font: "400 12px/1.5 Inter Variable, sans-serif", color: "#9CA3AF", margin: "8px 0 0", padding: "0 4px" }}>
                {t("results.disclaimer")}
              </p>
            )}
          </section>
        )}

        {/* ── STATIC SECTIONS (hidden when results or skeletons shown) ── */}
        {!hasResults && !isLoading && (
          <>
            {/* How it works */}
            <section style={{ background: "#ffffff", padding: isMobile ? "56px 20px" : "80px 48px" }}>
              <div style={{ maxWidth: 1200, margin: "0 auto" }}>
                <h2
                  style={{
                    font: "600 32px/1.25 'Space Grotesk Variable', 'Inter Variable', sans-serif",
                    color: "#0E1826",
                    textAlign: "center",
                    margin: "0 0 48px",
                  }}
                >
                  {t("how.title")}
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
                          background: "#F1F5F9",
                          color: "#0B2545",
                          font: "700 20px/1 Inter Variable, sans-serif",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          margin: "0 auto 16px",
                        }}
                      >
                        {step}
                      </div>
                      <div style={{ font: "600 18px/1.3 Inter Variable, sans-serif", color: "#0E1826", marginBottom: 8 }}>
                        {t(title)}
                      </div>
                      <div style={{ font: "400 15px/1.5 Inter Variable, sans-serif", color: "#5F6E7E" }}>
                        {t(desc)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            {/* Partners / carriers. Rendered from SUPPORTED_CARRIERS so the strip
                always matches the "N+ служб доставки" claim in the hero - one
                source of truth. */}
            <section style={{ background: "#FAFAFA", borderTop: "1px solid #E2E8EE", padding: isMobile ? "48px 20px" : "56px 48px", textAlign: "center" }}>
              <p style={{ font: "400 15px/1 Inter Variable, sans-serif", color: "#5F6E7E", margin: "0 0 28px" }}>
                {t("carriersStrip")}
              </p>
              <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap", alignItems: "center" }}>
                {SUPPORTED_CARRIERS.map((c) => (
                  <div
                    key={c.code}
                    style={{
                      background: "#ffffff",
                      border: "1px solid #E2E8EE",
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
            <section style={{ background: "#FAFAFA", borderTop: "1px solid #E2E8EE", padding: isMobile ? "56px 20px" : "80px 48px" }}>
              <div style={{ maxWidth: 1200, margin: "0 auto" }}>
                <h2
                  style={{
                    font: "600 32px/1.25 'Space Grotesk Variable', 'Inter Variable', sans-serif",
                    color: "#0E1826",
                    textAlign: "center",
                    margin: "0 0 48px",
                  }}
                >
                  {t("why.title")}
                </h2>
                <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(3,1fr)", gap: 24 }}>
                  {WHY_NOVEX.map(({ icon, title, desc }) => (
                    <div
                      key={title}
                      style={{
                        background: "#ffffff",
                        borderRadius: 16,
                        border: "1px solid #E2E8EE",
                        padding: "28px 24px",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                      }}
                    >
                      <div
                        style={{
                          width: 44,
                          height: 44,
                          borderRadius: 10,
                          background: "#F1F5F9",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          marginBottom: 16,
                        }}
                      >
                        {icon}
                      </div>
                      <div style={{ font: "600 20px/1.3 Inter Variable, sans-serif", color: "#0E1826", marginBottom: 8 }}>
                        {t(title)}
                      </div>
                      <div style={{ font: "400 15px/1.6 Inter Variable, sans-serif", color: "#5F6E7E" }}>
                        {t(desc)}
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
                  <h2 style={{ font: "600 32px/1.25 'Space Grotesk Variable', 'Inter Variable', sans-serif", color: "#0E1826", margin: "0 0 16px" }}>
                    {t("faq.title")}
                  </h2>
                  <p style={{ font: "400 16px/1.6 Inter Variable, sans-serif", color: "#5F6E7E", margin: "0 0 28px" }}>
                    {t("faq.noAnswer")}
                  </p>
                  <a
                    href={`mailto:${CONTACTS.supportEmail}`}
                    style={{
                      display: "inline-block",
                      border: "1.5px solid #E2E8EE",
                      background: "#ffffff",
                      color: "#0E1826",
                      borderRadius: 10,
                      padding: "12px 24px",
                      font: "600 15px/1 Inter Variable, sans-serif",
                      textDecoration: "none",
                      transition: "background 0.15s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#F9FAFB")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "#ffffff")}
                  >
                    {t("faq.writeSupport")}
                  </a>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                  {FAQ_ITEMS.map((item, i) => {
                    const isOpen = openFaq === i;
                    return (
                      <div
                        key={i}
                        style={{ borderBottom: "1px solid #E2E8EE" }}
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
                            color: "#0E1826",
                            textAlign: "left",
                            gap: 16,
                            fontFamily: "inherit",
                          }}
                        >
                          {t(item.q)}
                          {isOpen
                            ? <ChevronUp size={18} color="#0B2545" style={{ flexShrink: 0 }} />
                            : <ChevronDown size={18} color="#9CA3AF" style={{ flexShrink: 0 }} />
                          }
                        </button>
                        {isOpen && (
                          <div
                            style={{
                              padding: "0 0 20px",
                              font: "400 15px/1.6 Inter Variable, sans-serif",
                              color: "#5F6E7E",
                            }}
                          >
                            {t(item.a)}
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
                border: "1px solid #E2E8EE",
                background: "#ffffff",
                cursor: "pointer",
                fontSize: 18,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#5F6E7E",
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
                  background: "#F1F5F9",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  font: "700 24px/1 'Space Grotesk Variable', 'Inter Variable', sans-serif",
                  color: "#0B2545",
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
                <div style={{ font: "700 18px/1 Inter Variable, sans-serif", color: "#0E1826" }}>
                  {selectedRate.carrier_name}
                </div>
                <span style={{ background: "#D1FAE5", color: "#065F46", padding: "3px 10px", borderRadius: 999, font: "600 12px/1 Inter Variable, sans-serif" }}>
                  {t("panel.active")}
                </span>
              </div>
            </div>

            <hr style={{ border: "none", borderTop: "1px solid #E2E8EE", margin: "0 0 20px" }} />

            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 20 }}>
              <DetailRow label={t("panel.tariff")} value={selectedRate.tariff_name} />
              <DetailRow label={t("panel.eta")} value={t("panel.etaValue", { min: selectedRate.eta_days_min, max: selectedRate.eta_days_max })} />
              {/* Доп. услуги (страхование, хрупкий груз, звонок перед доставкой) - все
                  три интегрированных перевозчика их поддерживают, конкретный набор и
                  цена уточняются на шаге оформления. Раньше здесь был хардкод
                  "Страховка: Нет" и "Ограничения: 30 кг · 150×150×150 см", что не
                  соответствовало реальности ни одного из перевозчиков. */}
              <DetailRow label={t("panel.extras")} value={t("panel.extrasValue")} muted />
            </div>

            <hr style={{ border: "none", borderTop: "1px solid #E2E8EE", margin: "0 0 20px" }} />

            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 24 }}>
              <DetailRow label={t("panel.route")} value={`${cityLabel(shown.fromCity, locale)} → ${cityLabel(shown.toCity, locale)}`} />
              <DetailRow label={t("panel.cargo")} value={t("panel.cargoValue", { weight: shown.weightKg, qty: shown.quantity, type: shown.shipmentType === "parcel" ? t("form.parcel") : t("form.document") })} />
              <DetailRow label={t("panel.chargeable")} value={`${chargeable.toFixed(2)} ${t("units.kg")}`} />
            </div>

            <div style={{ textAlign: "center", marginBottom: 24 }}>
              <div style={{ font: "700 32px/1 'Space Grotesk Variable', 'Inter Variable', sans-serif", color: "#0E1826" }}>
                {formatPrice(selectedRate.price, selectedRate.currency)}
              </div>
              <div style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#9CA3AF", marginTop: 4 }}>
                {t("panel.vatTenge")}
              </div>
            </div>

            <button
              onClick={handleProceed}
              disabled={isSelectingRate}
              style={{
                width: "100%",
                height: 52,
                background: isSelectingRate ? "#94A6C0" : "#0B2545",
                color: "#ffffff",
                borderRadius: 10,
                font: "600 16px/1 Inter Variable, sans-serif",
                border: "none",
                cursor: isSelectingRate ? "not-allowed" : "pointer",
                fontFamily: "inherit",
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => {
                if (!isSelectingRate) e.currentTarget.style.background = "#0E2E5C";
              }}
              onMouseLeave={(e) => {
                if (!isSelectingRate) e.currentTarget.style.background = "#0B2545";
              }}
            >
              {isSelectingRate ? t("panel.processing") : t("panel.proceed")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
