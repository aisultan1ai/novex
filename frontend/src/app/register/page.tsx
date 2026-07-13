"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, ArrowLeft } from "lucide-react";

import { ApiError, registerUser } from "@/lib/api/auth";
import { useIsMobile } from "@/hooks/use-is-mobile";
import type { CustomerType, RegisterRequest } from "@/types/auth";

/* ─── Password strength ──────────────────────────────────────────────────── */

function getStrength(pwd: string): number {
  let score = 0;
  if (pwd.length >= 8) score++;
  if (/\d/.test(pwd)) score++;
  if (/[A-Z]/.test(pwd)) score++;
  if (/[^A-Za-z0-9]/.test(pwd)) score++;
  return score;
}

const STRENGTH_LABELS = ["", "Слабый", "Средний", "Хороший", "Надёжный"];
const STRENGTH_COLORS = ["#E5E7EB", "#EF4444", "#F59E0B", "#F59E0B", "#10B981"];

function PasswordStrength({ password }: { password: string }) {
  if (!password) return null;
  const score = getStrength(password);
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: "flex", gap: 4 }}>
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: 4,
              borderRadius: 2,
              background: i <= score ? STRENGTH_COLORS[score] : "#E5E7EB",
              transition: "background 0.2s",
            }}
          />
        ))}
      </div>
      <div
        style={{
          font: "500 12px/1 Inter Variable, sans-serif",
          color: STRENGTH_COLORS[score],
          marginTop: 4,
        }}
      >
        {STRENGTH_LABELS[score]}
      </div>
    </div>
  );
}

/* ─── Shared field ───────────────────────────────────────────────────────── */

function Field({
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  autoComplete,
  required,
  right,
  inputMode,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  autoComplete?: string;
  required?: boolean;
  right?: React.ReactNode;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
}) {
  const [focused, setFocused] = useState(false);
  return (
    <div>
      {label && (
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
      )}
      <div style={{ position: "relative" }}>
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          required={required}
          inputMode={inputMode}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={{
            width: "100%",
            padding: right ? "11px 40px 11px 14px" : "11px 14px",
            borderRadius: 10,
            border: focused ? "1.5px solid #2563EB" : "1.5px solid #E5E7EB",
            boxShadow: focused ? "0 0 0 3px rgba(37,99,235,0.15)" : "none",
            font: "400 14px/1 Inter Variable, sans-serif",
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

/* ─── Types ──────────────────────────────────────────────────────────────── */

type FormState = {
  email: string;
  password: string;
  full_name: string;
  phone: string;
  customer_type: CustomerType;
  company_name: string;
  tax_id: string;
};

const initial: FormState = {
  email: "",
  password: "",
  full_name: "",
  phone: "",
  customer_type: "individual",
  company_name: "",
  tax_id: "",
};

/* ─── Page ───────────────────────────────────────────────────────────────── */

export default function RegisterPage() {
  const router = useRouter();
  const isMobile = useIsMobile();
  const [form, setForm] = useState<FormState>(initial);
  const [showPwd, setShowPwd] = useState(false);
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
      tax_id: form.tax_id.trim(),
    };
  }

  function validateTaxId(): string | null {
    const cleaned = form.tax_id.trim();
    if (!/^\d{12}$/.test(cleaned)) {
      return `${isCompany ? "БИН" : "ИИН"} должен состоять ровно из 12 цифр.`;
    }
    return null;
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const taxErr = validateTaxId();
    if (taxErr) { setError(taxErr); return; }
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
      <div style={{ width: "100%", maxWidth: 420 }}>
        {/* Back */}
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
            padding: isMobile ? "24px 20px" : "32px 28px",
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
            Создать аккаунт
          </h1>
          <p
            style={{
              font: "400 14px/1 Inter Variable, sans-serif",
              color: "#6B7280",
              textAlign: "center",
              margin: "0 0 24px",
            }}
          >
            Регистрация займёт меньше минуты
          </p>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {/* Name + Phone */}
            <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: 12 }}>
              <Field
                label="ФИО"
                value={form.full_name}
                onChange={(v) => set("full_name", v)}
                placeholder="Ваше имя"
              />
              <Field
                label="Телефон"
                value={form.phone}
                onChange={(v) => set("phone", v)}
                placeholder="+7 700 000 0000"
                autoComplete="tel"
              />
            </div>

            {/* Email */}
            <Field
              label="Email"
              type="email"
              value={form.email}
              onChange={(v) => set("email", v)}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />

            {/* Password */}
            <div>
              <Field
                label="Пароль"
                type={showPwd ? "text" : "password"}
                value={form.password}
                onChange={(v) => set("password", v)}
                placeholder="Минимум 8 символов"
                autoComplete="new-password"
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
              <PasswordStrength password={form.password} />
            </div>

            {/* Customer type */}
            <div>
              <label
                style={{
                  display: "block",
                  font: "600 13px/1 Inter Variable, sans-serif",
                  color: "#374151",
                  marginBottom: 8,
                }}
              >
                Тип аккаунта
              </label>
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
                        border: active ? "1.5px solid #2563EB" : "1.5px solid #E5E7EB",
                        background: active ? "#EFF6FF" : "#ffffff",
                        color: active ? "#2563EB" : "#6B7280",
                        font: "600 13px/1 Inter Variable, sans-serif",
                        cursor: "pointer",
                        fontFamily: "inherit",
                        transition: "all 0.15s",
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
              <Field
                label="Название компании"
                value={form.company_name}
                onChange={(v) => set("company_name", v)}
                placeholder="ТОО «Название»"
                required={isCompany}
              />
            )}

            {/* ИИН / БИН */}
            <Field
              label={isCompany ? "БИН" : "ИИН"}
              value={form.tax_id}
              onChange={(v) => set("tax_id", v.replace(/\D/g, "").slice(0, 12))}
              placeholder="12 цифр"
              required
              inputMode="numeric"
            />

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
              {isSubmitting ? "Создаём аккаунт..." : "Создать аккаунт"}
            </button>
          </form>
        </div>

        {/* Switch to login */}
        <p
          style={{
            textAlign: "center",
            font: "400 14px/1 Inter Variable, sans-serif",
            color: "#6B7280",
            margin: "20px 0 0",
          }}
        >
          Уже есть аккаунт?{" "}
          <Link
            href="/login"
            style={{
              font: "600 14px/1 Inter Variable, sans-serif",
              color: "#2563EB",
              textDecoration: "none",
            }}
          >
            Войти
          </Link>
        </p>
      </div>
    </div>
  );
}
