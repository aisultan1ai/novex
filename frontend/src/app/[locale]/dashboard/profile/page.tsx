"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { saveAuthSession } from "@/lib/auth/session";
import { ApiError, changePassword, getProfile, updateProfile } from "@/lib/api/auth";
import type { ProfileResponse } from "@/types/auth";
import { useRouter } from "@/i18n/navigation";

// Подписи ролей, типов клиента и режимов оплаты - в messages:
// dashboard.profile.{role,customerType,billing}.<value>.

function getInitials(fullName: string | null, email: string): string {
  if (fullName) {
    const parts = fullName.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return parts[0].slice(0, 2).toUpperCase();
  }
  return email.slice(0, 2).toUpperCase();
}

const inp: React.CSSProperties = {
  border: "1px solid #E2E8EE",
  borderRadius: 10,
  padding: "11px 14px",
  fontSize: 14,
  background: "#f8fafc",
  width: "100%",
  boxSizing: "border-box",
  outline: "none",
  fontFamily: "inherit",
  color: "#0E1826",
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
  const t = useTranslations("dashboard.profile");
  // Подпись значения из словаря или само значение, если перевода нет.
  const enumLabel = (group: string, v: string | null | undefined) =>
    v && t.has(`${group}.${v}`) ? t(`${group}.${v}`) : v;
  const { isAuthenticated, isLoading: authLoading, currentUser, refreshSession, refreshProfile } = useAuth();
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
        if (!currentUser) setError(err instanceof ApiError ? err.detail : t("errors.load"));
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
      setError(t("errors.taxId"));
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
      // Keep the in-memory full profile (phone, ИИН/БИН, ...) in sync so the
      // order form prefills the new values without a reload.
      void refreshProfile(updated);
      setSuccessMsg(t("saved"));
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : t("errors.save"));
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
    if (newPassword !== confirmPassword) { setPwError(t("password.mismatchNew")); return; }
    if (newPassword.length < 8) { setPwError(t("password.min")); return; }
    setPwSaving(true);
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword });
      setPwSuccess(true);
      setTimeout(() => setShowPwModal(false), 1500);
    } catch (err) {
      setPwError(err instanceof ApiError ? err.detail : t("password.failed"));
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
        <h1 style={{ margin: 0, fontSize: isMobile ? 22 : 28, fontWeight: 800, color: "#0E1826" }}>{t("title")}</h1>
        <p style={{ margin: "4px 0 0", fontSize: isMobile ? 13 : 14, color: "#64748b" }}>
          {t("subtitle")}
        </p>
      </div>

      {isFetching && !dp ? (
        <div style={{ background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 16, padding: 32, textAlign: "center", color: "#64748b", fontSize: 14 }}>
          {t("loading")}
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
          <div style={{ flex: 1, minWidth: 0, background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 16, padding: isMobile ? 20 : 32 }}>
            {/* Avatar + name */}
            <div style={{ display: "flex", alignItems: "center", gap: isMobile ? 14 : 20, marginBottom: isMobile ? 20 : 32 }}>
              <div style={{
                width: isMobile ? 56 : 72,
                height: isMobile ? 56 : 72,
                borderRadius: "50%",
                background: "#0E1826",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: isMobile ? 22 : 28, fontWeight: 800, color: "#ffffff",
                flexShrink: 0,
              }}>
                {initials}
              </div>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{
                  fontSize: isMobile ? 17 : 22, fontWeight: 700, color: "#0E1826",
                  marginBottom: 4,
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}>
                  {dp?.full_name || dp?.email || "-"}
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 600, background: "#ede9fe", color: "#5b21b6" }}>
                    {enumLabel("role", dp?.role)}
                  </span>
                  <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 600, background: "#E6EEF7", color: "#1e40af" }}>
                    {enumLabel("customerType", dp?.customer_type)}
                  </span>
                  <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 600, background: dp?.is_active ? "#dcfce7" : "#fee2e2", color: dp?.is_active ? "#166534" : "#991b1b" }}>
                    {dp?.is_active ? t("active") : t("blocked")}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 8 }}>
                  ID: <span style={{ fontFamily: "monospace", color: "#475569", fontWeight: 600 }}>#{dp?.user_id}</span>
                  {" · "}
                  {enumLabel("billing", dp?.billing_mode)}
                </div>
              </div>
            </div>

            <hr style={{ border: "none", borderTop: "1px solid #f1f5f9", margin: "0 0 20px" }} />

            <h2 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700, color: "#0E1826" }}>
              {t("editTitle")}
            </h2>

            <form onSubmit={handleSubmit}>
              <div style={{
                display: "grid",
                gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr",
                gap: isMobile ? 14 : 20,
                marginBottom: 20,
              }}>
                <div style={{ gridColumn: isMobile ? undefined : "1 / -1" }}>
                  <label style={lbl}>{t("fields.email")}</label>
                  <input style={inpDisabled} value={dp?.email ?? ""} disabled readOnly />
                </div>
                <div>
                  <label style={lbl}>{t("fields.phone")}</label>
                  <input
                    style={inp} value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+7 700 000 0000" inputMode="tel"
                    onFocus={(e) => { e.currentTarget.style.borderColor = "#0E1826"; e.currentTarget.style.background = "#ffffff"; }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = "#E2E8EE"; e.currentTarget.style.background = "#f8fafc"; }}
                  />
                </div>
                <div>
                  <label style={lbl}>{t("fields.fullName")}</label>
                  <input
                    style={inp} value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder={t("fields.fullNamePlaceholder")}
                    onFocus={(e) => { e.currentTarget.style.borderColor = "#0E1826"; e.currentTarget.style.background = "#ffffff"; }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = "#E2E8EE"; e.currentTarget.style.background = "#f8fafc"; }}
                  />
                </div>
                <div>
                  <label style={lbl}>{t("fields.company")}</label>
                  <input
                    style={inp} value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder={t("fields.companyPlaceholder")}
                    onFocus={(e) => { e.currentTarget.style.borderColor = "#0E1826"; e.currentTarget.style.background = "#ffffff"; }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = "#E2E8EE"; e.currentTarget.style.background = "#f8fafc"; }}
                  />
                </div>
                <div>
                  <label style={lbl}>{t("fields.taxId")}</label>
                  <input
                    style={inp} value={taxId}
                    onChange={(e) => setTaxId(e.target.value.replace(/\D/g, "").slice(0, 12))}
                    placeholder={t("fields.taxIdPlaceholder")}
                    inputMode="numeric"
                    onFocus={(e) => { e.currentTarget.style.borderColor = "#0E1826"; e.currentTarget.style.background = "#ffffff"; }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = "#E2E8EE"; e.currentTarget.style.background = "#f8fafc"; }}
                  />
                </div>
              </div>

              <button
                type="submit" disabled={isSaving}
                style={{
                  background: "#0E1826", color: "#ffffff", border: "none",
                  borderRadius: 10,
                  padding: isMobile ? "12px 24px" : "12px 32px",
                  fontWeight: 600, fontSize: 15,
                  cursor: isSaving ? "not-allowed" : "pointer",
                  opacity: isSaving ? 0.7 : 1, fontFamily: "inherit",
                  width: isMobile ? "100%" : "auto",
                }}
              >
                {isSaving ? t("saving") : t("save")}
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
            background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 16,
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
              <div style={{ fontSize: 15, fontWeight: 700, color: "#0E1826", marginBottom: 4 }}>{t("password.title")}</div>
              <div style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.5 }}>
                {t("password.hint")}
              </div>
            </div>
            <button
              onClick={openPwModal}
              style={{
                width: isMobile ? "auto" : "100%",
                padding: isMobile ? "10px 16px" : "11px 0",
                borderRadius: 10, border: "1px solid #E2E8EE",
                background: "#fff", color: "#0E1826", fontSize: 14, fontWeight: 600,
                cursor: "pointer", fontFamily: "inherit", transition: "background 0.15s",
                whiteSpace: "nowrap", flexShrink: 0,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "#f8fafc"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "#fff"; }}
            >
              {t("password.open")}
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
                <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#0E1826" }}>{t("password.title")}</h2>
                <p style={{ margin: "4px 0 0", fontSize: 13, color: "#94a3b8" }}>{t("password.min")}</p>
              </div>
              <button
                onClick={() => setShowPwModal(false)}
                style={{ width: 32, height: 32, borderRadius: 8, border: "1px solid #E2E8EE", background: "#fff", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "#64748b", fontSize: 18, fontFamily: "inherit" }}
              >×</button>
            </div>

            {pwSuccess ? (
              <div style={{ padding: "24px 0", textAlign: "center" }}>
                <div style={{ width: 52, height: 52, borderRadius: "50%", background: "#dcfce7", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 14px" }}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                </div>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#0E1826" }}>{t("password.done")}</div>
              </div>
            ) : (
              <form onSubmit={(e) => void handleChangePassword(e)}>
                {/* Current password */}
                <div style={{ marginBottom: 16 }}>
                  <label style={lbl}>{t("password.current")}</label>
                  <div style={{ display: "flex", alignItems: "center", border: "1px solid #E2E8EE", borderRadius: 10, overflow: "hidden", background: "#f8fafc" }}>
                    <input
                      type={showCurrent ? "text" : "password"}
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      placeholder="••••••••" required
                      style={{ flex: 1, border: "none", background: "transparent", padding: "11px 14px", fontSize: 14, outline: "none", fontFamily: "inherit", color: "#0E1826" }}
                    />
                    <button type="button" onClick={() => setShowCurrent(v => !v)}
                      style={{ padding: "0 14px", background: "none", border: "none", cursor: "pointer", color: "#94a3b8", fontSize: 12, fontFamily: "inherit" }}>
                      {showCurrent ? t("password.hide") : t("password.show")}
                    </button>
                  </div>
                </div>

                {/* New password */}
                <div style={{ marginBottom: 16 }}>
                  <label style={lbl}>{t("password.new")}</label>
                  <div style={{ display: "flex", alignItems: "center", border: "1px solid #E2E8EE", borderRadius: 10, overflow: "hidden", background: "#f8fafc" }}>
                    <input
                      type={showNew ? "text" : "password"}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder={t("password.min")} required
                      style={{ flex: 1, border: "none", background: "transparent", padding: "11px 14px", fontSize: 14, outline: "none", fontFamily: "inherit", color: "#0E1826" }}
                    />
                    <button type="button" onClick={() => setShowNew(v => !v)}
                      style={{ padding: "0 14px", background: "none", border: "none", cursor: "pointer", color: "#94a3b8", fontSize: 12, fontFamily: "inherit" }}>
                      {showNew ? t("password.hide") : t("password.show")}
                    </button>
                  </div>
                </div>

                {/* Confirm */}
                <div style={{ marginBottom: 22 }}>
                  <label style={lbl}>{t("password.repeat")}</label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••" required
                    style={{ ...inp, background: confirmPassword && confirmPassword !== newPassword ? "#fef2f2" : "#f8fafc", borderColor: confirmPassword && confirmPassword !== newPassword ? "#fecaca" : "#E2E8EE" }}
                  />
                  {confirmPassword && confirmPassword !== newPassword && (
                    <div style={{ fontSize: 12, color: "#dc2626", marginTop: 4 }}>{t("password.mismatch")}</div>
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
                    style={{ flex: 1, padding: 12, borderRadius: 10, border: "none", background: "#0E1826", color: "#fff", fontSize: 14, fontWeight: 600, cursor: pwSaving ? "not-allowed" : "pointer", opacity: pwSaving ? 0.6 : 1, fontFamily: "inherit" }}
                  >
                    {pwSaving ? t("saving") : t("password.submit")}
                  </button>
                  <button
                    type="button" onClick={() => setShowPwModal(false)}
                    style={{ padding: "12px 20px", borderRadius: 10, border: "1px solid #E2E8EE", background: "#fff", color: "#475569", fontSize: 14, fontWeight: 500, cursor: "pointer", fontFamily: "inherit" }}
                  >
                    {t("cancel")}
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
