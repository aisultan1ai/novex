"use client";

import type { CSSProperties, FormEvent } from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { ApiError, getProfile, updateProfile } from "@/lib/api/auth";
import type { ProfileResponse } from "@/types/auth";

const cardStyle: CSSProperties = {
  border: "1px solid #e5e7eb",
  borderRadius: 16,
  padding: 28,
  background: "#ffffff",
  boxShadow: "0 4px 16px rgba(15, 23, 42, 0.05)",
};

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "12px 14px",
  borderRadius: 12,
  border: "1px solid #cbd5e1",
  fontSize: 14,
  outline: "none",
  boxSizing: "border-box",
  color: "#0f172a",
  background: "#ffffff",
};

const inputDisabledStyle: CSSProperties = {
  ...inputStyle,
  background: "#f8fafc",
  color: "#94a3b8",
  cursor: "not-allowed",
};

const labelStyle: CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 600,
  marginBottom: 8,
  color: "#334155",
};

const buttonPrimary: CSSProperties = {
  background: "#0f172a",
  color: "#ffffff",
  border: "none",
  borderRadius: 12,
  padding: "12px 20px",
  fontSize: 14,
  fontWeight: 600,
  cursor: "pointer",
};

const BILLING_LABELS: Record<string, string> = {
  prepaid: "Предоплата (физлицо)",
  postpaid: "Постоплата (юрлицо)",
};

const CUSTOMER_TYPE_LABELS: Record<string, string> = {
  individual: "Физическое лицо",
  company: "Компания",
};

export default function ProfilePage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();

  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [companyName, setCompanyName] = useState("");

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, authLoading, router]);

  useEffect(() => {
    if (!isAuthenticated) return;

    async function fetchProfile() {
      try {
        const data = await getProfile();
        setProfile(data);
        setFullName(data.full_name ?? "");
        setPhone(data.phone ?? "");
        setCompanyName(data.company_name ?? "");
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.detail);
        } else {
          setError("Не удалось загрузить профиль.");
        }
      } finally {
        setIsLoading(false);
      }
    }

    fetchProfile();
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
      setSuccessMsg("Профиль успешно обновлён.");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Не удалось сохранить профиль.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  if (authLoading || (!isAuthenticated && !authLoading)) return null;

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: "#0f172a" }}>
          Профиль
        </h1>
        <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>
          Ваши данные и настройки аккаунта
        </p>
      </div>

      {isLoading ? (
        <div style={{ ...cardStyle, color: "#64748b" }}>Загружаем профиль…</div>
      ) : (
        <>
          {/* Информационный блок */}
          <div style={{ ...cardStyle, marginBottom: 20 }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: 20,
              }}
            >
              <div>
                <div style={{ fontSize: 12, color: "#64748b", marginBottom: 4 }}>
                  Email
                </div>
                <div style={{ fontWeight: 600, fontSize: 15 }}>
                  {profile?.email}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: "#64748b", marginBottom: 4 }}>
                  Тип клиента
                </div>
                <div style={{ fontWeight: 600, fontSize: 15 }}>
                  {CUSTOMER_TYPE_LABELS[profile?.customer_type ?? ""] ?? profile?.customer_type}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: "#64748b", marginBottom: 4 }}>
                  Режим оплаты
                </div>
                <div style={{ fontWeight: 600, fontSize: 15 }}>
                  {BILLING_LABELS[profile?.billing_mode ?? ""] ?? profile?.billing_mode}
                </div>
              </div>
            </div>
          </div>

          {/* Форма редактирования */}
          <div style={cardStyle}>
            <h2 style={{ margin: "0 0 20px", fontSize: 18, fontWeight: 700 }}>
              Редактировать данные
            </h2>

            <form onSubmit={handleSubmit}>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, 1fr)",
                  gap: 16,
                  marginBottom: 16,
                }}
              >
                <div>
                  <label style={labelStyle}>Email (изменить нельзя)</label>
                  <input
                    style={inputDisabledStyle}
                    value={profile?.email ?? ""}
                    disabled
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
                  <label style={labelStyle}>Название компании (если есть)</label>
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
                  style={{
                    ...buttonPrimary,
                    opacity: isSaving ? 0.7 : 1,
                    cursor: isSaving ? "not-allowed" : "pointer",
                  }}
                  disabled={isSaving}
                >
                  {isSaving ? "Сохраняем…" : "Сохранить"}
                </button>

                {successMsg && (
                  <span style={{ color: "#166534", fontSize: 14, fontWeight: 500 }}>
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
                  borderRadius: 12,
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
