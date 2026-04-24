"use client";

import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";
import { flushSync } from "react-dom";
import { useRouter, useSearchParams } from "next/navigation";

import {
  ApiError,
  getShippingQuote,
  selectShippingQuote,
} from "@/lib/api/shipping";
import type { RateQuoteItem, ShippingQuoteResponse } from "@/types/quote";

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  background: "linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%)",
  padding: "32px 20px 64px",
  color: "#0f172a",
  fontFamily:
    "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
};

const containerStyle: CSSProperties = {
  maxWidth: 1100,
  margin: "0 auto",
};

const cardStyle: CSSProperties = {
  border: "1px solid #e5e7eb",
  borderRadius: 16,
  padding: 20,
  background: "#ffffff",
  boxShadow: "0 8px 24px rgba(15, 23, 42, 0.06)",
};

const badgeBaseStyle: CSSProperties = {
  display: "inline-block",
  padding: "6px 10px",
  borderRadius: 999,
  fontSize: 12,
  fontWeight: 700,
};

const buttonPrimary: CSSProperties = {
  background: "#0f172a",
  color: "#ffffff",
  border: "none",
  borderRadius: 12,
  padding: "12px 16px",
  fontSize: 14,
  fontWeight: 600,
  cursor: "pointer",
};

const buttonSecondary: CSSProperties = {
  background: "#ffffff",
  color: "#0f172a",
  border: "1px solid #cbd5e1",
  borderRadius: 12,
  padding: "12px 16px",
  fontSize: 14,
  fontWeight: 600,
  cursor: "pointer",
};

const loadingStyle: CSSProperties = {
  ...cardStyle,
  textAlign: "center",
  color: "#475569",
};

const errorStyle: CSSProperties = {
  ...cardStyle,
  border: "1px solid #fecaca",
  background: "#fef2f2",
  color: "#b91c1c",
};

const infoStyle: CSSProperties = {
  ...cardStyle,
  border: "1px solid #bfdbfe",
  background: "#eff6ff",
  color: "#1e3a8a",
};

function getBadgeStyle(badge: string | null): CSSProperties {
  switch (badge) {
    case "fastest":
      return {
        ...badgeBaseStyle,
        background: "#ede9fe",
        color: "#6d28d9",
      };
    case "recommended":
      return {
        ...badgeBaseStyle,
        background: "#dcfce7",
        color: "#166534",
      };
    case "best_value":
      return {
        ...badgeBaseStyle,
        background: "#fef3c7",
        color: "#92400e",
      };
    default:
      return {
        ...badgeBaseStyle,
        background: "#e2e8f0",
        color: "#334155",
      };
  }
}

function formatBadgeLabel(badge: string | null): string {
  switch (badge) {
    case "fastest":
      return "Fastest";
    case "recommended":
      return "Recommended";
    case "best_value":
      return "Best value";
    default:
      return "Option";
  }
}

function formatPrice(price: number, currency: string): string {
  return `${new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(price)} ${currency}`;
}

export default function QuoteResultsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const quoteSessionId = useMemo(() => {
    const raw = searchParams.get("quoteSessionId");
    if (!raw) return null;

    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);

  const [data, setData] = useState<ShippingQuoteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectingId, setSelectingId] = useState<number | null>(null);

  const selectedQuote = useMemo(
    () => data?.quotes.find((quote) => quote.is_selected) ?? null,
    [data],
  );

  useEffect(() => {
    let isMounted = true;

    async function loadQuoteSession() {
      if (!quoteSessionId) {
        setError("Не найден quoteSessionId в URL.");
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const response = await getShippingQuote(quoteSessionId);
        if (isMounted) {
          setData(response);
        }
      } catch (err) {
        if (!isMounted) return;

        if (err instanceof ApiError) {
          setError(err.detail);
        } else if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Не удалось загрузить результаты расчёта.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadQuoteSession();

    return () => {
      isMounted = false;
    };
  }, [quoteSessionId]);

  async function handleSelectQuote(
    e: React.MouseEvent<HTMLButtonElement>,
    rateQuote: RateQuoteItem,
  ) {
    if (!quoteSessionId || rateQuote.id == null) return;

    e.currentTarget.blur();
    const savedScrollY = window.scrollY;
    setSelectingId(rateQuote.id);
    setError(null);

    let nextData: typeof data | null = null;
    let nextError: string | null = null;

    try {
      nextData = await selectShippingQuote(quoteSessionId, {
        rate_quote_id: rateQuote.id,
      });
    } catch (err) {
      if (err instanceof ApiError) {
        nextError = err.detail;
      } else if (err instanceof Error) {
        nextError = err.message;
      } else {
        nextError = "Не удалось выбрать тариф.";
      }
    }

    // flushSync commits all state changes to the DOM synchronously so that
    // the scrollTo below runs after layout is stable, not before.
    flushSync(() => {
      setSelectingId(null);
      if (nextData) setData(nextData);
      if (nextError) setError(nextError);
    });

    window.scrollTo({ top: savedScrollY, behavior: "instant" });
  }

  function handleContinueToShipment() {
    if (!quoteSessionId || !selectedQuote) {
      return;
    }

    router.push(`/quote/shipment?quoteSessionId=${quoteSessionId}`);
  }

  return (
    <main style={pageStyle}>
      <div style={containerStyle}>
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: 16,
            alignItems: "center",
            marginBottom: 28,
            flexWrap: "wrap",
          }}
        >
          <div>
            <div
              style={{
                ...badgeBaseStyle,
                background: "#eff6ff",
                color: "#1d4ed8",
              }}
            >
              Quote results
            </div>
            <h1 style={{ margin: "14px 0 8px", fontSize: 34, lineHeight: 1.1 }}>
              Доступные тарифы
            </h1>
          </div>

          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button style={buttonSecondary} onClick={() => router.push("/")}>
              Назад к форме
            </button>

            <button
              style={{
                ...buttonPrimary,
                opacity: selectedQuote ? 1 : 0.6,
                cursor: selectedQuote ? "pointer" : "not-allowed",
              }}
              onClick={handleContinueToShipment}
              disabled={!selectedQuote}
            >
              Продолжить оформление
            </button>
          </div>
        </header>

        {isLoading ? (
          <div style={loadingStyle}>Загружаем результаты расчёта...</div>
        ) : error ? (
          <div style={errorStyle}>{error}</div>
        ) : !data ? (
          <div style={errorStyle}>Нет данных для отображения.</div>
        ) : (
          <>
            <div
              style={{
                ...cardStyle,
                marginBottom: 20,
                display: "flex",
                justifyContent: "space-between",
                gap: 16,
                flexWrap: "wrap",
                alignItems: "center",
              }}
            >
              <div>
                <strong>Quote session ID:</strong> {data.quote_session_id}
              </div>
              <div style={{ color: "#475569" }}>
                Найдено тарифов: <strong>{data.quotes.length}</strong>
              </div>
            </div>

            {selectedQuote ? (
              <div style={{ ...infoStyle, marginBottom: 20 }}>
                <div style={{ marginBottom: 8 }}>
                  <strong>Выбранный тариф:</strong>{" "}
                  {selectedQuote.carrier_name} — {selectedQuote.tariff_name}
                </div>
                <div>
                  Стоимость:{" "}
                  <strong>
                    {formatPrice(selectedQuote.price, selectedQuote.currency)}
                  </strong>
                  {" • "}
                  Срок:{" "}
                  <strong>
                    {selectedQuote.eta_days_min}-{selectedQuote.eta_days_max} дн.
                  </strong>
                </div>
              </div>
            ) : (
              <div style={{ ...infoStyle, marginBottom: 20 }}>
                Сначала выберите один тариф, после этого можно будет продолжить
                оформление отправления.
              </div>
            )}

            <div style={{ display: "grid", gap: 16 }}>
              {data.quotes.map((quote) => (
                <div
                  key={quote.id ?? `${quote.carrier_code}-${quote.tariff_name}`}
                  style={{
                    ...cardStyle,
                    border: quote.is_selected
                      ? "1px solid #22c55e"
                      : "1px solid #e5e7eb",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 16,
                      flexWrap: "wrap",
                      alignItems: "flex-start",
                    }}
                  >
                    <div>
                      <div
                        style={{
                          display: "flex",
                          gap: 10,
                          flexWrap: "wrap",
                          alignItems: "center",
                          marginBottom: 10,
                        }}
                      >
                        <span style={getBadgeStyle(quote.badge)}>
                          {formatBadgeLabel(quote.badge)}
                        </span>

                        {quote.is_selected ? (
                          <span
                            style={{
                              ...badgeBaseStyle,
                              background: "#dcfce7",
                              color: "#166534",
                            }}
                          >
                            Selected
                          </span>
                        ) : null}
                      </div>

                      <h2 style={{ margin: "0 0 8px", fontSize: 22 }}>
                        {quote.carrier_name} — {quote.tariff_name}
                      </h2>

                      <p style={{ margin: "0 0 6px", color: "#475569" }}>
                        Код перевозчика: <strong>{quote.carrier_code}</strong>
                      </p>

                      <p style={{ margin: 0, color: "#475569" }}>
                        Срок доставки:{" "}
                        <strong>
                          {quote.eta_days_min}-{quote.eta_days_max} дн.
                        </strong>
                      </p>
                    </div>

                    <div style={{ textAlign: "right", minWidth: 180 }}>
                      <div
                        style={{
                          fontSize: 28,
                          fontWeight: 800,
                          marginBottom: 12,
                        }}
                      >
                        {formatPrice(quote.price, quote.currency)}
                      </div>

                      <button
                        style={{
                          ...buttonPrimary,
                          opacity:
                            selectingId === quote.id || quote.is_selected
                              ? 0.7
                              : 1,
                          cursor:
                            selectingId === quote.id || quote.is_selected
                              ? "not-allowed"
                              : "pointer",
                        }}
                        onClick={(e) => void handleSelectQuote(e, quote)}
                        disabled={
                          quote.id == null ||
                          selectingId === quote.id ||
                          quote.is_selected
                        }
                      >
                        {quote.is_selected
                          ? "Тариф выбран"
                          : selectingId === quote.id
                            ? "Сохраняем..."
                            : "Выбрать тариф"}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </main>
  );
}