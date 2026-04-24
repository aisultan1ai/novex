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

  const inp: React.CSSProperties = {
    width: "100%",
    padding: "12px 14px",
    borderRadius: 10,
    border: "1.5px solid #e5e7eb",
    fontSize: 14,
    outline: "none",
    boxSizing: "border-box",
    color: "#111827",
    background: "#fff",
    fontFamily: "inherit",
  };

  const lbl: React.CSSProperties = {
    display: "block",
    fontSize: 13,
    fontWeight: 600,
    color: "#374151",
    marginBottom: 6,
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
      <div style={{ maxWidth: 520, margin: "48px auto 60px", padding: "0 16px" }}>
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
            Создать аккаунт
          </h1>
          <p style={{ margin: "0 0 28px", fontSize: 14, color: "#9ca3af" }}>
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
                        border: active ? "1.5px solid #111827" : "1.5px solid #e5e7eb",
                        background: active ? "#111827" : "#fff",
                        color: active ? "#fff" : "#6b7280",
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

            {/* Company name — only when type = company */}
            {isCompany && (
              <div>
                <label style={lbl}>Название компании</label>
                <input
                  style={inp}
                  value={form.company_name}
                  onChange={(e) => set("company_name", e.target.value)}
                  placeholder="ТОО «Название»"
                  required={isCompany}
                />
              </div>
            )}

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
              {isSubmitting ? "Создаём аккаунт..." : "Создать аккаунт"}
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
            Уже есть аккаунт?{" "}
            <Link
              href="/login"
              style={{ color: "#111827", fontWeight: 600, textDecoration: "none" }}
            >
              Войти
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
