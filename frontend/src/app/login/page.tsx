"use client";

import type { CSSProperties, FormEvent } from "react";
import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ApiError, loginUser, saveAccessToken } from "@/lib/api/auth";

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  background: "linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%)",
  padding: "32px 20px 64px",
  color: "#0f172a",
  fontFamily:
    "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
};

const cardStyle: CSSProperties = {
  maxWidth: 520,
  margin: "48px auto 0",
  border: "1px solid #e5e7eb",
  borderRadius: 20,
  padding: 24,
  background: "#ffffff",
  boxShadow: "0 8px 24px rgba(15, 23, 42, 0.06)",
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

const successStyle: CSSProperties = {
  marginTop: 12,
  padding: "10px 12px",
  borderRadius: 12,
  background: "#ecfdf5",
  color: "#166534",
  fontSize: 13,
  lineHeight: 1.5,
};

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const isRegistered = useMemo(
    () => searchParams.get("registered") === "1",
    [searchParams],
  );

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const response = await loginUser({
        email: email.trim().toLowerCase(),
        password,
      });

      saveAccessToken(response.access_token);
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Не удалось выполнить вход.");
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
          Войти
        </h1>
        <p style={{ margin: 0, color: "#475569", lineHeight: 1.7 }}>
          Вход в личный кабинет Novex.
        </p>

        {isRegistered ? (
          <div style={successStyle}>
            Регистрация прошла успешно. Теперь можно войти в систему.
          </div>
        ) : null}

        <form
          onSubmit={handleSubmit}
          style={{ display: "grid", gap: 16, marginTop: 24 }}
        >
          <div>
            <label style={labelStyle}>Email</label>
            <input
              style={inputStyle}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Введите email"
              autoComplete="email"
            />
          </div>

          <div>
            <label style={labelStyle}>Пароль</label>
            <input
              style={inputStyle}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Введите пароль"
              autoComplete="current-password"
            />
          </div>

          <button
            type="submit"
            style={{
              ...buttonPrimary,
              opacity: isSubmitting ? 0.7 : 1,
              cursor: isSubmitting ? "not-allowed" : "pointer",
            }}
            disabled={isSubmitting}
          >
            {isSubmitting ? "Входим..." : "Войти"}
          </button>
        </form>

        {error ? <div style={errorStyle}>{error}</div> : null}

        <div style={hintStyle}>
          Нет аккаунта? <a href="/register">Создать аккаунт</a>
        </div>
      </div>
    </main>
  );
}