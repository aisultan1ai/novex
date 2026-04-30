"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, registerUser } from "@/lib/api/auth";
import type { CustomerType, RegisterRequest } from "@/types/auth";

type FormState = {
  email: string;
  password: string;
  full_name: string;
  phone: string;
  customer_type: CustomerType;
  company_name: string;
};

const initial: FormState = {
  email: "",
  password: "",
  full_name: "",
  phone: "",
  customer_type: "individual",
  company_name: "",
};

const inp: React.CSSProperties = {
  width: "100%",
  padding: "12px 14px",
  borderRadius: 10,
  border: "1px solid #e5e7eb",
  fontSize: 14,
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

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(initial);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isCompany = useMemo(() => form.customer_type === "company", [form.customer_type]);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function toPayload(): RegisterRequest {
    return {
      email: form.email.trim().toLowerCase(),
      password: form.password,
      full_name: form.full_name.trim() || null,
      phone: form.phone.trim() || null,
      customer_type: form.customer_type,
      company_name: isCompany ? form.company_name.trim() || null : null,
    };
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await registerUser(toPayload());
      router.push("/login?registered=1");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : "Не удалось создать аккаунт.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  function focusStyle(e: React.FocusEvent<HTMLInputElement>) {
    e.currentTarget.style.borderColor = "#0f172a";
    e.currentTarget.style.background = "#ffffff";
  }

  function blurStyle(e: React.FocusEvent<HTMLInputElement>) {
    e.currentTarget.style.borderColor = "#e5e7eb";
    e.currentTarget.style.background = "#f8fafc";
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
      <div style={{ width: "100%", maxWidth: 440 }}>
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
            Создать аккаунт
          </h1>
          <p style={{ margin: "0 0 24px", fontSize: 14, color: "#64748b" }}>
            Регистрация займёт меньше минуты
          </p>

          <form onSubmit={handleSubmit} style={{ display: "grid", gap: 16 }}>
            {/* Email + Password */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <label style={lbl}>Email</label>
                <input
                  style={inp}
                  type="email"
                  value={form.email}
                  onChange={(e) => set("email", e.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                  onFocus={focusStyle}
                  onBlur={blurStyle}
                />
              </div>
              <div>
                <label style={lbl}>Пароль</label>
                <input
                  style={inp}
                  type="password"
                  value={form.password}
                  onChange={(e) => set("password", e.target.value)}
                  placeholder="Минимум 8 символов"
                  autoComplete="new-password"
                  required
                  onFocus={focusStyle}
                  onBlur={blurStyle}
                />
              </div>
            </div>

            {/* Name + Phone */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <label style={lbl}>ФИО</label>
                <input
                  style={inp}
                  value={form.full_name}
                  onChange={(e) => set("full_name", e.target.value)}
                  placeholder="Иванов Иван"
                  onFocus={focusStyle}
                  onBlur={blurStyle}
                />
              </div>
              <div>
                <label style={lbl}>Телефон</label>
                <input
                  style={inp}
                  value={form.phone}
                  onChange={(e) => set("phone", e.target.value)}
                  placeholder="+7 700 000 0000"
                  inputMode="tel"
                  onFocus={focusStyle}
                  onBlur={blurStyle}
                />
              </div>
            </div>

            {/* Customer type toggle */}
            <div>
              <label style={lbl}>Тип аккаунта</label>
              <div style={{ display: "flex", gap: 8 }}>
                {(
                  [
                    { value: "individual", label: "Физическое лицо" },
                    { value: "company", label: "Компания" },
                  ] as { value: CustomerType; label: string }[]
                ).map(({ value, label }) => {
                  const active = form.customer_type === value;
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => set("customer_type", value)}
                      style={{
                        flex: 1,
                        padding: "10px",
                        borderRadius: 10,
                        border: active ? "none" : "1px solid #e5e7eb",
                        background: active ? "#0f172a" : "#ffffff",
                        color: active ? "#ffffff" : "#64748b",
                        fontSize: 14,
                        fontWeight: 600,
                        cursor: "pointer",
                        fontFamily: "inherit",
                      }}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Company name */}
            {isCompany && (
              <div>
                <label style={lbl}>Название компании</label>
                <input
                  style={inp}
                  value={form.company_name}
                  onChange={(e) => set("company_name", e.target.value)}
                  placeholder="ТОО «Название»"
                  required={isCompany}
                  onFocus={focusStyle}
                  onBlur={blurStyle}
                />
              </div>
            )}

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
              {isSubmitting ? "Создаём аккаунт..." : "Создать аккаунт"}
            </button>
          </form>

          <p style={{ margin: "20px 0 0", fontSize: 14, color: "#64748b", textAlign: "center" }}>
            Уже есть аккаунт?{" "}
            <Link href="/login" style={{ color: "#0f172a", fontWeight: 600, textDecoration: "none" }}>
              Войти
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
