"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { ApiError, loginUser } from "@/lib/api/auth";

const inp: React.CSSProperties = {
  width: "100%",
  padding: "12px 14px",
  borderRadius: 10,
  border: "1px solid #e5e7eb",
  fontSize: 15,
  outline: "none",
  boxSizing: "border-box",
  color: "#0f172a",
  background: "#f8fafc",
  fontFamily: "inherit",
  transition: "border-color 0.15s, background 0.15s",
};

const lbl: React.CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 600,
  color: "#334155",
  marginBottom: 8,
};

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();

  const isRegistered = useMemo(() => searchParams.get("registered") === "1", [searchParams]);
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

  return (
    <div
      style={{
        background: "#f1f5f9",
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "20px 16px",
      }}
    >
      <div style={{ width: "100%", maxWidth: 400 }}>
        {/* Back link */}
        <Link
          href="/"
          style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 13, color: "#64748b", textDecoration: "none", fontWeight: 500, marginBottom: 24 }}
          onMouseEnter={(e) => { e.currentTarget.style.color = "#0f172a"; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = "#64748b"; }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          На главную
        </Link>

        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <Link href="/" style={{ fontSize: 26, fontWeight: 800, color: "#0f172a", textDecoration: "none", letterSpacing: "-0.5px" }}>
            Novex
          </Link>
        </div>

        <div
          style={{
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            borderRadius: 16,
            padding: 40,
            boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)",
          }}
        >
          <h1 style={{ margin: "0 0 6px", fontSize: 20, fontWeight: 700, color: "#0f172a" }}>
            Войти в аккаунт
          </h1>
          <p style={{ margin: "0 0 24px", fontSize: 14, color: "#64748b" }}>
            Добро пожаловать в Novex
          </p>

          {isRegistered && (
            <div style={{ marginBottom: 20, padding: "12px 14px", borderRadius: 10, background: "#f0fdf4", border: "1px solid #bbf7d0", color: "#166534", fontSize: 14, fontWeight: 500 }}>
              Аккаунт создан — теперь войдите.
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "grid", gap: 16 }}>
            <div>
              <label style={lbl}>Email</label>
              <input
                style={inp}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
                onFocus={(e) => { e.currentTarget.style.borderColor = "#0f172a"; e.currentTarget.style.background = "#ffffff"; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = "#e5e7eb"; e.currentTarget.style.background = "#f8fafc"; }}
              />
            </div>

            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <label style={{ ...lbl, marginBottom: 0 }}>Пароль</label>
                <Link href="/forgot-password" style={{ fontSize: 13, color: "#64748b", textDecoration: "none", fontWeight: 500 }}>
                  Забыли пароль?
                </Link>
              </div>
              <input
                style={inp}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Минимум 8 символов"
                autoComplete="current-password"
                required
                onFocus={(e) => { e.currentTarget.style.borderColor = "#0f172a"; e.currentTarget.style.background = "#ffffff"; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = "#e5e7eb"; e.currentTarget.style.background = "#f8fafc"; }}
              />
            </div>

            {error && (
              <div style={{ padding: "11px 14px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 13 }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              style={{
                width: "100%",
                height: 52,
                borderRadius: 12,
                border: "none",
                background: "#0f172a",
                color: "#ffffff",
                fontSize: 16,
                fontWeight: 600,
                cursor: isSubmitting ? "not-allowed" : "pointer",
                opacity: isSubmitting ? 0.7 : 1,
                fontFamily: "inherit",
                marginTop: 4,
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => { if (!isSubmitting) e.currentTarget.style.background = "#1e293b"; }}
              onMouseLeave={(e) => { if (!isSubmitting) e.currentTarget.style.background = "#0f172a"; }}
            >
              {isSubmitting ? "Входим..." : "Войти"}
            </button>
          </form>

          <p style={{ margin: "20px 0 0", fontSize: 14, color: "#64748b", textAlign: "center" }}>
            Нет аккаунта?{" "}
            <Link href="/register" style={{ color: "#0f172a", fontWeight: 600, textDecoration: "none" }}>
              Зарегистрироваться
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
