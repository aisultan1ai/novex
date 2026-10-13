"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { ApiError } from "@/lib/api/client";
import {
  submitPartnerApplication,
  type PartnerIntegrationType,
} from "@/lib/api/partners";

interface FormState {
  company_name: string;
  contact_name: string;
  phone: string;
  email: string;
  cities: string;
  integration_type: PartnerIntegrationType;
  comment: string;
  consent: boolean;
}

const EMPTY: FormState = {
  company_name: "",
  contact_name: "",
  phone: "",
  email: "",
  cities: "",
  integration_type: "unsure",
  comment: "",
  consent: false,
};

const BENEFITS = [
  {
    title: "benefits.flow.title",
    body: "benefits.flow.body",
  },
  {
    title: "benefits.integration.title",
    body: "benefits.integration.body",
  },
  {
    title: "benefits.settlements.title",
    body: "benefits.settlements.body",
  },
  {
    title: "benefits.fullCycle.title",
    body: "benefits.fullCycle.body",
  },
];

const STEPS = [
  { n: 1, title: "steps.s1.title", body: "steps.s1.body" },
  { n: 2, title: "steps.s2.title", body: "steps.s2.body" },
  { n: 3, title: "steps.s3.title", body: "steps.s3.body" },
  { n: 4, title: "steps.s4.title", body: "steps.s4.body" },
  { n: 5, title: "steps.s5.title", body: "steps.s5.body" },
];

export default function PartnersPage() {
  const isMobile = useIsMobile();
  const t = useTranslations("partners");
  const [form, setForm] = useState<FormState>(EMPTY);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  function upd<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): string | null {
    if (form.company_name.trim().length < 2) return t("errors.company");
    if (form.contact_name.trim().length < 2) return t("errors.contact");
    const digits = form.phone.replace(/\D/g, "");
    if (digits.length < 10) return t("errors.phone");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) return t("errors.email");
    if (!form.consent) return t("errors.consent");
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const err = validate();
    if (err) { setError(err); return; }
    setSubmitting(true);
    try {
      await submitPartnerApplication({
        company_name: form.company_name.trim(),
        contact_name: form.contact_name.trim(),
        phone: form.phone.trim(),
        email: form.email.trim(),
        cities: form.cities.trim() || null,
        integration_type: form.integration_type,
        comment: form.comment.trim() || null,
        consent: form.consent,
      });
      setSubmitted(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("errors.failed"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Navbar />
      <main style={{ minHeight: "calc(100vh - 64px)", background: "#FAFAFA" }}>
        {/* Hero */}
        <section style={{ padding: isMobile ? "48px 20px" : "72px 48px", background: "#FFFFFF", borderBottom: "1px solid #E2E8EE" }}>
          <div style={{ maxWidth: 900, margin: "0 auto", textAlign: "center" }}>
            <div
              style={{
                font: "500 13px/1 Inter Variable, sans-serif",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "#0B2545",
                marginBottom: 16,
              }}
            >
              {t("eyebrow")}
            </div>
            <h1 style={{ font: `800 ${isMobile ? 32 : 44}px/1.15 'Space Grotesk Variable', 'Inter Variable', sans-serif`, letterSpacing: "-0.02em", margin: "0 0 16px", color: "#0E1826" }}>
              {t("title")}
            </h1>
            <p style={{ font: "400 17px/1.55 Inter Variable, sans-serif", color: "#5F6E7E", margin: "0 0 8px" }}>
              {t("lead1")}
            </p>
            <p style={{ font: "400 17px/1.55 Inter Variable, sans-serif", color: "#5F6E7E", margin: 0 }}>
              {t("lead2")}
            </p>
          </div>
        </section>

        {/* Benefits */}
        <section style={{ padding: isMobile ? "48px 20px" : "64px 48px" }}>
          <div style={{ maxWidth: 1100, margin: "0 auto" }}>
            <h2 style={{ font: `700 ${isMobile ? 24 : 30}px/1.2 'Space Grotesk Variable', 'Inter Variable', sans-serif`, letterSpacing: "-0.01em", margin: "0 0 32px", color: "#0E1826", textAlign: "center" }}>
              {t("benefitsTitle")}
            </h2>
            <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(2, minmax(0, 1fr))", gap: 16 }}>
              {BENEFITS.map((b) => (
                <div key={b.title} style={{ background: "#FFFFFF", border: "1px solid #E2E8EE", borderRadius: 16, padding: "20px 22px" }}>
                  <div style={{ font: "700 16px/1.3 Inter Variable, sans-serif", color: "#0E1826", marginBottom: 8 }}>{t(b.title)}</div>
                  <p style={{ font: "400 14px/1.55 Inter Variable, sans-serif", color: "#5F6E7E", margin: 0 }}>{t(b.body)}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section style={{ padding: isMobile ? "48px 20px" : "64px 48px", background: "#FFFFFF", borderTop: "1px solid #E2E8EE", borderBottom: "1px solid #E2E8EE" }}>
          <div style={{ maxWidth: 1100, margin: "0 auto" }}>
            <h2 style={{ font: `700 ${isMobile ? 24 : 30}px/1.2 'Space Grotesk Variable', 'Inter Variable', sans-serif`, letterSpacing: "-0.01em", margin: "0 0 32px", color: "#0E1826", textAlign: "center" }}>
              {t("howTitle")}
            </h2>
            <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(5, minmax(0, 1fr))", gap: 12 }}>
              {STEPS.map((s) => (
                <div key={s.n} style={{ background: "#FAFAFA", border: "1px solid #E2E8EE", borderRadius: 14, padding: "18px 18px" }}>
                  <div style={{ width: 32, height: 32, borderRadius: "50%", background: "#0B2545", color: "#FFFFFF", display: "flex", alignItems: "center", justifyContent: "center", font: "700 14px/1 Inter Variable, sans-serif", marginBottom: 10 }}>
                    {s.n}
                  </div>
                  <div style={{ font: "700 14px/1.3 Inter Variable, sans-serif", color: "#0E1826", marginBottom: 6 }}>{t(s.title)}</div>
                  <p style={{ font: "400 13px/1.5 Inter Variable, sans-serif", color: "#5F6E7E", margin: 0 }}>{t(s.body)}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Form */}
        <section id="apply" style={{ padding: isMobile ? "48px 20px" : "64px 48px", background: "#FFFFFF", borderTop: "1px solid #E2E8EE" }}>
          <div style={{ maxWidth: 640, margin: "0 auto" }}>
            <h2 style={{ font: `700 ${isMobile ? 24 : 30}px/1.2 'Space Grotesk Variable', 'Inter Variable', sans-serif`, letterSpacing: "-0.01em", margin: "0 0 8px", color: "#0E1826", textAlign: "center" }}>
              {t("formTitle")}
            </h2>
            <p style={{ font: "400 15px/1.55 Inter Variable, sans-serif", color: "#5F6E7E", margin: "0 0 28px", textAlign: "center" }}>
              {t("formLead")}
            </p>

            {submitted ? (
              <div style={{ background: "#ECFDF5", border: "1px solid #A7F3D0", borderRadius: 16, padding: "24px 28px", textAlign: "center" }}>
                <div style={{ width: 48, height: 48, borderRadius: "50%", background: "#10B981", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 12px" }}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                <div style={{ font: "700 18px/1.3 Inter Variable, sans-serif", color: "#065F46", marginBottom: 6 }}>{t("sentTitle")}</div>
                <p style={{ font: "400 14px/1.55 Inter Variable, sans-serif", color: "#047857", margin: 0 }}>
                  {t("sentText")}
                </p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <Field label={t("fields.company")} value={form.company_name} onChange={(v) => upd("company_name", v)} required disabled={submitting} />
                <Field label={t("fields.contact")} value={form.contact_name} onChange={(v) => upd("contact_name", v)} required disabled={submitting} />
                <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: 14 }}>
                  <Field label={t("fields.phone")} value={form.phone} onChange={(v) => upd("phone", v)} placeholder="+7 700 000 00 00" required disabled={submitting} type="tel" />
                  <Field label="Email *" value={form.email} onChange={(v) => upd("email", v)} placeholder="info@company.kz" required disabled={submitting} type="email" />
                </div>
                <Field label={t("fields.cities")} value={form.cities} onChange={(v) => upd("cities", v)} disabled={submitting} />

                <div>
                  <label style={{ display: "block", font: "600 13px/1 Inter Variable, sans-serif", color: "#0E1826", marginBottom: 8 }}>
                    {t("fields.integration")}
                  </label>
                  <div style={{ display: "grid", gap: 8 }}>
                    {[
                      { key: "api", label: t("fields.integrationApi") },
                      { key: "unsure", label: t("fields.integrationUnsure") },
                    ].map((opt) => (
                      <label key={opt.key} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", border: form.integration_type === opt.key ? "1px solid #0B2545" : "1px solid #E2E8EE", borderRadius: 10, background: form.integration_type === opt.key ? "#F1F5F9" : "#FFFFFF", cursor: submitting ? "not-allowed" : "pointer", transition: "all 0.15s" }}>
                        <input
                          type="radio"
                          name="integration_type"
                          value={opt.key}
                          checked={form.integration_type === opt.key}
                          onChange={() => upd("integration_type", opt.key as PartnerIntegrationType)}
                          disabled={submitting}
                          style={{ accentColor: "#0B2545" }}
                        />
                        <span style={{ font: "400 14px/1.4 Inter Variable, sans-serif", color: "#0E1826" }}>{opt.label}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div>
                  <label style={{ display: "block", font: "600 13px/1 Inter Variable, sans-serif", color: "#0E1826", marginBottom: 6 }}>
                    {t("fields.comment")}
                  </label>
                  <textarea
                    value={form.comment}
                    onChange={(e) => upd("comment", e.target.value)}
                    rows={4}
                    maxLength={2000}
                    placeholder={t("fields.commentPlaceholder")}
                    disabled={submitting}
                    style={{ width: "100%", padding: "10px 12px", border: "1px solid #E2E8EE", borderRadius: 10, font: "400 14px/1.5 Inter Variable, sans-serif", color: "#0E1826", background: "#FFFFFF", outline: "none", resize: "vertical", boxSizing: "border-box" }}
                  />
                </div>

                <label style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "4px 0" }}>
                  <input
                    type="checkbox"
                    checked={form.consent}
                    onChange={(e) => upd("consent", e.target.checked)}
                    disabled={submitting}
                    style={{ marginTop: 3, accentColor: "#0B2545" }}
                  />
                  <span style={{ font: "400 13px/1.5 Inter Variable, sans-serif", color: "#5F6E7E" }}>
                    {t("fields.consent")}
                  </span>
                </label>

                {error && (
                  <div style={{ padding: "12px 14px", background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 10, font: "400 13px/1.5 Inter Variable, sans-serif", color: "#B91C1C" }}>
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={submitting}
                  style={{ marginTop: 4, padding: "12px 24px", background: "#0B2545", color: "#FFFFFF", border: "none", borderRadius: 10, font: "600 15px/1 Inter Variable, sans-serif", cursor: submitting ? "not-allowed" : "pointer", opacity: submitting ? 0.7 : 1, transition: "background 0.15s" }}
                >
                  {submitting ? t("sending") : t("submit")}
                </button>
              </form>
            )}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}

function Field({
  label, value, onChange, placeholder, required, disabled, type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  type?: string;
}) {
  return (
    <div>
      <label style={{ display: "block", font: "600 13px/1 Inter Variable, sans-serif", color: "#0E1826", marginBottom: 6 }}>
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        style={{ width: "100%", padding: "10px 12px", border: "1px solid #E2E8EE", borderRadius: 10, font: "400 14px/1 Inter Variable, sans-serif", color: "#0E1826", background: "#FFFFFF", outline: "none", boxSizing: "border-box" }}
      />
    </div>
  );
}
