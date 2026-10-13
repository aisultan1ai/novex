"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { useAuth } from "@/components/providers/auth-provider";
import { errorMessage } from "@/lib/api/client";
import { resendVerificationEmail } from "@/lib/api/auth";

/**
 * «Подтвердите email» — shown where an unverified customer cannot continue
 * (payment) or is about to hit that wall (order form). Offers to re-send the
 * letter and to re-check once the link was opened (possibly on another device).
 *
 * variant "card":   blocking panel (checkout)
 * variant "banner": compact notice above a form
 */
export default function EmailVerificationNotice({
  variant = "card",
  onVerified,
}: {
  variant?: "card" | "banner";
  onVerified?: () => void;
}) {
  const { currentUser, refreshProfile } = useAuth();
  const t = useTranslations("emailVerify");
  const [sending, setSending] = useState(false);
  const [checking, setChecking] = useState(false);
  const [info, setInfo] = useState<{ tone: "ok" | "warn"; text: string } | null>(null);

  async function handleResend() {
    setSending(true);
    setInfo(null);
    try {
      await resendVerificationEmail();
      setInfo({ tone: "ok", text: t("sent") });
    } catch (err) {
      setInfo({ tone: "warn", text: errorMessage(err, t("sendFailed")) });
    } finally {
      setSending(false);
    }
  }

  async function handleCheck() {
    setChecking(true);
    setInfo(null);
    const profile = await refreshProfile();
    setChecking(false);
    if (profile?.email_verified) {
      onVerified?.();
    } else {
      setInfo({ tone: "warn", text: t("notYet") });
    }
  }

  const email = currentUser?.email ?? "";
  const isCard = variant === "card";

  const btnBase: React.CSSProperties = {
    padding: "10px 16px",
    borderRadius: 10,
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
    whiteSpace: "nowrap",
  };

  return (
    <div
      style={{
        background: isCard ? "#ffffff" : "#F8FAFC",
        border: "1px solid #E2E8EE",
        borderRadius: 16,
        padding: isCard ? "28px" : "16px 18px",
        fontFamily: "Inter Variable, sans-serif",
      }}
    >
      <div style={{ fontSize: isCard ? 18 : 15, fontWeight: 700, color: "#0B2545", marginBottom: 6 }}>
        {t("title")}
      </div>
      <div style={{ fontSize: 14, color: "#5F6E7E", lineHeight: 1.5, marginBottom: 14 }}>
        {t.rich("text", { email, b: (c) => <b style={{ color: "#0B2545" }}>{c}</b> })}
      </div>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={handleCheck}
          disabled={checking}
          style={{ ...btnBase, background: "#0B2545", color: "#ffffff", border: "none", opacity: checking ? 0.7 : 1 }}
        >
          {checking ? t("checking") : t("confirmed")}
        </button>
        <button
          type="button"
          onClick={handleResend}
          disabled={sending}
          style={{ ...btnBase, background: "#ffffff", color: "#0B2545", border: "1px solid #E2E8EE", opacity: sending ? 0.7 : 1 }}
        >
          {sending ? t("sending") : t("resend")}
        </button>
      </div>

      {info && (
        <div style={{ marginTop: 12, fontSize: 13, color: info.tone === "ok" ? "#166534" : "#B45309" }}>{info.text}</div>
      )}
    </div>
  );
}
