"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { flushSync } from "react-dom";
import { useRouter, useSearchParams } from "next/navigation";

import Navbar from "@/components/layout/Navbar";
import { useIsMobile } from "@/hooks/use-is-mobile";
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
  const isMobile = useIsMobile();

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

      <main style={{
        maxWidth: 900, margin: "0 auto",
        padding: isMobile ? "24px 16px 40px" : "40px 20px 80px",
      }}>
        {/* Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: isMobile ? "flex-start" : "center",
            flexWrap: "wrap",
            gap: isMobile ? 12 : 16,
            marginBottom: isMobile ? 20 : 32,
          }}
        >
          <div style={{ minWidth: 0, flex: 1 }}>
            <div
              style={{
                font: `500 ${isMobile ? 11 : 13}px/1 Inter Variable, sans-serif`,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "#0B2545",
                marginBottom: 8,
              }}
            >
              Шаг 2 из 4 · Выбор тарифа
            </div>
            <h1
              style={{
                font: `700 ${isMobile ? 22 : 28}px/1.2 'Space Grotesk Variable', 'Inter Variable', sans-serif`,
                letterSpacing: "-0.02em",
                color: "#0E1826",
                margin: 0,
              }}
            >
              Доступные тарифы
            </h1>
          </div>
          <button
            onClick={() => router.push("/")}
            style={{
              border: "1.5px solid #E2E8EE",
              background: "#ffffff",
              color: "#0E1826",
              borderRadius: 10,
              padding: isMobile ? "8px 14px" : "10px 18px",
              font: `600 ${isMobile ? 13 : 14}px/1 Inter Variable, sans-serif`,
              cursor: "pointer",
              fontFamily: "inherit",
              transition: "background 0.15s",
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#F9FAFB")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "#ffffff")}
          >
            ← Назад
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
                border: "1px solid #E2E8EE",
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
              <span style={{ font: "500 14px/1 Inter Variable, sans-serif", color: "#5F6E7E" }}>
                Найдено тарифов:{" "}
                <b style={{ color: "#0E1826" }}>{data.quotes.length}</b>
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
                  background: "#F1F5F9",
                  border: "1px solid #CFDCEA",
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
                      background: isSelected ? "#F1F5F9" : "#ffffff",
                      borderRadius: 16,
                      border: `1.5px solid ${isSelected ? "#0B2545" : isBest ? "#0B2545" : "#E2E8EE"}`,
                      padding: isMobile ? "16px" : "20px 24px",
                      display: "flex",
                      flexDirection: isMobile ? "column" : "row",
                      alignItems: isMobile ? "stretch" : "center",
                      justifyContent: "space-between",
                      gap: isMobile ? 14 : 16,
                      cursor: isSelected ? "default" : "pointer",
                      boxShadow: isBest || isSelected
                        ? "0 4px 16px rgba(11,37,69,0.10)"
                        : "0 1px 3px rgba(0,0,0,0.06)",
                      transition: "all 0.15s ease",
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected && !isMobile) {
                        e.currentTarget.style.boxShadow = "0 4px 16px rgba(11,37,69,0.10)";
                        e.currentTarget.style.transform = "translateY(-2px)";
                        e.currentTarget.style.borderColor = "#0B2545";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected && !isMobile) {
                        e.currentTarget.style.boxShadow = isBest
                          ? "0 4px 16px rgba(11,37,69,0.10)"
                          : "0 1px 3px rgba(0,0,0,0.06)";
                        e.currentTarget.style.transform = "translateY(0)";
                        e.currentTarget.style.borderColor = isBest ? "#0B2545" : "#E2E8EE";
                      }
                    }}
                  >
                    {/* Left: carrier info */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        display: "flex",
                        alignItems: "center",
                        gap: isMobile ? 10 : 12,
                        marginBottom: 8,
                      }}>
                        <div
                          style={{
                            width: isMobile ? 40 : 48,
                            height: isMobile ? 40 : 48,
                            borderRadius: 10,
                            background: "#F1F5F9",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            font: `700 ${isMobile ? 16 : 20}px/1 Inter Variable, sans-serif`,
                            color: "#0B2545",
                            flexShrink: 0,
                          }}
                        >
                          {rate.carrier_name[0]}
                        </div>
                        <div style={{ minWidth: 0, flex: 1, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6 }}>
                          <span style={{
                            font: `600 ${isMobile ? 15 : 16}px/1.2 Inter Variable, sans-serif`,
                            color: "#0E1826",
                          }}>
                            {rate.carrier_name}
                          </span>
                          <TariffBadge name={rate.tariff_name} />
                          {badgeLabel && (
                            <span
                              style={{
                                background: "#F1F5F9",
                                color: "#0E2E5C",
                                padding: "3px 10px",
                                borderRadius: 999,
                                font: "600 11px/1 Inter Variable, sans-serif",
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
                                font: "600 11px/1 Inter Variable, sans-serif",
                              }}
                            >
                              Выбран ✓
                            </span>
                          )}
                        </div>
                      </div>
                      <div style={{
                        font: "400 13px/1.3 Inter Variable, sans-serif",
                        color: "#5F6E7E",
                        display: "flex",
                        gap: 16,
                        flexWrap: "wrap",
                        paddingLeft: isMobile ? 50 : 60,
                      }}>
                        <span>Срок: {rate.eta_days_min}-{rate.eta_days_max} дн.</span>
                        {/эконом|econom/i.test(rate.tariff_name) && (
                          <span style={{ color: "#F59E0B" }}>мин. 10 кг</span>
                        )}
                      </div>
                    </div>

                    {/* Right: price + button */}
                    <div style={{
                      display: "flex",
                      flexDirection: isMobile ? "row" : "column",
                      alignItems: isMobile ? "center" : "flex-end",
                      justifyContent: isMobile ? "space-between" : "flex-start",
                      gap: isMobile ? 12 : 8,
                      flexShrink: 0,
                      paddingTop: isMobile ? 10 : 0,
                      borderTop: isMobile ? "1px solid #f1f5f9" : "none",
                    }}>
                      <div style={{ minWidth: 0 }}>
                        <div style={{
                          font: `700 ${isMobile ? 22 : 24}px/1 'Space Grotesk Variable', 'Inter Variable', sans-serif`,
                          color: "#0E1826",
                          textAlign: isMobile ? "left" : "right",
                          whiteSpace: "nowrap",
                        }}>
                          {formatPrice(rate.price, rate.currency)}
                        </div>
                        <div style={{
                          font: "400 12px/1 Inter Variable, sans-serif",
                          color: "#9CA3AF",
                          textAlign: isMobile ? "left" : "right",
                          marginTop: 4,
                        }}>
                          с НДС
                        </div>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); void handleSelectQuote(e, rate); }}
                        disabled={rate.id == null || selectingId === rate.id || isSelected}
                        style={{
                          border: isSelected ? "none" : "1.5px solid #E2E8EE",
                          background: isSelected ? "#0B2545" : "#ffffff",
                          color: isSelected ? "#ffffff" : "#0E1826",
                          borderRadius: 10,
                          padding: isMobile ? "10px 20px" : "8px 18px",
                          font: "600 14px/1 Inter Variable, sans-serif",
                          cursor: isSelected || selectingId === rate.id ? "not-allowed" : "pointer",
                          fontFamily: "inherit",
                          opacity: selectingId === rate.id ? 0.6 : 1,
                          transition: "all 0.15s",
                          whiteSpace: "nowrap",
                          flexShrink: 0,
                        }}
                        onMouseEnter={(e) => {
                          if (!isSelected && selectingId !== rate.id && !isMobile) {
                            e.currentTarget.style.background = "#0B2545";
                            e.currentTarget.style.color = "#ffffff";
                            e.currentTarget.style.borderColor = "#0B2545";
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (!isSelected && selectingId !== rate.id && !isMobile) {
                            e.currentTarget.style.background = "#ffffff";
                            e.currentTarget.style.color = "#0E1826";
                            e.currentTarget.style.borderColor = "#E2E8EE";
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

            {/* Disclaimer */}
            <p style={{ font: "400 12px/1.5 Inter Variable, sans-serif", color: "#9CA3AF", margin: "4px 0 0" }}>
              * Расчёт носит предварительный характер и может измениться после контрольного измерения отправления.
            </p>

            {/* Continue button */}
            <div style={{
              display: "flex",
              justifyContent: isMobile ? "stretch" : "flex-end",
              marginTop: 20,
            }}>
              <button
                onClick={handleContinue}
                disabled={!selectedQuote}
                style={{
                  background: selectedQuote ? "#0B2545" : "#E2E8EE",
                  color: selectedQuote ? "#ffffff" : "#9CA3AF",
                  border: "none",
                  borderRadius: 10,
                  padding: isMobile ? "14px 24px" : "14px 32px",
                  font: "600 15px/1 Inter Variable, sans-serif",
                  cursor: selectedQuote ? "pointer" : "not-allowed",
                  fontFamily: "inherit",
                  transition: "background 0.15s",
                  width: isMobile ? "100%" : "auto",
                }}
                onMouseEnter={(e) => {
                  if (selectedQuote) e.currentTarget.style.background = "#0E2E5C";
                }}
                onMouseLeave={(e) => {
                  if (selectedQuote) e.currentTarget.style.background = "#0B2545";
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
