"use client";

import Link from "next/link";

import { useAuth } from "@/components/providers/auth-provider";
import ShortQuoteForm from "@/components/forms/short-quote-form";

export default function HomePage() {
  const { isAuthenticated, isLoading } = useAuth();

  return (
    <div style={{ minHeight: "100vh", background: "#f9fafb" }}>

      {/* Navbar */}
      <nav
        style={{
          background: "#fff",
          borderBottom: "1px solid #f3f4f6",
          padding: "0 32px",
          height: 60,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          position: "sticky",
          top: 0,
          zIndex: 50,
        }}
      >
        <span
          style={{
            fontSize: 20,
            fontWeight: 900,
            letterSpacing: "-0.8px",
            color: "#111827",
          }}
        >
          Novex
        </span>

        {!isLoading && (
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {isAuthenticated ? (
              <Link
                href="/dashboard"
                style={{
                  padding: "8px 18px",
                  borderRadius: 10,
                  background: "#111827",
                  color: "#fff",
                  fontSize: 14,
                  fontWeight: 600,
                  textDecoration: "none",
                }}
              >
                Мой кабинет
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  style={{
                    padding: "8px 18px",
                    borderRadius: 10,
                    border: "1.5px solid #e5e7eb",
                    background: "#fff",
                    color: "#374151",
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
                    padding: "8px 18px",
                    borderRadius: 10,
                    background: "#111827",
                    color: "#fff",
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
      </nav>

      {/* Hero */}
      <div
        style={{
          maxWidth: 860,
          margin: "0 auto",
          padding: "60px 24px 80px",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <h1
            style={{
              fontSize: 48,
              fontWeight: 900,
              letterSpacing: "-1.5px",
              lineHeight: 1.1,
              color: "#111827",
              margin: "0 0 16px",
            }}
          >
            Доставка по Казахстану
          </h1>
          <p
            style={{
              fontSize: 18,
              color: "#6b7280",
              margin: 0,
              lineHeight: 1.6,
              maxWidth: 520,
              marginLeft: "auto",
              marginRight: "auto",
            }}
          >
            Сравните тарифы курьерских служб и оформите
            отправление онлайн за несколько минут
          </p>
        </div>

        {/* Quote form card */}
        <div
          style={{
            background: "#fff",
            border: "1px solid #e5e7eb",
            borderRadius: 20,
            padding: "32px 36px",
            boxShadow:
              "0 1px 3px rgba(0,0,0,0.05), 0 10px 40px rgba(0,0,0,0.06)",
          }}
        >
          <div style={{ marginBottom: 24 }}>
            <h2
              style={{
                margin: 0,
                fontSize: 20,
                fontWeight: 700,
                color: "#111827",
                letterSpacing: "-0.3px",
              }}
            >
              Рассчитать стоимость
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: 14, color: "#9ca3af" }}>
              Укажите маршрут и параметры отправления
            </p>
          </div>
          <ShortQuoteForm />
        </div>

        {/* Feature pills */}
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            gap: 32,
            marginTop: 40,
            flexWrap: "wrap",
          }}
        >
          {[
            "Мгновенный расчёт",
            "Лучшие тарифы",
            "Онлайн-оформление",
          ].map((f) => (
            <span
              key={f}
              style={{
                fontSize: 14,
                color: "#9ca3af",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span style={{ color: "#10b981", fontWeight: 700 }}>✓</span> {f}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
