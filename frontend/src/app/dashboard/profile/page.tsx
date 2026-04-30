"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { getAccessToken, saveAuthSession } from "@/lib/auth/session";
import { ApiError, getProfile, updateProfile } from "@/lib/api/auth";
import type { ProfileResponse } from "@/types/auth";

const BILLING_LABELS: Record<string, string> = {
  prepaid: "Предоплата",
  postpaid: "Постоплата",
};

const CUSTOMER_TYPE_LABELS: Record<string, string> = {
  individual: "Физическое лицо",
  company: "Компания",
};

const ROLE_LABELS: Record<string, string> = {
  customer: "Клиент",
  admin: "Администратор",
  operator: "Оператор",
};

function getInitials(fullName: string | null, email: string): string {
  if (fullName) {
    const parts = fullName.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return parts[0].slice(0, 2).toUpperCase();
  }
  return email.slice(0, 2).toUpperCase();
}

const inp: React.CSSProperties = {
  border: "1px solid #e5e7eb",
  borderRadius: 10,
  padding: "11px 14px",
  fontSize: 14,
  background: "#f8fafc",
  width: "100%",
  boxSizing: "border-box",
  outline: "none",
  fontFamily: "inherit",
  color: "#0f172a",
  transition: "border-color 0.15s, background 0.15s",
};

const inpDisabled: React.CSSProperties = {
  ...inp,
  background: "#f1f5f9",
  color: "#94a3b8",
  cursor: "not-allowed",
};

const lbl: React.CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 600,
  color: "#334155",
  marginBottom: 8,
};

export default function ProfilePage() {
  const { isAuthenticated, isLoading: authLoading, currentUser, refreshSession } = useAuth();
  const router = useRouter();

  const [profile, setProfile] = useState<ProfileResponse | null>(currentUser);
  const [isFetching, setIsFetching] = useState(!currentUser);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [fullName, setFullName] = useState(currentUser?.full_name ?? "");
  const [phone, setPhone] = useState(currentUser?.phone ?? "");
  const [companyName, setCompanyName] = useState(currentUser?.company_name ?? "");

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push("/login");
  }, [isAuthenticated, authLoading, router]);

  useEffect(() => {
    if (!isAuthenticated) return;
    async function fetchProfile() {
      setIsFetching(true);
      try {
        const data = await getProfile();
        setProfile(data);
        setFullName(data.full_name ?? "");
        setPhone(data.phone ?? "");
        setCompanyName(data.company_name ?? "");
      } catch (err) {
        if (!currentUser) setError(err instanceof ApiError ? err.detail : "Не удалось загрузить профиль.");
      } finally {
        setIsFetching(false);
      }
    }
    void fetchProfile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    setIsSaving(true);
    try {
      const updated = await updateProfile({
        full_name: fullName.trim() || null,
        phone: phone.trim() || null,
        company_name: companyName.trim() || null,
      });
      setProfile(updated);
      const token = getAccessToken();
      if (token) {
        saveAuthSession(token, updated);
        refreshSession();
      }
      setSuccessMsg("Данные сохранены");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось сохранить профиль.");
    } finally {
      setIsSaving(false);
    }
  }

  if (authLoading || (!isAuthenticated && !authLoading)) return null;

  const dp = profile;
  const initials = dp ? getInitials(dp.full_name, dp.email) : "?";

  return (
    <>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: "#0f172a" }}>Профиль</h1>
        <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>
          Ваши данные и настройки аккаунта
        </p>
      </div>

      {isFetching && !dp ? (
        <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, padding: 32, textAlign: "center", color: "#64748b", fontSize: 14 }}>
          Загружаем профиль…
        </div>
      ) : (
        <div style={{ maxWidth: 640 }}>
          <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, padding: 32 }}>
            {/* Avatar + name */}
            <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 32 }}>
              <div
                style={{
                  width: 72,
                  height: 72,
                  borderRadius: "50%",
                  background: "#0f172a",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 28,
                  fontWeight: 800,
                  color: "#ffffff",
                  flexShrink: 0,
                }}
              >
                {initials}
              </div>
              <div>
                <div style={{ fontSize: 22, fontWeight: 700, color: "#0f172a", marginBottom: 4 }}>
                  {dp?.full_name || dp?.email || "—"}
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: "#ede9fe", color: "#5b21b6" }}>
                    {ROLE_LABELS[dp?.role ?? ""] ?? dp?.role}
                  </span>
                  <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: "#dbeafe", color: "#1e40af" }}>
                    {CUSTOMER_TYPE_LABELS[dp?.customer_type ?? ""] ?? dp?.customer_type}
                  </span>
                  <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: dp?.is_active ? "#dcfce7" : "#fee2e2", color: dp?.is_active ? "#166534" : "#991b1b" }}>
                    {dp?.is_active ? "Активен" : "Заблокирован"}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 8 }}>
                  ID: <span style={{ fontFamily: "monospace", color: "#475569", fontWeight: 600 }}>#{dp?.user_id}</span>
                  {" · "}
                  {BILLING_LABELS[dp?.billing_mode ?? ""] ?? dp?.billing_mode}
                </div>
              </div>
            </div>

            <hr style={{ border: "none", borderTop: "1px solid #f1f5f9", margin: "0 0 24px" }} />

            <h2 style={{ margin: "0 0 20px", fontSize: 16, fontWeight: 700, color: "#0f172a" }}>
              Редактировать данные
            </h2>

            <form onSubmit={handleSubmit}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
                <div style={{ gridColumn: "1 / -1" }}>
                  <label style={lbl}>Эл. почта</label>
                  <input style={inpDisabled} value={dp?.email ?? ""} disabled readOnly />
                </div>

                <div>
                  <label style={lbl}>Контактный телефон</label>
                  <input
                    style={inp}
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+7 700 000 0000"
                    inputMode="tel"
                    onFocus={(e) => { e.currentTarget.style.borderColor = "#0f172a"; e.currentTarget.style.background = "#ffffff"; }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = "#e5e7eb"; e.currentTarget.style.background = "#f8fafc"; }}
                  />
                </div>

                <div>
                  <label style={lbl}>Имя / ФИО</label>
                  <input
                    style={inp}
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Иван Иванов"
                    onFocus={(e) => { e.currentTarget.style.borderColor = "#0f172a"; e.currentTarget.style.background = "#ffffff"; }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = "#e5e7eb"; e.currentTarget.style.background = "#f8fafc"; }}
                  />
                </div>

                <div>
                  <label style={lbl}>Название компании</label>
                  <input
                    style={inp}
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="ТОО «Компания»"
                    onFocus={(e) => { e.currentTarget.style.borderColor = "#0f172a"; e.currentTarget.style.background = "#ffffff"; }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = "#e5e7eb"; e.currentTarget.style.background = "#f8fafc"; }}
                  />
                </div>
              </div>

              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <button
                  type="submit"
                  disabled={isSaving}
                  style={{ background: "#0f172a", color: "#ffffff", border: "none", borderRadius: 10, padding: "12px 32px", fontWeight: 600, fontSize: 15, cursor: isSaving ? "not-allowed" : "pointer", opacity: isSaving ? 0.7 : 1, fontFamily: "inherit" }}
                >
                  {isSaving ? "Сохраняем…" : "Сохранить"}
                </button>
              </div>
            </form>

            {successMsg && (
              <div style={{ marginTop: 16, padding: "12px 16px", borderRadius: 10, background: "#f0fdf4", border: "1px solid #bbf7d0", color: "#166534", fontSize: 14, fontWeight: 600 }}>
                ✓ {successMsg}
              </div>
            )}

            {error && (
              <div style={{ marginTop: 16, padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 14 }}>
                {error}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
