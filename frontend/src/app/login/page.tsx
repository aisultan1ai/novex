"use client";

import type { FormEvent } from "react";
import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, ArrowLeft } from "lucide-react";

import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { ApiError, loginUser } from "@/lib/api/auth";

/* ─── Shared input component ─────────────────────────────────────────────── */

function Field({
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  autoComplete,
  required,
  right,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  autoComplete?: string;
  required?: boolean;
  right?: React.ReactNode;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <div>
      <label
        style={{
          display: "block",
          font: "600 13px/1 Inter Variable, sans-serif",
          color: "#374151",
          marginBottom: 8,
        }}
      >
        {label}
      </label>
      <div style={{ position: "relative" }}>
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          required={required}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={{
            width: "100%",
            padding: right ? "12px 44px 12px 14px" : "12px 14px",
            borderRadius: 10,
            border: focused ? "1.5px solid #2563EB" : "1.5px solid #E5E7EB",
            boxShadow: focused ? "0 0 0 3px rgba(37,99,235,0.15)" : "none",
            font: "400 15px/1 Inter Variable, sans-serif",
            color: "#111827",
            background: "#fff",
            outline: "none",
            boxSizing: "border-box",
            fontFamily: "inherit",
            transition: "border-color 0.15s, box-shadow 0.15s",
          }}
        />
        {right && (
          <div
            style={{
              position: "absolute",
              right: 12,
              top: "50%",
              transform: "translateY(-50%)",
            }}
          >
            {right}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Login page ─────────────────────────────────────────────────────────── */

function LoginPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const isMobile = useIsMobile();

  const isRegistered = useMemo(() => searchParams.get("registered") === "1", [searchParams]);
  const isExpired = useMemo(() => searchParams.get("expired") === "1", [searchParams]);
  const nextPath = useMemo(() => {
    const raw = searchParams.get("next");
    if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return "/dashboard";
    if (/[\\\x00-\x1f]/.test(raw)) return "/dashboard";
    try {
      const resolved = new URL(raw, window.location.origin);
      if (resolved.origin !== window.location.origin) return "/dashboard";
    } catch {
      return "/dashboard";
    }
    return raw;
  }, [searchParams]);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const res = await loginUser({ email: email.trim().toLowerCase(), password });
      login(res.profile, res.expires_in);

      const role = res.profile.role;

      if (role === "carrier") {
        router.push("/dashboard/carrier");
      } else if (role === "admin" || role === "operator") {
        router.push("/dashboard/admin");
      } else {
        router.push(nextPath);
      }
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
        background: "#F4F6FB",
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px 16px",
      }}
    >
      <div style={{ width: "100%", maxWidth: 400 }}>
        {/* Back link */}
        <Link
          href="/"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            font: "500 13px/1 Inter Variable, sans-serif",
            color: "#6B7280",
            textDecoration: "none",
            marginBottom: 28,
            transition: "color 0.15s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "#111827")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "#6B7280")}
        >
          <ArrowLeft size={14} />
          На главную
        </Link>

        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <Link
            href="/"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              textDecoration: "none",
              font: "700 24px/1 Inter Variable, sans-serif",
              letterSpacing: "-0.02em",
              color: "#111827",
            }}
          >
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: "#2563EB",
                flexShrink: 0,
              }}
            />
            novex
          </Link>
        </div>

        {/* Card */}
        <div
          style={{
            background: "#ffffff",
            borderRadius: 18,
            padding: isMobile ? "24px 20px" : "36px 32px",
            boxShadow: "0 12px 40px rgba(17,24,39,0.08)",
          }}
        >
          <h1
            style={{
              font: "700 22px/1.2 Inter Variable, sans-serif",
              color: "#111827",
              margin: "0 0 4px",
              textAlign: "center",
            }}
          >
            Войти в аккаунт
          </h1>
          <p
            style={{
              font: "400 14px/1 Inter Variable, sans-serif",
              color: "#6B7280",
              textAlign: "center",
              margin: "0 0 28px",
            }}
          >
            Добро пожаловать в Novex
          </p>

          {isRegistered && (
            <div
              style={{
                marginBottom: 20,
                padding: "12px 14px",
                borderRadius: 10,
                background: "#D1FAE5",
                color: "#065F46",
                font: "500 14px/1.4 Inter Variable, sans-serif",
              }}
            >
              Аккаунт создан - войдите, чтобы продолжить.
            </div>
          )}

          {isExpired && (
            <div
              style={{
                marginBottom: 20,
                padding: "12px 14px",
                borderRadius: 10,
                background: "#FEF3C7",
                color: "#92400E",
                font: "500 14px/1.4 Inter Variable, sans-serif",
              }}
            >
              Сессия истекла. Пожалуйста, войдите снова.
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Field
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />

            <div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 8,
                }}
              >
                <label style={{ font: "600 13px/1 Inter Variable, sans-serif", color: "#374151" }}>
                  Пароль
                </label>
                <Link
                  href="/forgot-password"
                  style={{
                    font: "500 13px/1 Inter Variable, sans-serif",
                    color: "#6B7280",
                    textDecoration: "none",
                    transition: "color 0.15s",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = "#2563EB")}
                  onMouseLeave={(e) => (e.currentTarget.style.color = "#6B7280")}
                >
                  Забыли пароль?
                </Link>
              </div>
              <Field
                label=""
                type={showPwd ? "text" : "password"}
                value={password}
                onChange={setPassword}
                placeholder="Минимум 8 символов"
                autoComplete="current-password"
                required
                right={
                  <button
                    type="button"
                    onClick={() => setShowPwd((p) => !p)}
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: 0,
                      color: "#9CA3AF",
                      display: "flex",
                    }}
                  >
                    {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                }
              />
            </div>

            {error && (
              <div
                style={{
                  padding: "11px 14px",
                  borderRadius: 10,
                  background: "#FEF2F2",
                  border: "1px solid #FECACA",
                  color: "#B91C1C",
                  font: "400 13px/1.4 Inter Variable, sans-serif",
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
                height: 48,
                borderRadius: 10,
                border: "none",
                background: isSubmitting ? "#93C5FD" : "#2563EB",
                color: "#ffffff",
                font: "600 15px/1 Inter Variable, sans-serif",
                cursor: isSubmitting ? "not-allowed" : "pointer",
                fontFamily: "inherit",
                marginTop: 4,
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => {
                if (!isSubmitting) e.currentTarget.style.background = "#1D4ED8";
              }}
              onMouseLeave={(e) => {
                if (!isSubmitting) e.currentTarget.style.background = "#2563EB";
              }}
            >
              {isSubmitting ? "Входим..." : "Войти"}
            </button>
          </form>
        </div>

        {/* Switch to register */}
        <p
          style={{
            textAlign: "center",
            font: "400 14px/1 Inter Variable, sans-serif",
            color: "#6B7280",
            margin: "20px 0 0",
          }}
        >
          Нет аккаунта?{" "}
          <Link
            href="/register"
            style={{
              font: "600 14px/1 Inter Variable, sans-serif",
              color: "#2563EB",
              textDecoration: "none",
            }}
          >
            Зарегистрироваться
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginPageInner />
    </Suspense>
  );
}
