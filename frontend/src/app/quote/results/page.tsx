"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { flushSync } from "react-dom";
import { useRouter, useSearchParams } from "next/navigation";

import Navbar from "@/components/layout/Navbar";
import { ApiError, getShippingQuote, selectShippingQuote } from "@/lib/api/shipping";
import type { RateQuoteItem, ShippingQuoteResponse } from "@/types/quote";

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function formatPrice(price: number, currency: string): string {
  return `${new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(price)} ${currency}`;
}

const BADGE_LABELS: Record<string, string> = {
  fastest: "Быстрее всего",
  recommended: "Рекомендуем",
  best_value: "Лучшая цена",
};

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
    <span style={{ background: bg, color, padding: "3px 10px", borderRadius: 999, font: "600 12px/1 Inter Variable, sans-serif" }}>
      {name}
    </span>
  );
}

function SkeletonCard() {
  return <div className="skeleton" style={{ height: 100, borderRadius: 16 }} />;
}

/* ─── Page inner ─────────────────────────────────────────────────────────── */

function QuoteResultsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const quoteSessionId = useMemo(() => {
    const raw = searchParams.get("quoteSessionId");
    if (!raw) return null;
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);

  const token = searchParams.get("token");

  const [data, setData] = useState<ShippingQuoteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectingId, setSelectingId] = useState<number | null>(null);

  const selectedQuote = useMemo(
    () => data?.quotes.find((q) => q.is_selected) ?? null,
    [data],
  );
  const minPrice = data ? Math.min(...data.quotes.map((q) => q.price)) : null;

  useEffect(() => {
    let isMounted = true;
    async function load() {
      if (!quoteSessionId) {
        setError("Не найден quoteSessionId в URL.");
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      setError(null);
      try {
        const res = await getShippingQuote(quoteSessionId, token);
        if (isMounted) setData(res);
      } catch (err) {
        if (!isMounted) return;
        setError(err instanceof ApiError ? err.detail : err instanceof Error ? err.message : "Не удалось загрузить результаты.");
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }
    void load();
    return () => { isMounted = false; };
  }, [quoteSessionId, token]);

  async function handleSelectQuote(e: React.MouseEvent<HTMLButtonElement>, rate: RateQuoteItem) {
    if (!quoteSessionId || rate.id == null) return;
    e.currentTarget.blur();
    const savedScrollY = window.scrollY;
    setSelectingId(rate.id);
    setError(null);

    let nextData: typeof data | null = null;
    let nextError: string | null = null;
    try {
      nextData = await selectShippingQuote(quoteSessionId, { rate_quote_id: rate.id }, token);
    } catch (err) {
      nextError = err instanceof ApiError ? err.detail : err instanceof Error ? err.message : "Не удалось выбрать тариф.";
    }

    flushSync(() => {
      setSelectingId(null);
      if (nextData) setData(nextData);
      if (nextError) setError(nextError);
    });

    window.scrollTo({ top: savedScrollY, behavior: "instant" });
  }

  function handleContinue() {
    if (!quoteSessionId || !selectedQuote) return;
    router.push(`/quote/shipment?quoteSessionId=${quoteSessionId}${token ? `&token=${token}` : ""}`);
  }

  return (
    <div style={{ minHeight: "100vh", background: "#FAFAFA" }}>
      <Navbar />

      <main style={{ maxWidth: 900, margin: "0 auto", padding: "40px 20px 80px" }}>
        {/* Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 16,
            marginBottom: 32,
          }}
        >
          <div>
            <div
              style={{
                font: "500 13px/1 Inter Variable, sans-serif",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "#2563EB",
                marginBottom: 10,
              }}
            >
              Шаг 2 из 4 - Выбор тарифа
            </div>
            <h1
              style={{
                font: "700 28px/1.2 Inter Variable, sans-serif",
                letterSpacing: "-0.02em",
                color: "#111827",
                margin: 0,
              }}
            >
              Доступные тарифы
            </h1>
          </div>
          <button
            onClick={() => router.push("/")}
            style={{
              border: "1.5px solid #E5E7EB",
              background: "#ffffff",
              color: "#111827",
              borderRadius: 10,
              padding: "10px 18px",
              font: "600 14px/1 Inter Variable, sans-serif",
              cursor: "pointer",
              fontFamily: "inherit",
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#F9FAFB")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "#ffffff")}
          >
            ← Назад к форме
          </button>
        </div>

        {/* Error */}
        {error && (
          <div
            style={{
              padding: "12px 16px",
              borderRadius: 10,
              background: "#FEF2F2",
              border: "1px solid #FECACA",
              color: "#B91C1C",
              font: "400 14px/1.4 Inter Variable, sans-serif",
              marginBottom: 20,
            }}
          >
            {error}
          </div>
        )}

        {/* Loading */}
        {isLoading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <SkeletonCard /><SkeletonCard /><SkeletonCard />
          </div>
        ) : !data ? null : (
          <>
            {/* Summary bar */}
            <div
              style={{
                background: "#ffffff",
                border: "1px solid #E5E7EB",
                borderRadius: 12,
                padding: "14px 20px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: 12,
                marginBottom: 20,
                boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
              }}
            >
              <span style={{ font: "500 14px/1 Inter Variable, sans-serif", color: "#6B7280" }}>
                Найдено тарифов:{" "}
                <b style={{ color: "#111827" }}>{data.quotes.length}</b>
              </span>
              {selectedQuote && (
                <span
                  style={{
                    background: "#D1FAE5",
                    color: "#065F46",
                    padding: "4px 12px",
                    borderRadius: 999,
                    font: "600 13px/1 Inter Variable, sans-serif",
                  }}
                >
                  Выбран: {selectedQuote.carrier_name} · {formatPrice(selectedQuote.price, selectedQuote.currency)}
                </span>
              )}
            </div>

            {/* Hint */}
            {!selectedQuote && (
              <div
                style={{
                  background: "#EFF6FF",
                  border: "1px solid #BFDBFE",
                  borderRadius: 10,
                  padding: "12px 16px",
                  font: "400 14px/1.4 Inter Variable, sans-serif",
                  color: "#1E3A8A",
                  marginBottom: 20,
                }}
              >
                Выберите тариф, чтобы продолжить оформление отправления.
              </div>
            )}

            {/* Tariff cards */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 28 }}>
              {data.quotes.map((rate) => {
                const isBest = rate.price === minPrice;
                const isSelected = rate.is_selected;
                const badgeLabel = rate.badge ? BADGE_LABELS[rate.badge] : isBest && !rate.badge ? "Лучшая цена" : null;

                return (
                  <div
                    key={rate.id ?? `${rate.carrier_code}-${rate.tariff_name}`}
                    className="result-card"
                    onClick={(e) => {
                      if (rate.id != null && !isSelected && selectingId !== rate.id) {
                        void handleSelectQuote(e as unknown as React.MouseEvent<HTMLButtonElement>, rate);
                      }
                    }}
                    style={{
                      background: isSelected ? "#EFF6FF" : "#ffffff",
                      borderRadius: 16,
                      border: `1.5px solid ${isSelected ? "#2563EB" : isBest ? "#2563EB" : "#E5E7EB"}`,
                      padding: "20px 24px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 16,
                      cursor: isSelected ? "default" : "pointer",
                      boxShadow: isBest || isSelected
                        ? "0 4px 16px rgba(37,99,235,0.10)"
                        : "0 1px 3px rgba(0,0,0,0.06)",
                      transition: "all 0.15s ease",
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.boxShadow = "0 4px 16px rgba(37,99,235,0.10)";
                        e.currentTarget.style.transform = "translateY(-2px)";
                        e.currentTarget.style.borderColor = "#2563EB";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.boxShadow = isBest
                          ? "0 4px 16px rgba(37,99,235,0.10)"
                          : "0 1px 3px rgba(0,0,0,0.06)";
                        e.currentTarget.style.transform = "translateY(0)";
                        e.currentTarget.style.borderColor = isBest ? "#2563EB" : "#E5E7EB";
                      }
                    }}
                  >
                    {/* Left */}
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
                          }}
                        >
                          {rate.carrier_name[0]}
                        </div>
                        <div>
                          <span style={{ font: "600 16px/1 Inter Variable, sans-serif", color: "#111827", marginRight: 8 }}>
                            {rate.carrier_name}
                          </span>
                          <TariffBadge name={rate.tariff_name} />
                          {badgeLabel && (
                            <span
                              style={{
                                background: "#EFF6FF",
                                color: "#1D4ED8",
                                padding: "3px 10px",
                                borderRadius: 999,
                                font: "600 12px/1 Inter Variable, sans-serif",
                                marginLeft: 6,
                              }}
                            >
                              {badgeLabel}
                            </span>
                          )}
                          {isSelected && (
                            <span
                              style={{
                                background: "#D1FAE5",
                                color: "#065F46",
                                padding: "3px 10px",
                                borderRadius: 999,
                                font: "600 12px/1 Inter Variable, sans-serif",
                                marginLeft: 6,
                              }}
                            >
                              Выбран ✓
                            </span>
                          )}
                        </div>
                      </div>
                      <div style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#6B7280", display: "flex", gap: 16, flexWrap: "wrap" }}>
                        <span>Срок: {rate.eta_days_min}–{rate.eta_days_max} дн.</span>
                        {/эконом|econom/i.test(rate.tariff_name) && (
                          <span style={{ color: "#F59E0B" }}>мин. 10 кг</span>
                        )}
                      </div>
                    </div>

                    {/* Right */}
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
                        onClick={(e) => { e.stopPropagation(); void handleSelectQuote(e, rate); }}
                        disabled={rate.id == null || selectingId === rate.id || isSelected}
                        style={{
                          border: isSelected ? "none" : "1.5px solid #E5E7EB",
                          background: isSelected ? "#2563EB" : "#ffffff",
                          color: isSelected ? "#ffffff" : "#111827",
                          borderRadius: 10,
                          padding: "8px 18px",
                          font: "600 14px/1 Inter Variable, sans-serif",
                          cursor: isSelected || selectingId === rate.id ? "not-allowed" : "pointer",
                          fontFamily: "inherit",
                          opacity: selectingId === rate.id ? 0.6 : 1,
                          transition: "all 0.15s",
                        }}
                        onMouseEnter={(e) => {
                          if (!isSelected && selectingId !== rate.id) {
                            e.currentTarget.style.background = "#2563EB";
                            e.currentTarget.style.color = "#ffffff";
                            e.currentTarget.style.borderColor = "#2563EB";
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (!isSelected && selectingId !== rate.id) {
                            e.currentTarget.style.background = "#ffffff";
                            e.currentTarget.style.color = "#111827";
                            e.currentTarget.style.borderColor = "#E5E7EB";
                          }
                        }}
                      >
                        {isSelected ? "Выбрано ✓" : selectingId === rate.id ? "Выбираем..." : "Выбрать"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Continue button */}
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                onClick={handleContinue}
                disabled={!selectedQuote}
                style={{
                  background: selectedQuote ? "#2563EB" : "#E5E7EB",
                  color: selectedQuote ? "#ffffff" : "#9CA3AF",
                  border: "none",
                  borderRadius: 10,
                  padding: "14px 32px",
                  font: "600 15px/1 Inter Variable, sans-serif",
                  cursor: selectedQuote ? "pointer" : "not-allowed",
                  fontFamily: "inherit",
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) => {
                  if (selectedQuote) e.currentTarget.style.background = "#1D4ED8";
                }}
                onMouseLeave={(e) => {
                  if (selectedQuote) e.currentTarget.style.background = "#2563EB";
                }}
              >
                Продолжить оформление →
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default function QuoteResultsPage() {
  return (
    <Suspense>
      <QuoteResultsPageInner />
    </Suspense>
  );
}
