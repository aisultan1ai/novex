"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { saveAuthSession } from "@/lib/auth/session";
import { ApiError, changePassword, getProfile, updateProfile } from "@/lib/api/auth";
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
  color: "#111827",
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
  const isMobile = useIsMobile();

  const [profile, setProfile] = useState<ProfileResponse | null>(currentUser);
  const [isFetching, setIsFetching] = useState(!currentUser);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [fullName, setFullName] = useState(currentUser?.full_name ?? "");
  const [phone, setPhone] = useState(currentUser?.phone ?? "");
  const [companyName, setCompanyName] = useState(currentUser?.company_name ?? "");
  const [taxId, setTaxId] = useState(currentUser?.tax_id ?? "");

  // Password modal
  const [showPwModal, setShowPwModal] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [pwSaving, setPwSaving] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSuccess, setPwSuccess] = useState(false);

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
        setTaxId(data.tax_id ?? "");
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
    const taxCleaned = taxId.trim();
    if (taxCleaned && !/^\d{12}$/.test(taxCleaned)) {
      setError("ИИН / БИН должен состоять ровно из 12 цифр.");
      return;
    }
    setIsSaving(true);
    try {
      const updated = await updateProfile({
        full_name: fullName.trim() || null,
        phone: phone.trim() || null,
        company_name: companyName.trim() || null,
        tax_id: taxCleaned || null,
      });
      setProfile(updated);
      saveAuthSession(updated);
      refreshSession();
      setSuccessMsg("Данные сохранены");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось сохранить профиль.");
    } finally {
      setIsSaving(false);
    }
  }

  function openPwModal() {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setPwError(null);
    setPwSuccess(false);
    setShowCurrent(false);
    setShowNew(false);
    setShowPwModal(true);
  }

  async function handleChangePassword(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setPwError(null);
    if (newPassword !== confirmPassword) { setPwError("Новые пароли не совпадают"); return; }
    if (newPassword.length < 8) { setPwError("Минимум 8 символов"); return; }
    setPwSaving(true);
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword });
      setPwSuccess(true);
      setTimeout(() => setShowPwModal(false), 1500);
    } catch (err) {
      setPwError(err instanceof ApiError ? err.detail : "Не удалось изменить пароль.");
    } finally {
      setPwSaving(false);
    }
  }

  if (authLoading || (!isAuthenticated && !authLoading)) return null;

  const dp = profile;
  const initials = dp ? getInitials(dp.full_name, dp.email) : "?";

  return (
    <>
      <div style={{ marginBottom: isMobile ? 20 : 28 }}>
        <h1 style={{ margin: 0, fontSize: isMobile ? 22 : 28, fontWeight: 800, color: "#111827" }}>Профиль</h1>
        <p style={{ margin: "4px 0 0", fontSize: isMobile ? 13 : 14, color: "#64748b" }}>
          Ваши данные и настройки аккаунта
        </p>
      </div>

      {isFetching && !dp ? (
        <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, padding: 32, textAlign: "center", color: "#64748b", fontSize: 14 }}>
          Загружаем профиль…
        </div>
      ) : (
        <div style={{
          display: "flex",
          flexDirection: isMobile ? "column" : "row",
          gap: isMobile ? 12 : 20,
          alignItems: "stretch",
          maxWidth: 900,
        }}>

          {/* ── Main profile card ──────────────────────────────── */}
          <div style={{ flex: 1, minWidth: 0, background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, padding: isMobile ? 20 : 32 }}>
            {/* Avatar + name */}
            <div style={{ display: "flex", alignItems: "center", gap: isMobile ? 14 : 20, marginBottom: isMobile ? 20 : 32 }}>
              <div style={{
                width: isMobile ? 56 : 72,
                height: isMobile ? 56 : 72,
                borderRadius: "50%",
                background: "#111827",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: isMobile ? 22 : 28, fontWeight: 800, color: "#ffffff",
                flexShrink: 0,
              }}>
                {initials}
              </div>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{
                  fontSize: isMobile ? 17 : 22, fontWeight: 700, color: "#111827",
                  marginBottom: 4,
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}>
                  {dp?.full_name || dp?.email || "-"}
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 600, background: "#ede9fe", color: "#5b21b6" }}>
                    {ROLE_LABELS[dp?.role ?? ""] ?? dp?.role}
                  </span>
                  <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 600, background: "#dbeafe", color: "#1e40af" }}>
                    {CUSTOMER_TYPE_LABELS[dp?.customer_type ?? ""] ?? dp?.customer_type}
                  </span>
                  <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 600, background: dp?.is_active ? "#dcfce7" : "#fee2e2", color: dp?.is_active ? "#166534" : "#991b1b" }}>
                    {dp?.is_active ? "Активен" : "Заблокирован"}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 8 }}>
                  ID: <span style={{ fontFamily: "monospace", color: "#475569", fontWeight: 600 }}>#{dp?.user_id}</span>
                  {" · "}
                  {BILLING_LABELS[dp?.billing_mode ?? ""] ?? dp?.billing_mode}
                </div>
              </div>
            </div>

            <hr style={{ border: "none", borderTop: "1px solid #f1f5f9", margin: "0 0 20px" }} />

            <h2 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700, color: "#111827" }}>
              Редактировать данные
            </h2>

            <form onSubmit={handleSubmit}>
              <div style={{
                display: "grid",
                gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr",
                gap: isMobile ? 14 : 20,
                marginBottom: 20,
              }}>
                <div style={{ gridColumn: isMobile ? undefined : "1 / -1" }}>
                  <label style={lbl}>Эл. почта</label>
                  <input style={inpDisabled} value={dp?.email ?? ""} disabled readOnly />
                </div>
                <div>
                  <label style={lbl}>Контактный телефон</label>
                  <input
                    style={inp} value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+7 700 000 0000" inputMode="tel"
                    onFocus={(e) => { e.currentTarget.style.borderColor = "#111827"; e.currentTarget.style.background = "#ffffff"; }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = "#e5e7eb"; e.currentTarget.style.background = "#f8fafc"; }}
                  />
                </div>
                <div>
                  <label style={lbl}>Имя / ФИО</label>
                  <input
                    style={inp} value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Иван Иванов"
                    onFocus={(e) => { e.currentTarget.style.borderColor = "#111827"; e.currentTarget.style.background = "#ffffff"; }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = "#e5e7eb"; e.currentTarget.style.background = "#f8fafc"; }}
                  />
                </div>
                <div>
                  <label style={lbl}>Название компании</label>
                  <input
                    style={inp} value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="ТОО «Компания»"
                    onFocus={(e) => { e.currentTarget.style.borderColor = "#111827"; e.currentTarget.style.background = "#ffffff"; }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = "#e5e7eb"; e.currentTarget.style.background = "#f8fafc"; }}
                  />
                </div>
                <div>
                  <label style={lbl}>ИИН / БИН</label>
                  <input
                    style={inp} value={taxId}
                    onChange={(e) => setTaxId(e.target.value.replace(/\D/g, "").slice(0, 12))}
                    placeholder="12 цифр"
                    inputMode="numeric"
                    onFocus={(e) => { e.currentTarget.style.borderColor = "#111827"; e.currentTarget.style.background = "#ffffff"; }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = "#e5e7eb"; e.currentTarget.style.background = "#f8fafc"; }}
                  />
                </div>
              </div>

              <button
                type="submit" disabled={isSaving}
                style={{
                  background: "#111827", color: "#ffffff", border: "none",
                  borderRadius: 10,
                  padding: isMobile ? "12px 24px" : "12px 32px",
                  fontWeight: 600, fontSize: 15,
                  cursor: isSaving ? "not-allowed" : "pointer",
                  opacity: isSaving ? 0.7 : 1, fontFamily: "inherit",
                  width: isMobile ? "100%" : "auto",
                }}
              >
                {isSaving ? "Сохраняем…" : "Сохранить"}
              </button>
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

          {/* ── Password card ──────────────────────────────────── */}
          <div style={{
            width: isMobile ? "100%" : 240,
            flexShrink: 0,
            background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16,
            padding: isMobile ? 20 : 24,
            display: "flex",
            flexDirection: isMobile ? "row" : "column",
            alignItems: "center",
            textAlign: isMobile ? "left" : "center",
            gap: isMobile ? 14 : 16,
            boxSizing: "border-box",
          }}>
            <div style={{ width: 52, height: 52, borderRadius: 14, background: "#f1f5f9", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#475569" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
            </div>
            <div style={{ flex: isMobile ? 1 : "none", minWidth: 0 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: "#111827", marginBottom: 4 }}>Сменить пароль</div>
              <div style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.5 }}>
                Рекомендуем использовать надёжный пароль
              </div>
            </div>
            <button
              onClick={openPwModal}
              style={{
                width: isMobile ? "auto" : "100%",
                padding: isMobile ? "10px 16px" : "11px 0",
                borderRadius: 10, border: "1px solid #e5e7eb",
                background: "#fff", color: "#111827", fontSize: 14, fontWeight: 600,
                cursor: "pointer", fontFamily: "inherit", transition: "background 0.15s",
                whiteSpace: "nowrap", flexShrink: 0,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "#f8fafc"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "#fff"; }}
            >
              Изменить
            </button>
          </div>
        </div>
      )}

      {/* ── Password modal ──────────────────────────────────────── */}
      {showPwModal && (
        <div
          onClick={(e) => { if (e.target === e.currentTarget) setShowPwModal(false); }}
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
            zIndex: 50, display: "flex",
            alignItems: isMobile ? "flex-end" : "center",
            justifyContent: "center",
            padding: isMobile ? 0 : 16,
          }}
        >
          <div style={{
            background: "#fff",
            borderRadius: isMobile ? "20px 20px 0 0" : 20,
            padding: isMobile ? "24px 20px 32px" : "36px 40px",
            width: isMobile ? "100%" : 420,
            maxWidth: "100%",
            boxSizing: "border-box",
            boxShadow: "0 24px 64px rgba(0,0,0,0.16)",
            maxHeight: isMobile ? "92vh" : "auto",
            overflowY: "auto",
          }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 26 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#111827" }}>Сменить пароль</h2>
                <p style={{ margin: "4px 0 0", fontSize: 13, color: "#94a3b8" }}>Минимум 8 символов</p>
              </div>
              <button
                onClick={() => setShowPwModal(false)}
                style={{ width: 32, height: 32, borderRadius: 8, border: "1px solid #e5e7eb", background: "#fff", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "#64748b", fontSize: 18, fontFamily: "inherit" }}
              >×</button>
            </div>

            {pwSuccess ? (
              <div style={{ padding: "24px 0", textAlign: "center" }}>
                <div style={{ width: 52, height: 52, borderRadius: "50%", background: "#dcfce7", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 14px" }}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                </div>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#111827" }}>Пароль изменён</div>
              </div>
            ) : (
              <form onSubmit={(e) => void handleChangePassword(e)}>
                {/* Current password */}
                <div style={{ marginBottom: 16 }}>
                  <label style={lbl}>Текущий пароль</label>
                  <div style={{ display: "flex", alignItems: "center", border: "1px solid #e5e7eb", borderRadius: 10, overflow: "hidden", background: "#f8fafc" }}>
                    <input
                      type={showCurrent ? "text" : "password"}
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      placeholder="••••••••" required
                      style={{ flex: 1, border: "none", background: "transparent", padding: "11px 14px", fontSize: 14, outline: "none", fontFamily: "inherit", color: "#111827" }}
                    />
                    <button type="button" onClick={() => setShowCurrent(v => !v)}
                      style={{ padding: "0 14px", background: "none", border: "none", cursor: "pointer", color: "#94a3b8", fontSize: 12, fontFamily: "inherit" }}>
                      {showCurrent ? "Скрыть" : "Показать"}
                    </button>
                  </div>
                </div>

                {/* New password */}
                <div style={{ marginBottom: 16 }}>
                  <label style={lbl}>Новый пароль</label>
                  <div style={{ display: "flex", alignItems: "center", border: "1px solid #e5e7eb", borderRadius: 10, overflow: "hidden", background: "#f8fafc" }}>
                    <input
                      type={showNew ? "text" : "password"}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="Минимум 8 символов" required
                      style={{ flex: 1, border: "none", background: "transparent", padding: "11px 14px", fontSize: 14, outline: "none", fontFamily: "inherit", color: "#111827" }}
                    />
                    <button type="button" onClick={() => setShowNew(v => !v)}
                      style={{ padding: "0 14px", background: "none", border: "none", cursor: "pointer", color: "#94a3b8", fontSize: 12, fontFamily: "inherit" }}>
                      {showNew ? "Скрыть" : "Показать"}
                    </button>
                  </div>
                </div>

                {/* Confirm */}
                <div style={{ marginBottom: 22 }}>
                  <label style={lbl}>Повторите новый пароль</label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••" required
                    style={{ ...inp, background: confirmPassword && confirmPassword !== newPassword ? "#fef2f2" : "#f8fafc", borderColor: confirmPassword && confirmPassword !== newPassword ? "#fecaca" : "#e5e7eb" }}
                  />
                  {confirmPassword && confirmPassword !== newPassword && (
                    <div style={{ fontSize: 12, color: "#dc2626", marginTop: 4 }}>Пароли не совпадают</div>
                  )}
                </div>

                {pwError && (
                  <div style={{ marginBottom: 14, padding: "10px 14px", borderRadius: 8, background: "#fef2f2", color: "#b91c1c", fontSize: 13 }}>
                    {pwError}
                  </div>
                )}

                <div style={{ display: "flex", gap: 10 }}>
                  <button
                    type="submit" disabled={pwSaving}
                    style={{ flex: 1, padding: 12, borderRadius: 10, border: "none", background: "#111827", color: "#fff", fontSize: 14, fontWeight: 600, cursor: pwSaving ? "not-allowed" : "pointer", opacity: pwSaving ? 0.6 : 1, fontFamily: "inherit" }}
                  >
                    {pwSaving ? "Сохраняем…" : "Изменить пароль"}
                  </button>
                  <button
                    type="button" onClick={() => setShowPwModal(false)}
                    style={{ padding: "12px 20px", borderRadius: 10, border: "1px solid #e5e7eb", background: "#fff", color: "#475569", fontSize: 14, fontWeight: 500, cursor: "pointer", fontFamily: "inherit" }}
                  >
                    Отмена
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
}
