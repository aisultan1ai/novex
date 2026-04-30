"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import CitySelect from "@/components/ui/CitySelect";
import { ApiError, calculateShippingQuote } from "@/lib/api/shipping";
import { selectShippingQuote } from "@/lib/api/shipping";
import type { RateQuoteItem, ShipmentType, ShippingQuoteResponse } from "@/types/quote";

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
  fromCity: "Алматы",
  toCity: "Астана",
  shipmentType: "parcel",
  weightKg: "2.5",
  quantity: "1",
  widthCm: "20",
  heightCm: "15",
  depthCm: "10",
};

const BADGE_LABELS: Record<string, string> = {
  fastest: "Быстрее всего",
  recommended: "Рекомендуем",
  best_value: "Лучшая цена",
};

const BADGE_STYLES: Record<string, React.CSSProperties> = {
  fastest: { background: "#fff7ed", color: "#c2410c" },
  recommended: { background: "#eff6ff", color: "#1d4ed8" },
  best_value: { background: "#fefce8", color: "#854d0e" },
};

function getBadgeStyle(badge: string | null): React.CSSProperties {
  if (!badge) return {};
  return BADGE_STYLES[badge] ?? { background: "#f1f5f9", color: "#475569" };
}

function formatPrice(price: number, currency: string): string {
  return `${new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(price)} ${currency}`;
}

function calcChargeable(weightKg: number, widthCm: number, heightCm: number, depthCm: number, qty: number): number {
  const vol = (widthCm * heightCm * depthCm) / 5000;
  return Math.max(weightKg, vol) * qty;
}

function SkeletonCard() {
  return (
    <div
      style={{
        height: 90,
        borderRadius: 16,
        background: "#e5e7eb",
        animation: "pulse 1.5s ease infinite",
      }}
    />
  );
}

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading, currentUser } = useAuth();

  const [form, setForm] = useState<FormState>(initialForm);
  const [results, setResults] = useState<ShippingQuoteResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRate, setSelectedRate] = useState<RateQuoteItem | null>(null);
  const [isSelectingRate, setIsSelectingRate] = useState(false);

  const resultsRef = useRef<HTMLDivElement>(null);

  function setField<K extends keyof FormState>(key: K, val: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: val }));
  }

  useEffect(() => {
    if (results) {
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    }
  }, [results]);

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
    setIsLoading(true);
    setResults(null);
    setSelectedRate(null);
    try {
      const res = await calculateShippingQuote({
        from_country: "KZ",
        from_city: form.fromCity.trim(),
        to_country: "KZ",
        to_city: form.toCity.trim(),
        shipment_type: form.shipmentType,
        weight_kg: Number(form.weightKg),
        quantity: Number(form.quantity),
        width_cm: Number(form.widthCm),
        height_cm: Number(form.heightCm),
        depth_cm: Number(form.depthCm),
      });
      setResults(res);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail : "Не удалось рассчитать тарифы.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSelectRate(rate: RateQuoteItem) {
    setSelectedRate(rate);
    if (!results || rate.id === null) return;
    try {
      setIsSelectingRate(true);
      await selectShippingQuote(results.quote_session_id, { rate_quote_id: rate.id as number });
    } catch {
      // selection is best-effort; navigation carries session id
    } finally {
      setIsSelectingRate(false);
    }
  }

  function handleProceed() {
    if (!selectedRate || !results) return;
    router.push(`/quote/shipment?quoteSessionId=${results.quote_session_id}`);
  }

  const hasResults = results !== null;
  const minPrice = results ? Math.min(...results.quotes.map((q) => q.price)) : null;
  const chargeable = calcChargeable(
    Number(form.weightKg),
    Number(form.widthCm),
    Number(form.heightCm),
    Number(form.depthCm),
    Number(form.quantity),
  );

  const inp: React.CSSProperties = {
    border: "1px solid #e5e7eb",
    borderRadius: 10,
    padding: "10px 12px",
    background: "#f8fafc",
    fontSize: 15,
    width: "100%",
    boxSizing: "border-box",
    textAlign: "center",
    outline: "none",
    fontFamily: "inherit",
    color: "#0f172a",
    transition: "border-color 0.15s, background 0.15s",
  };

  const lbl: React.CSSProperties = {
    display: "block",
    fontSize: 10,
    fontWeight: 700,
    color: "#94a3b8",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    marginBottom: 6,
  };

  return (
    <div style={{ minHeight: "100vh", background: "#f1f5f9" }}>

      {/* HEADER */}
      <header
        style={{
          height: 60,
          background: "#ffffff",
          borderBottom: "1px solid #e5e7eb",
          padding: "0 40px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          position: "sticky",
          top: 0,
          zIndex: 50,
        }}
      >
        <span style={{ fontSize: 20, fontWeight: 800, color: "#0f172a" }}>Novex</span>

        {!authLoading && (
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {isAuthenticated ? (
              <Link
                href="/dashboard"
                style={{
                  padding: "8px 20px",
                  borderRadius: 10,
                  background: "#0f172a",
                  color: "#ffffff",
                  fontSize: 14,
                  fontWeight: 600,
                  textDecoration: "none",
                }}
              >
                {currentUser?.full_name ? currentUser.full_name.split(" ")[0] : "Кабинет"} →
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  style={{
                    padding: "8px 20px",
                    borderRadius: 10,
                    border: "1px solid #e5e7eb",
                    background: "#ffffff",
                    color: "#0f172a",
                    fontSize: 14,
                    fontWeight: 600,
                    textDecoration: "none",
                  }}
                >
                  Войти
                </Link>
                <Link
                  href="/register"
                  style={{
                    padding: "8px 20px",
                    borderRadius: 10,
                    background: "#0f172a",
                    color: "#ffffff",
                    fontSize: 14,
                    fontWeight: 600,
                    textDecoration: "none",
                  }}
                >
                  Регистрация
                </Link>
              </>
            )}
          </div>
        )}
      </header>

      {/* MAIN */}
      <main style={{ background: "#f1f5f9", minHeight: "calc(100vh - 60px)", paddingBottom: 80 }}>

        {/* HERO (only before search) */}
        {!hasResults && (
          <div style={{ textAlign: "center", paddingTop: 80, paddingBottom: 48 }}>
            <h1 style={{ fontSize: 48, fontWeight: 800, color: "#0f172a", lineHeight: 1.15, margin: "0 0 16px" }}>
              Доставка по Казахстану
            </h1>
            <p style={{ fontSize: 18, color: "#64748b", maxWidth: 480, margin: "0 auto 40px", lineHeight: 1.6 }}>
              Сравните тарифы курьерских служб и оформите отправление онлайн за несколько минут
            </p>
          </div>
        )}

        {/* BREADCRUMB (after search) */}
        {hasResults && (
          <div style={{ maxWidth: 900, margin: "0 auto", padding: "24px 20px 0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <button
                onClick={() => { setResults(null); setSelectedRate(null); }}
                style={{
                  background: "none",
                  border: "none",
                  color: "#64748b",
                  fontSize: 14,
                  fontWeight: 500,
                  cursor: "pointer",
                  padding: 0,
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  fontFamily: "inherit",
                }}
              >
                ← Новый расчёт
              </button>
              <span style={{ color: "#94a3b8", fontSize: 13 }}>
                {form.fromCity} → {form.toCity} · {form.weightKg}кг · {form.shipmentType === "parcel" ? "Посылка" : "Документ"}
              </span>
            </div>
          </div>
        )}

        {/* FORM CARD */}
        <div
          style={{
            maxWidth: hasResults ? 900 : 720,
            margin: "0 auto",
            padding: hasResults ? "16px 20px 0" : "0 20px",
            transition: "max-width 0.3s ease",
          }}
        >
          <div
            style={{
              background: "#ffffff",
              borderRadius: 16,
              boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)",
              padding: "32px",
            }}
          >
            <div style={{ marginBottom: 24 }}>
              <h2 style={{ margin: "0 0 4px", fontSize: 20, fontWeight: 700, color: "#0f172a" }}>
                Рассчитать стоимость
              </h2>
              <p style={{ margin: 0, fontSize: 14, color: "#64748b" }}>
                Укажите маршрут и параметры отправления
              </p>
            </div>

            <form onSubmit={handleSubmit}>
              {/* Route */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 40px 1fr",
                  gap: 12,
                  alignItems: "end",
                  marginBottom: 20,
                }}
              >
                <div>
                  <label style={lbl}>Откуда</label>
                  <CitySelect
                    value={form.fromCity}
                    onChange={(v) => setField("fromCity", v)}
                    placeholder="Город отправки"
                  />
                </div>
                <div style={{ display: "flex", justifyContent: "center", paddingBottom: 12 }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="5" y1="12" x2="19" y2="12" />
                    <polyline points="12 5 19 12 12 19" />
                  </svg>
                </div>
                <div>
                  <label style={lbl}>Куда</label>
                  <CitySelect
                    value={form.toCity}
                    onChange={(v) => setField("toCity", v)}
                    placeholder="Город доставки"
                  />
                </div>
              </div>

              {/* Shipment type */}
              <div style={{ marginBottom: 20 }}>
                <label style={lbl}>Что отправляете</label>
                <div style={{ display: "flex", gap: 8 }}>
                  {(["parcel", "document"] as ShipmentType[]).map((t) => {
                    const active = form.shipmentType === t;
                    return (
                      <button
                        key={t}
                        type="button"
                        onClick={() => setField("shipmentType", t)}
                        style={{
                          padding: "8px 20px",
                          borderRadius: 8,
                          border: active ? "none" : "1px solid #e5e7eb",
                          background: active ? "#0f172a" : "transparent",
                          color: active ? "#ffffff" : "#64748b",
                          fontSize: 14,
                          fontWeight: 600,
                          cursor: "pointer",
                          fontFamily: "inherit",
                        }}
                      >
                        {t === "parcel" ? "Посылка" : "Документ"}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Parameters */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 24 }}>
                {(
                  [
                    { key: "weightKg", label: "Вес, кг", placeholder: "2.5" },
                    { key: "quantity", label: "Кол-во", placeholder: "1" },
                    { key: "widthCm", label: "Ширина, см", placeholder: "20" },
                    { key: "heightCm", label: "Высота, см", placeholder: "15" },
                    { key: "depthCm", label: "Глубина, см", placeholder: "10" },
                  ] as { key: keyof FormState; label: string; placeholder: string }[]
                ).map(({ key, label, placeholder }) => (
                  <div key={key}>
                    <label style={lbl}>{label}</label>
                    <input
                      style={inp}
                      value={form[key]}
                      onChange={(e) => setField(key, e.target.value)}
                      placeholder={placeholder}
                      inputMode="decimal"
                      required
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = "#0f172a";
                        e.currentTarget.style.background = "#ffffff";
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = "#e5e7eb";
                        e.currentTarget.style.background = "#f8fafc";
                      }}
                    />
                  </div>
                ))}
              </div>

              <button
                type="submit"
                disabled={isLoading}
                style={{
                  width: "100%",
                  height: 52,
                  background: isLoading ? "#1e293b" : "#0f172a",
                  color: "#ffffff",
                  borderRadius: 12,
                  fontSize: 16,
                  fontWeight: 600,
                  border: "none",
                  cursor: isLoading ? "not-allowed" : "pointer",
                  opacity: isLoading ? 0.7 : 1,
                  fontFamily: "inherit",
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) => {
                  if (!isLoading) e.currentTarget.style.background = "#1e293b";
                }}
                onMouseLeave={(e) => {
                  if (!isLoading) e.currentTarget.style.background = "#0f172a";
                }}
              >
                {isLoading ? "Рассчитываем..." : "Рассчитать тарифы →"}
              </button>

              {error && (
                <div style={{ marginTop: 12, padding: "12px 14px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 13 }}>
                  {error}
                </div>
              )}
            </form>
          </div>
        </div>

        {/* FEATURE PILLS (before search) */}
        {!hasResults && (
          <div style={{ textAlign: "center", marginTop: 24, display: "flex", justifyContent: "center", gap: 32, flexWrap: "wrap" }}>
            {["Мгновенный расчёт", "Лучшие тарифы", "Онлайн-оформление"].map((f) => (
              <span key={f} style={{ fontSize: 14, color: "#64748b", display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ color: "#16a34a", fontWeight: 700 }}>✓</span> {f}
              </span>
            ))}
          </div>
        )}

        {/* RESULTS SECTION */}
        {hasResults && (
          <div ref={resultsRef} style={{ maxWidth: 900, margin: "0 auto", padding: "0 20px" }}>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: "#0f172a", margin: "32px 0 20px" }}>
              Результаты поиска
            </h2>

            {isLoading ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {results.quotes.map((rate) => {
                  const isBest = rate.price === minPrice;
                  return (
                    <div
                      key={rate.id ?? rate.carrier_code + rate.tariff_name}
                      className="result-card"
                      onClick={() => handleSelectRate(rate)}
                      style={{
                        background: "#ffffff",
                        borderRadius: 16,
                        border: `1px solid ${selectedRate === rate ? "#0f172a" : "#e5e7eb"}`,
                        padding: "20px 24px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 16,
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.boxShadow = "0 4px 20px rgba(0,0,0,0.09)";
                        e.currentTarget.style.borderColor = selectedRate === rate ? "#0f172a" : "#d1d5db";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.boxShadow = "none";
                        e.currentTarget.style.borderColor = selectedRate === rate ? "#0f172a" : "#e5e7eb";
                      }}
                    >
                      {/* Left */}
                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
                          <div
                            style={{
                              width: 48,
                              height: 48,
                              borderRadius: 10,
                              background: "#f1f5f9",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: 20,
                              fontWeight: 800,
                              color: "#0f172a",
                              flexShrink: 0,
                            }}
                          >
                            {rate.carrier_name[0]}
                          </div>
                          <div>
                            <span style={{ fontSize: 16, fontWeight: 700, color: "#0f172a", marginRight: 8 }}>
                              {rate.carrier_name}
                            </span>
                            <TariffBadge name={rate.tariff_name} />
                            {rate.badge && (
                              <span
                                style={{
                                  ...getBadgeStyle(rate.badge),
                                  padding: "3px 10px",
                                  borderRadius: 999,
                                  fontSize: 12,
                                  fontWeight: 600,
                                  marginLeft: 6,
                                }}
                              >
                                {BADGE_LABELS[rate.badge] ?? rate.badge}
                              </span>
                            )}
                            {isBest && !rate.badge && (
                              <span
                                style={{
                                  background: "#fefce8",
                                  color: "#854d0e",
                                  padding: "3px 10px",
                                  borderRadius: 999,
                                  fontSize: 12,
                                  fontWeight: 600,
                                  marginLeft: 6,
                                }}
                              >
                                Лучшая цена
                              </span>
                            )}
                          </div>
                        </div>
                        <div style={{ fontSize: 13, color: "#64748b", display: "flex", gap: 20, alignItems: "center", flexWrap: "wrap" }}>
                          <span>📅 Срок: {rate.eta_days_min}–{rate.eta_days_max} дн.</span>
                          <span>🕐 Сбор: по будням</span>
                          <span>🛡 Страховка: нет</span>
                        </div>
                      </div>

                      {/* Right */}
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8, flexShrink: 0 }}>
                        <div>
                          <div style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", textAlign: "right" }}>
                            {formatPrice(rate.price, rate.currency)}
                          </div>
                          <div style={{ fontSize: 12, color: "#94a3b8", textAlign: "right" }}>с НДС</div>
                        </div>
                        <button
                          onClick={(e) => { e.stopPropagation(); void handleSelectRate(rate); }}
                          style={{
                            border: "1px solid #e5e7eb",
                            background: selectedRate === rate ? "#0f172a" : "#ffffff",
                            color: selectedRate === rate ? "#ffffff" : "#0f172a",
                            borderColor: selectedRate === rate ? "#0f172a" : "#e5e7eb",
                            borderRadius: 10,
                            padding: "8px 20px",
                            fontWeight: 600,
                            fontSize: 14,
                            cursor: "pointer",
                            fontFamily: "inherit",
                            transition: "all 0.15s",
                          }}
                          onMouseEnter={(e) => {
                            if (selectedRate !== rate) {
                              e.currentTarget.style.background = "#0f172a";
                              e.currentTarget.style.color = "#ffffff";
                              e.currentTarget.style.borderColor = "#0f172a";
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (selectedRate !== rate) {
                              e.currentTarget.style.background = "#ffffff";
                              e.currentTarget.style.color = "#0f172a";
                              e.currentTarget.style.borderColor = "#e5e7eb";
                            }
                          }}
                        >
                          {selectedRate === rate ? "Выбрано ✓" : "Выбрать →"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </main>

      {/* SIDE PANEL OVERLAY */}
      {selectedRate && (
        <>
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.3)",
              zIndex: 199,
            }}
            onClick={() => setSelectedRate(null)}
          />
          <div
            style={{
              position: "fixed",
              right: 0,
              top: 0,
              bottom: 0,
              width: 420,
              background: "#ffffff",
              boxShadow: "-4px 0 32px rgba(0,0,0,0.12)",
              overflowY: "auto",
              padding: 32,
              zIndex: 200,
              animation: "slideInRight 0.2s ease",
            }}
          >
            {/* Close */}
            <button
              onClick={() => setSelectedRate(null)}
              style={{
                position: "absolute",
                top: 20,
                right: 20,
                width: 36,
                height: 36,
                borderRadius: "50%",
                border: "1px solid #e5e7eb",
                background: "#ffffff",
                cursor: "pointer",
                fontSize: 18,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#64748b",
                fontFamily: "inherit",
              }}
            >
              ×
            </button>

            {/* Logo + name */}
            <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 20 }}>
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 12,
                  background: "#f1f5f9",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 24,
                  fontWeight: 800,
                  color: "#0f172a",
                }}
              >
                {selectedRate.carrier_name[0]}
              </div>
              <div>
                <div style={{ fontSize: 18, fontWeight: 700, color: "#0f172a" }}>
                  {selectedRate.carrier_name}
                </div>
                <span style={{ background: "#f0fdf4", color: "#16a34a", padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600 }}>
                  Активен
                </span>
              </div>
            </div>

            <hr style={{ border: "none", borderTop: "1px solid #f1f5f9", margin: "0 0 20px" }} />

            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 20 }}>
              <DetailRow label="Тариф" value={selectedRate.tariff_name} />
              <DetailRow label="Срок доставки" value={`${selectedRate.eta_days_min}–${selectedRate.eta_days_max} рабочих дней`} />
              <DetailRow label="Ограничения" value="Макс. 30 кг · 150×150×150 см" muted />
              <DetailRow label="Страховка" value="Нет" />
            </div>

            <hr style={{ border: "none", borderTop: "1px solid #f1f5f9", margin: "0 0 20px" }} />

            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 24 }}>
              <DetailRow label="Маршрут" value={`${form.fromCity} → ${form.toCity}`} />
              <DetailRow label="Груз" value={`${form.weightKg} кг × ${form.quantity} шт · ${form.shipmentType === "parcel" ? "Посылка" : "Документ"}`} />
              <DetailRow label="Расчётный вес" value={`${chargeable.toFixed(2)} кг`} />
            </div>

            <div style={{ textAlign: "center", marginBottom: 24 }}>
              <div style={{ fontSize: 32, fontWeight: 800, color: "#0f172a" }}>
                {formatPrice(selectedRate.price, selectedRate.currency)}
              </div>
              <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 4 }}>с НДС · тенге</div>
            </div>

            <button
              onClick={handleProceed}
              disabled={isSelectingRate}
              style={{
                width: "100%",
                height: 52,
                background: "#0f172a",
                color: "#ffffff",
                borderRadius: 12,
                fontSize: 16,
                fontWeight: 600,
                border: "none",
                cursor: isSelectingRate ? "not-allowed" : "pointer",
                opacity: isSelectingRate ? 0.7 : 1,
                fontFamily: "inherit",
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

function TariffBadge({ name }: { name: string }) {
  const lower = name.toLowerCase();
  let style: React.CSSProperties;
  if (lower.includes("экспресс") || lower.includes("express")) {
    style = { background: "#fff7ed", color: "#c2410c" };
  } else if (lower.includes("эконом") || lower.includes("econom")) {
    style = { background: "#f0fdf4", color: "#15803d" };
  } else {
    style = { background: "#f1f5f9", color: "#475569" };
  }
  return (
    <span style={{ ...style, padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600 }}>
      {name}
    </span>
  );
}

function DetailRow({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span style={{ fontSize: 13, color: "#94a3b8" }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 600, color: muted ? "#94a3b8" : "#0f172a" }}>{value}</span>
    </div>
  );
}
