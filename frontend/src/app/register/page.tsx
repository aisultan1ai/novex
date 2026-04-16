"use client";

import type { CSSProperties, FormEvent } from "react";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, registerUser } from "@/lib/api/auth";
import type { CustomerType, RegisterRequest } from "@/types/auth";

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  background: "linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%)",
  padding: "32px 20px 64px",
  color: "#0f172a",
  fontFamily:
    "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
};

const cardStyle: CSSProperties = {
  maxWidth: 640,
  margin: "48px auto 0",
  border: "1px solid #e5e7eb",
  borderRadius: 20,
  padding: 24,
  background: "#ffffff",
  boxShadow: "0 8px 24px rgba(15, 23, 42, 0.06)",
};

const formGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  gap: 16,
  marginTop: 24,
};

const labelStyle: CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 600,
  marginBottom: 8,
  color: "#334155",
};

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "12px 14px",
  borderRadius: 12,
  border: "1px solid #cbd5e1",
  fontSize: 14,
  outline: "none",
  boxSizing: "border-box",
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

const hintStyle: CSSProperties = {
  marginTop: 8,
  color: "#64748b",
  fontSize: 13,
  lineHeight: 1.6,
};

const errorStyle: CSSProperties = {
  marginTop: 12,
  padding: "10px 12px",
  borderRadius: 12,
  background: "#fef2f2",
  color: "#b91c1c",
  fontSize: 13,
  lineHeight: 1.5,
};

type RegisterFormState = {
  email: string;
  password: string;
  full_name: string;
  phone: string;
  customer_type: CustomerType;
  company_name: string;
};

const initialState: RegisterFormState = {
  email: "",
  password: "",
  full_name: "",
  phone: "",
  customer_type: "individual",
  company_name: "",
};

export default function RegisterPage() {
  const router = useRouter();

  const [form, setForm] = useState<RegisterFormState>(initialState);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isCompany = useMemo(
    () => form.customer_type === "company",
    [form.customer_type],
  );

  function updateField<K extends keyof RegisterFormState>(
    key: K,
    value: RegisterFormState[K],
  ) {
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await registerUser(toPayload());
      router.push("/login?registered=1");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Не удалось выполнить регистрацию.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main style={pageStyle}>
      <div style={cardStyle}>
        <div
          style={{
            display: "inline-block",
            padding: "6px 10px",
            borderRadius: 999,
            background: "#eff6ff",
            color: "#1d4ed8",
            fontSize: 12,
            fontWeight: 700,
            marginBottom: 14,
          }}
        >
          Novex Auth
        </div>

        <h1 style={{ margin: "0 0 8px", fontSize: 32, lineHeight: 1.1 }}>
          Регистрация
        </h1>
        <p style={{ margin: 0, color: "#475569", lineHeight: 1.7 }}>
          Создание клиентского аккаунта Novex.
        </p>

        <form onSubmit={handleSubmit} style={formGridStyle}>
          <div>
            <label style={labelStyle}>Email</label>
            <input
              style={inputStyle}
              type="email"
              value={form.email}
              onChange={(e) => updateField("email", e.target.value)}
              placeholder="Введите email"
              autoComplete="email"
            />
          </div>

          <div>
            <label style={labelStyle}>Пароль</label>
            <input
              style={inputStyle}
              type="password"
              value={form.password}
              onChange={(e) => updateField("password", e.target.value)}
              placeholder="Введите пароль"
              autoComplete="new-password"
            />
          </div>

          <div>
            <label style={labelStyle}>ФИО</label>
            <input
              style={inputStyle}
              value={form.full_name}
              onChange={(e) => updateField("full_name", e.target.value)}
              placeholder="Введите ФИО"
            />
          </div>

          <div>
            <label style={labelStyle}>Телефон</label>
            <input
              style={inputStyle}
              value={form.phone}
              onChange={(e) => updateField("phone", e.target.value)}
              placeholder="Введите номер телефона"
            />
          </div>

          <div>
            <label style={labelStyle}>Тип клиента</label>
            <select
              style={inputStyle}
              value={form.customer_type}
              onChange={(e) =>
                updateField("customer_type", e.target.value as CustomerType)
              }
            >
              <option value="individual">Физическое лицо</option>
              <option value="company">Компания</option>
            </select>
          </div>

          <div>
            <label style={labelStyle}>Компания</label>
            <input
              style={inputStyle}
              value={form.company_name}
              onChange={(e) => updateField("company_name", e.target.value)}
              placeholder="Введите название компании"
              disabled={!isCompany}
            />
            <div style={hintStyle}>Для типа `company` поле обязательно.</div>
          </div>

          <div style={{ gridColumn: "1 / -1" }}>
            <button
              type="submit"
              style={{
                ...buttonPrimary,
                opacity: isSubmitting ? 0.7 : 1,
                cursor: isSubmitting ? "not-allowed" : "pointer",
              }}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Регистрируем..." : "Создать аккаунт"}
            </button>
          </div>
        </form>

        {error ? <div style={errorStyle}>{error}</div> : null}

        <div style={hintStyle}>
          Уже есть аккаунт? <a href="/login">Перейти ко входу</a>
        </div>
      </div>
    </main>
  );
}