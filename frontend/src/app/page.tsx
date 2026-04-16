import type { CSSProperties } from "react";

import ShortQuoteForm from "@/components/forms/short-quote-form";

export default function HomePage() {
  const cardStyle: CSSProperties = {
    border: "1px solid #e5e7eb",
    borderRadius: 16,
    padding: 20,
    background: "#ffffff",
    boxShadow: "0 8px 24px rgba(15, 23, 42, 0.06)",
  };

  const badgeStyle: CSSProperties = {
    display: "inline-block",
    padding: "6px 10px",
    borderRadius: 999,
    background: "#eff6ff",
    color: "#1d4ed8",
    fontSize: 12,
    fontWeight: 700,
  };

  const buttonPrimary: CSSProperties = {
    background: "#0f172a",
    color: "#ffffff",
    border: "none",
    borderRadius: 12,
    padding: "12px 18px",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  };

  const buttonSecondary: CSSProperties = {
    background: "#ffffff",
    color: "#0f172a",
    border: "1px solid #cbd5e1",
    borderRadius: 12,
    padding: "12px 18px",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  };

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%)",
        padding: "32px 20px 64px",
        color: "#0f172a",
        fontFamily:
          "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      }}
    >
      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 16,
            marginBottom: 40,
            flexWrap: "wrap",
          }}
        >
          <div>
            <div style={badgeStyle}>Novex MVP</div>
            <h1
              style={{
                margin: "16px 0 8px",
                fontSize: 40,
                lineHeight: 1.1,
                fontWeight: 800,
              }}
            >
              Агрегатор курьерских служб
            </h1>
            <p
              style={{
                margin: 0,
                maxWidth: 760,
                fontSize: 16,
                lineHeight: 1.6,
                color: "#475569",
              }}
            >
              Единый интерфейс для расчёта тарифа, выбора службы доставки,
              оформления отправления, оплаты и дальнейшего трекинга заказа.
            </p>
          </div>

          <div style={{ display: "flex", gap: 12 }}>
            <a href="/login" style={{ textDecoration: "none" }}>
              <button style={buttonSecondary}>Войти</button>
            </a>
            <a href="/register" style={{ textDecoration: "none" }}>
              <button style={buttonPrimary}>Регистрация</button>
            </a>
          </div>
        </header>

        <section>
          <div style={cardStyle}>
            <ShortQuoteForm />
          </div>
        </section>
      </div>
    </main>
  );
}