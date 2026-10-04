"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, ArrowLeft } from "lucide-react";

import { ApiError, registerUser } from "@/lib/api/auth";
import { useIsMobile } from "@/hooks/use-is-mobile";
import type { CustomerType, RegisterRequest } from "@/types/auth";
import PdConsentCheckbox from "@/components/forms/PdConsentCheckbox";

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
const STRENGTH_COLORS = ["#E2E8EE", "#EF4444", "#F59E0B", "#F59E0B", "#10B981"];

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
              background: i <= score ? STRENGTH_COLORS[score] : "#E2E8EE",
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
            border: focused ? "1.5px solid #0B2545" : "1.5px solid #E2E8EE",
            boxShadow: focused ? "0 0 0 3px rgba(11,37,69,0.15)" : "none",
            font: "400 14px/1 Inter Variable, sans-serif",
            color: "#0E1826",
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
  pd_consent: boolean;
};

const initial: FormState = {
  email: "",
  password: "",
  full_name: "",
  phone: "",
  customer_type: "individual",
  company_name: "",
  tax_id: "",
  pd_consent: false,
};

/* ─── Page ───────────────────────────────────────────────────────────────── */

export default function RegisterPage() {
  const router = useRouter();
  const isMobile = useIsMobile();
  const [form, setForm] = useState<FormState>(initial);
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [verifyModalEmail, setVerifyModalEmail] = useState<string | null>(null);

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
      pd_consent: form.pd_consent,
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
    if (!form.pd_consent) {
      setError("Чтобы создать аккаунт, подтвердите согласие на обработку персональных данных.");
      return;
    }
    setIsSubmitting(true);
    try {
      const created = await registerUser(toPayload());
      // Show a "check your inbox" modal before sending the user to /login.
      // Existing accounts (backfilled email_verified=true in migration 036)
      // don't get the modal - but freshly created ones always do.
      if (!created.email_verified) {
        setVerifyModalEmail(created.email);
        return;
      }
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
            color: "#5F6E7E",
            textDecoration: "none",
            marginBottom: 28,
            transition: "color 0.15s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "#0E1826")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "#5F6E7E")}
        >
          <ArrowLeft size={14} />
          На главную
        </Link>

        {/* Logo */}
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 28 }}>
          <Link
            href="/"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              textDecoration: "none",
              font: "700 24px/1 'Space Grotesk Variable', 'Inter Variable', sans-serif",
              letterSpacing: "-0.02em",
              color: "#0E1826",
            }}
          >
            <svg
              width="30"
              height="27"
              viewBox="10 11 38 34"
              fill="none"
              role="img"
              aria-hidden="true"
              style={{ flexShrink: 0, display: "block" }}
            >
              <circle cx="17" cy="28" r="5" fill="#22C9E0" />
              <line x1="20" y1="25.5" x2="37" y2="17" stroke="#3E6E8A" strokeWidth="2.2" strokeLinecap="round" />
              <line x1="21" y1="28" x2="38" y2="28" stroke="#22C9E0" strokeWidth="2.4" strokeLinecap="round" />
              <line x1="20" y1="30.5" x2="37" y2="39" stroke="#3E6E8A" strokeWidth="2.2" strokeLinecap="round" />
              <circle cx="40" cy="16" r="3.4" fill="#3E6E8A" />
              <circle cx="41" cy="28" r="4.6" fill="#22C9E0" />
              <circle cx="40" cy="40" r="3.4" fill="#3E6E8A" />
            </svg>
            <span>n<span style={{ color: "#22C9E0" }}>o</span>vex</span>
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
              color: "#0E1826",
              margin: "0 0 4px",
              textAlign: "center",
            }}
          >
            Создать аккаунт
          </h1>
          <p
            style={{
              font: "400 14px/1 Inter Variable, sans-serif",
              color: "#5F6E7E",
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
                        border: active ? "1.5px solid #0B2545" : "1.5px solid #E2E8EE",
                        background: active ? "#F1F5F9" : "#ffffff",
                        color: active ? "#0B2545" : "#5F6E7E",
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

            <PdConsentCheckbox checked={form.pd_consent} onChange={(v) => set("pd_consent", v)} />

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
                background: isSubmitting ? "#94A6C0" : "#0B2545",
                color: "#ffffff",
                font: "600 15px/1 Inter Variable, sans-serif",
                cursor: isSubmitting ? "not-allowed" : "pointer",
                fontFamily: "inherit",
                marginTop: 4,
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => {
                if (!isSubmitting) e.currentTarget.style.background = "#0E2E5C";
              }}
              onMouseLeave={(e) => {
                if (!isSubmitting) e.currentTarget.style.background = "#0B2545";
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
            color: "#5F6E7E",
            margin: "20px 0 0",
          }}
        >
          Уже есть аккаунт?{" "}
          <Link
            href="/login"
            style={{
              font: "600 14px/1 Inter Variable, sans-serif",
              color: "#0B2545",
              textDecoration: "none",
            }}
          >
            Войти
          </Link>
        </p>
      </div>

      {verifyModalEmail && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed", inset: 0, background: "rgba(15,23,42,0.55)",
            display: "flex", alignItems: "center", justifyContent: "center",
            padding: 20, zIndex: 100,
          }}
        >
          <div
            style={{
              background: "#ffffff", borderRadius: 18, maxWidth: 440, width: "100%",
              padding: isMobile ? "28px 22px" : "32px 30px",
              boxShadow: "0 24px 64px rgba(15,23,42,0.28)",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: 44, marginBottom: 12 }}>📩</div>
            <h2 style={{ font: "700 20px/1.3 Inter Variable, sans-serif", color: "#0E1826", margin: "0 0 10px" }}>
              Аккаунт создан
            </h2>
            <p style={{ font: "400 14px/1.6 Inter Variable, sans-serif", color: "#4B5563", margin: "0 0 8px" }}>
              Мы отправили письмо на <b style={{ color: "#0E1826" }}>{verifyModalEmail}</b>.
            </p>
            <p style={{ font: "400 14px/1.6 Inter Variable, sans-serif", color: "#4B5563", margin: "0 0 24px" }}>
              Перейдите по ссылке в письме, чтобы подтвердить аккаунт. Проверьте папку «Спам», если письмо не пришло - ссылка живёт 24 часа.
            </p>
            <button
              type="button"
              onClick={() => { setVerifyModalEmail(null); router.push("/login?registered=1"); }}
              style={{
                width: "100%", height: 46, borderRadius: 10, border: "none",
                background: "#0B2545", color: "#ffffff",
                font: "600 15px/1 Inter Variable, sans-serif",
                cursor: "pointer", fontFamily: "inherit", transition: "background 0.15s",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "#0E2E5C"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "#0B2545"; }}
            >
              Понятно
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
