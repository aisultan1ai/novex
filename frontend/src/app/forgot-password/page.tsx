"use client";

import { useState } from "react";
import Link from "next/link";

import { forgotPassword, ApiError } from "@/lib/api/auth";

const inp: React.CSSProperties = {
  width: "100%", padding: "12px 14px", borderRadius: 10, border: "1px solid #e5e7eb",
  fontSize: 15, outline: "none", boxSizing: "border-box", color: "#0f172a",
  background: "#f8fafc", fontFamily: "inherit", transition: "border-color 0.15s, background 0.15s",
};

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await forgotPassword(email.trim().toLowerCase());
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Ошибка. Попробуйте позже.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ background: "#f1f5f9", minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: "20px 16px" }}>
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
          <Link href="/" style={{ fontSize: 26, fontWeight: 800, color: "#0f172a", textDecoration: "none", letterSpacing: "-0.5px" }}>Novex</Link>
        </div>

        <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, padding: 40, boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)" }}>
          {sent ? (
            <div style={{ textAlign: "center" }}>
              <div style={{ width: 56, height: 56, borderRadius: "50%", background: "#f0fdf4", border: "2px solid #bbf7d0", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px", fontSize: 24 }}>
                ✓
              </div>
              <h1 style={{ margin: "0 0 10px", fontSize: 20, fontWeight: 700, color: "#0f172a" }}>Письмо отправлено</h1>
              <p style={{ margin: "0 0 24px", fontSize: 14, color: "#64748b", lineHeight: 1.6 }}>
                Если аккаунт с адресом <b>{email}</b> существует — вы получите письмо со ссылкой для сброса пароля. Проверьте папку «Спам».
              </p>
              <Link href="/login" style={{ fontSize: 14, color: "#0f172a", fontWeight: 600, textDecoration: "none" }}>
                ← Вернуться ко входу
              </Link>
            </div>
          ) : (
            <>
              <h1 style={{ margin: "0 0 6px", fontSize: 20, fontWeight: 700, color: "#0f172a" }}>Сброс пароля</h1>
              <p style={{ margin: "0 0 24px", fontSize: 14, color: "#64748b" }}>
                Введите email — мы пришлём ссылку для создания нового пароля.
              </p>

              <form onSubmit={handleSubmit} style={{ display: "grid", gap: 16 }}>
                <div>
                  <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#334155", marginBottom: 8 }}>Email</label>
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

                {error && (
                  <div style={{ padding: "11px 14px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 13 }}>
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  style={{ width: "100%", height: 52, borderRadius: 12, border: "none", background: "#0f172a", color: "#ffffff", fontSize: 16, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.7 : 1, fontFamily: "inherit", transition: "background 0.15s" }}
                  onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background = "#1e293b"; }}
                  onMouseLeave={(e) => { if (!loading) e.currentTarget.style.background = "#0f172a"; }}
                >
                  {loading ? "Отправляем..." : "Отправить ссылку"}
                </button>
              </form>

              <p style={{ margin: "20px 0 0", fontSize: 14, color: "#64748b", textAlign: "center" }}>
                <Link href="/login" style={{ color: "#0f172a", fontWeight: 600, textDecoration: "none" }}>← Назад ко входу</Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
