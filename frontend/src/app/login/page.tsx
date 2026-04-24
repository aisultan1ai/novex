"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { ApiError, loginUser } from "@/lib/api/auth";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();

  const isRegistered = useMemo(
    () => searchParams.get("registered") === "1",
    [searchParams],
  );
  const nextPath = useMemo(() => {
    const raw = searchParams.get("next");
    return raw && raw.startsWith("/") ? raw : "/dashboard";
  }, [searchParams]);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const res = await loginUser({ email: email.trim().toLowerCase(), password });
      login(res.access_token, res.profile);
      router.push(nextPath);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : "Не удалось выполнить вход.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  const inp: React.CSSProperties = {
    width: "100%",
    padding: "12px 14px",
    borderRadius: 10,
    border: "1.5px solid #e5e7eb",
    fontSize: 15,
    outline: "none",
    boxSizing: "border-box",
    color: "#111827",
    background: "#fff",
    fontFamily: "inherit",
  };

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
        }}
      >
        <Link
          href="/"
          style={{
            fontSize: 20,
            fontWeight: 900,
            letterSpacing: "-0.8px",
            color: "#111827",
            textDecoration: "none",
          }}
        >
          Novex
        </Link>
      </nav>

      {/* Form card */}
      <div
        style={{
          maxWidth: 440,
          margin: "60px auto 0",
          padding: "0 16px",
        }}
      >
        <div
          style={{
            background: "#fff",
            border: "1px solid #e5e7eb",
            borderRadius: 20,
            padding: "36px 32px",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05), 0 8px 30px rgba(0,0,0,0.06)",
          }}
        >
          <h1
            style={{
              margin: "0 0 6px",
              fontSize: 26,
              fontWeight: 800,
              letterSpacing: "-0.5px",
              color: "#111827",
            }}
          >
            Вход в аккаунт
          </h1>
          <p style={{ margin: "0 0 28px", fontSize: 14, color: "#9ca3af" }}>
            Добро пожаловать в Novex
          </p>

          {isRegistered && (
            <div
              style={{
                marginBottom: 20,
                padding: "12px 14px",
                borderRadius: 10,
                background: "#f0fdf4",
                border: "1px solid #bbf7d0",
                color: "#166534",
                fontSize: 14,
                fontWeight: 500,
              }}
            >
              Аккаунт создан — теперь войдите.
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "grid", gap: 16 }}>
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 13,
                  fontWeight: 600,
                  color: "#374151",
                  marginBottom: 6,
                }}
              >
                Email
              </label>
              <input
                style={inp}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
            </div>

            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 13,
                  fontWeight: 600,
                  color: "#374151",
                  marginBottom: 6,
                }}
              >
                Пароль
              </label>
              <input
                style={inp}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Минимум 8 символов"
                autoComplete="current-password"
                required
              />
            </div>

            {error && (
              <div
                style={{
                  padding: "11px 14px",
                  borderRadius: 10,
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  color: "#b91c1c",
                  fontSize: 13,
                }}
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              style={{
                width: "100%",
                padding: "13px",
                borderRadius: 11,
                border: "none",
                background: isSubmitting ? "#6b7280" : "#111827",
                color: "#fff",
                fontSize: 15,
                fontWeight: 700,
                cursor: isSubmitting ? "not-allowed" : "pointer",
                fontFamily: "inherit",
                marginTop: 4,
              }}
            >
              {isSubmitting ? "Входим..." : "Войти"}
            </button>
          </form>

          <p
            style={{
              margin: "20px 0 0",
              fontSize: 14,
              color: "#6b7280",
              textAlign: "center",
            }}
          >
            Нет аккаунта?{" "}
            <Link
              href="/register"
              style={{ color: "#111827", fontWeight: 600, textDecoration: "none" }}
            >
              Зарегистрироваться
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
