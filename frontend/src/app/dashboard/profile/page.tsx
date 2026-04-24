"use client";

import type { CSSProperties, FormEvent } from "react";
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

const cardStyle: CSSProperties = {
  border: "1px solid #e5e7eb",
  borderRadius: 16,
  background: "#ffffff",
  boxShadow: "0 2px 12px rgba(15, 23, 42, 0.05)",
};

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "11px 14px",
  borderRadius: 10,
  border: "1px solid #cbd5e1",
  fontSize: 14,
  outline: "none",
  boxSizing: "border-box",
  color: "#0f172a",
  background: "#ffffff",
  fontFamily: "inherit",
};

const inputDisabledStyle: CSSProperties = {
  ...inputStyle,
  background: "#f8fafc",
  color: "#94a3b8",
  cursor: "not-allowed",
};

const labelStyle: CSSProperties = {
  display: "block",
  fontSize: 12,
  fontWeight: 600,
  marginBottom: 6,
  color: "#475569",
  textTransform: "uppercase",
  letterSpacing: "0.04em",
};

export default function ProfilePage() {
  const { isAuthenticated, isLoading: authLoading, currentUser, refreshSession } = useAuth();
  const router = useRouter();

  // Initialize immediately from cached currentUser — no loading flicker
  const [profile, setProfile] = useState<ProfileResponse | null>(currentUser);
  const [isFetching, setIsFetching] = useState(!currentUser);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [fullName, setFullName] = useState(currentUser?.full_name ?? "");
  const [phone, setPhone] = useState(currentUser?.phone ?? "");
  const [companyName, setCompanyName] = useState(currentUser?.company_name ?? "");

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, authLoading, router]);

  // Refresh from server to get the latest data
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
        if (!currentUser) {
          setError(
            err instanceof ApiError ? err.detail : "Не удалось загрузить профиль.",
          );
        }
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

      // Sync updated profile into localStorage so the sidebar reflects it immediately
      const token = getAccessToken();
      if (token) {
        saveAuthSession(token, updated);
        refreshSession();
      }

      setSuccessMsg("Профиль успешно обновлён.");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail : "Не удалось сохранить профиль.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  if (authLoading || (!isAuthenticated && !authLoading)) return null;

  const displayProfile = profile;
  const initials = displayProfile
    ? getInitials(displayProfile.full_name, displayProfile.email)
    : "?";

  return (
    <>
      {/* Page header */}
      <div style={{ marginBottom: 28 }}>
        <h1
          style={{ margin: 0, fontSize: 26, fontWeight: 800, color: "#0f172a" }}
        >
          Профиль
        </h1>
        <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>
          Ваши данные и настройки аккаунта
        </p>
      </div>

      {isFetching && !displayProfile ? (
        <div
          style={{
            ...cardStyle,
            padding: 32,
            textAlign: "center",
            color: "#64748b",
            fontSize: 14,
          }}
        >
          Загружаем профиль…
        </div>
      ) : (
        <>
          {/* Identity card */}
          <div style={{ ...cardStyle, marginBottom: 20, padding: "24px 28px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
              {/* Avatar */}
              <div
                style={{
                  width: 64,
                  height: 64,
                  borderRadius: "50%",
                  background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 22,
                  fontWeight: 700,
                  color: "#fff",
                  flexShrink: 0,
                  letterSpacing: 1,
                }}
              >
                {initials}
              </div>

              {/* Name + badges */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 20,
                    fontWeight: 700,
                    color: "#0f172a",
                    marginBottom: 4,
                  }}
                >
                  {displayProfile?.full_name || displayProfile?.email || "—"}
                </div>
                {displayProfile?.full_name && (
                  <div
                    style={{ fontSize: 14, color: "#64748b", marginBottom: 10 }}
                  >
                    {displayProfile.email}
                  </div>
                )}

                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <span
                    style={{
                      display: "inline-block",
                      padding: "3px 10px",
                      borderRadius: 999,
                      fontSize: 12,
                      fontWeight: 600,
                      background: "#ede9fe",
                      color: "#5b21b6",
                    }}
                  >
                    {ROLE_LABELS[displayProfile?.role ?? ""] ?? displayProfile?.role}
                  </span>
                  <span
                    style={{
                      display: "inline-block",
                      padding: "3px 10px",
                      borderRadius: 999,
                      fontSize: 12,
                      fontWeight: 600,
                      background: "#dbeafe",
                      color: "#1e40af",
                    }}
                  >
                    {CUSTOMER_TYPE_LABELS[displayProfile?.customer_type ?? ""] ?? displayProfile?.customer_type}
                  </span>
                  <span
                    style={{
                      display: "inline-block",
                      padding: "3px 10px",
                      borderRadius: 999,
                      fontSize: 12,
                      fontWeight: 600,
                      background: displayProfile?.is_active ? "#dcfce7" : "#fee2e2",
                      color: displayProfile?.is_active ? "#166534" : "#991b1b",
                    }}
                  >
                    {displayProfile?.is_active ? "Активен" : "Заблокирован"}
                  </span>
                </div>
              </div>

              {/* Meta info */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                  alignItems: "flex-end",
                  flexShrink: 0,
                }}
              >
                <div style={{ fontSize: 12, color: "#94a3b8" }}>
                  ID:{" "}
                  <span
                    style={{
                      fontFamily: "monospace",
                      color: "#475569",
                      fontWeight: 600,
                    }}
                  >
                    #{displayProfile?.user_id}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: "#94a3b8" }}>
                  Оплата:{" "}
                  <span style={{ color: "#475569", fontWeight: 600 }}>
                    {BILLING_LABELS[displayProfile?.billing_mode ?? ""] ?? displayProfile?.billing_mode}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Edit form */}
          <div style={{ ...cardStyle, padding: "24px 28px" }}>
            <h2
              style={{
                margin: "0 0 20px",
                fontSize: 16,
                fontWeight: 700,
                color: "#0f172a",
              }}
            >
              Редактировать данные
            </h2>

            <form onSubmit={handleSubmit}>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, 1fr)",
                  gap: 16,
                  marginBottom: 20,
                }}
              >
                <div>
                  <label style={labelStyle}>Email</label>
                  <input
                    style={inputDisabledStyle}
                    value={displayProfile?.email ?? ""}
                    disabled
                    readOnly
                  />
                </div>

                <div>
                  <label style={labelStyle}>Имя / ФИО</label>
                  <input
                    style={inputStyle}
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Иван Иванов"
                  />
                </div>

                <div>
                  <label style={labelStyle}>Телефон</label>
                  <input
                    style={inputStyle}
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+7 700 000 0000"
                    inputMode="tel"
                  />
                </div>

                <div>
                  <label style={labelStyle}>Название компании</label>
                  <input
                    style={inputStyle}
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="ТОО «Компания»"
                  />
                </div>
              </div>

              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <button
                  type="submit"
                  disabled={isSaving}
                  style={{
                    background: "#0f172a",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: 10,
                    padding: "11px 24px",
                    fontSize: 14,
                    fontWeight: 600,
                    cursor: isSaving ? "not-allowed" : "pointer",
                    opacity: isSaving ? 0.7 : 1,
                    fontFamily: "inherit",
                  }}
                >
                  {isSaving ? "Сохраняем…" : "Сохранить"}
                </button>

                {successMsg && (
                  <span
                    style={{ color: "#166534", fontSize: 14, fontWeight: 500 }}
                  >
                    ✓ {successMsg}
                  </span>
                )}
              </div>
            </form>

            {error && (
              <div
                style={{
                  marginTop: 16,
                  padding: "12px 16px",
                  borderRadius: 10,
                  background: "#fef2f2",
                  color: "#b91c1c",
                  fontSize: 14,
                  border: "1px solid #fecaca",
                }}
              >
                {error}
              </div>
            )}
          </div>
        </>
      )}
    </>
  );
}
