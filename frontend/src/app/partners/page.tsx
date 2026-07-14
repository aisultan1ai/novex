"use client";

import { useState } from "react";
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
    title: "Поток клиентов без затрат на маркетинг",
    body: "Novex приводит новых отправителей ежедневно - вы получаете заказы, не тратя бюджет на рекламу.",
  },
  {
    title: "Готовая интеграция и автоматизация",
    body: "Есть API - подключаем автоматически. Нет API - принимаем заказы через личный кабинет.",
  },
  {
    title: "Прозрачные взаиморасчёты",
    body: "Комиссия фиксирована и прописана в договоре. Отчёты по заказам - в кабинете перевозчика.",
  },
  {
    title: "Полный цикл под ключ",
    body: "Оплата от клиента, оформление накладной, трекинг, поддержка - всё берёт на себя Novex.",
  },
];

const STEPS = [
  { n: 1, title: "Расчёт", body: "Клиент вводит маршрут и габариты - наш калькулятор показывает вашу цену наряду с другими перевозчиками." },
  { n: 2, title: "Оформление", body: "Клиент выбирает вас, оплачивает заказ на Novex, заполняет отправителя и получателя." },
  { n: 3, title: "Передача", body: "Novex отправляет вам заказ через API (или через кабинет вручную), вы получаете накладную." },
  { n: 4, title: "Доставка и трекинг", body: "Вы обновляете статусы через API или кабинет - клиент видит движение в реальном времени." },
  { n: 5, title: "Взаиморасчёты", body: "Novex начисляет ваш платёж за вычетом комиссии по завершённым доставкам." },
];

export default function PartnersPage() {
  const isMobile = useIsMobile();
  const [form, setForm] = useState<FormState>(EMPTY);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  function upd<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): string | null {
    if (form.company_name.trim().length < 2) return "Укажите название компании.";
    if (form.contact_name.trim().length < 2) return "Укажите ФИО контактного лица.";
    const digits = form.phone.replace(/\D/g, "");
    if (digits.length < 10) return "Проверьте номер телефона.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) return "Проверьте email.";
    if (!form.consent) return "Требуется согласие на обработку персональных данных.";
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
      setError(e instanceof ApiError ? e.detail : "Не удалось отправить заявку. Попробуйте позже.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Navbar />
      <main style={{ minHeight: "calc(100vh - 64px)", background: "#FAFAFA" }}>
        {/* Hero */}
        <section style={{ padding: isMobile ? "48px 20px" : "72px 48px", background: "#FFFFFF", borderBottom: "1px solid #E5E7EB" }}>
          <div style={{ maxWidth: 900, margin: "0 auto", textAlign: "center" }}>
            <span style={{ display: "inline-block", padding: "6px 14px", borderRadius: 999, background: "#EFF6FF", color: "#1D4ED8", fontSize: 13, fontWeight: 600, marginBottom: 16 }}>
              Для курьерских служб
            </span>
            <h1 style={{ font: `800 ${isMobile ? 32 : 44}px/1.15 Inter Variable, sans-serif`, letterSpacing: "-0.02em", margin: "0 0 16px", color: "#111827" }}>
              Станьте партнёром Novex
            </h1>
            <p style={{ font: "400 17px/1.55 Inter Variable, sans-serif", color: "#6B7280", margin: "0 0 8px" }}>
              Мы агрегируем спрос на доставку по Казахстану и передаём заказы курьерским службам.
            </p>
            <p style={{ font: "400 17px/1.55 Inter Variable, sans-serif", color: "#6B7280", margin: 0 }}>
              Подключитесь - и получайте поток заказов без затрат на маркетинг.
            </p>
          </div>
        </section>

        {/* Benefits */}
        <section style={{ padding: isMobile ? "48px 20px" : "64px 48px" }}>
          <div style={{ maxWidth: 1100, margin: "0 auto" }}>
            <h2 style={{ font: `700 ${isMobile ? 24 : 30}px/1.2 Inter Variable, sans-serif`, letterSpacing: "-0.01em", margin: "0 0 32px", color: "#111827", textAlign: "center" }}>
              Что мы даём
            </h2>
            <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(2, minmax(0, 1fr))", gap: 16 }}>
              {BENEFITS.map((b) => (
                <div key={b.title} style={{ background: "#FFFFFF", border: "1px solid #E5E7EB", borderRadius: 16, padding: "20px 22px" }}>
                  <div style={{ font: "700 16px/1.3 Inter Variable, sans-serif", color: "#111827", marginBottom: 8 }}>{b.title}</div>
                  <p style={{ font: "400 14px/1.55 Inter Variable, sans-serif", color: "#6B7280", margin: 0 }}>{b.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section style={{ padding: isMobile ? "48px 20px" : "64px 48px", background: "#FFFFFF", borderTop: "1px solid #E5E7EB", borderBottom: "1px solid #E5E7EB" }}>
          <div style={{ maxWidth: 1100, margin: "0 auto" }}>
            <h2 style={{ font: `700 ${isMobile ? 24 : 30}px/1.2 Inter Variable, sans-serif`, letterSpacing: "-0.01em", margin: "0 0 32px", color: "#111827", textAlign: "center" }}>
              Как это работает
            </h2>
            <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(5, minmax(0, 1fr))", gap: 12 }}>
              {STEPS.map((s) => (
                <div key={s.n} style={{ background: "#FAFAFA", border: "1px solid #E5E7EB", borderRadius: 14, padding: "18px 18px" }}>
                  <div style={{ width: 32, height: 32, borderRadius: "50%", background: "#2563EB", color: "#FFFFFF", display: "flex", alignItems: "center", justifyContent: "center", font: "700 14px/1 Inter Variable, sans-serif", marginBottom: 10 }}>
                    {s.n}
                  </div>
                  <div style={{ font: "700 14px/1.3 Inter Variable, sans-serif", color: "#111827", marginBottom: 6 }}>{s.title}</div>
                  <p style={{ font: "400 13px/1.5 Inter Variable, sans-serif", color: "#6B7280", margin: 0 }}>{s.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Form */}
        <section id="apply" style={{ padding: isMobile ? "48px 20px" : "64px 48px", background: "#FFFFFF", borderTop: "1px solid #E5E7EB" }}>
          <div style={{ maxWidth: 640, margin: "0 auto" }}>
            <h2 style={{ font: `700 ${isMobile ? 24 : 30}px/1.2 Inter Variable, sans-serif`, letterSpacing: "-0.01em", margin: "0 0 8px", color: "#111827", textAlign: "center" }}>
              Оставить заявку
            </h2>
            <p style={{ font: "400 15px/1.55 Inter Variable, sans-serif", color: "#6B7280", margin: "0 0 28px", textAlign: "center" }}>
              Оставьте заявку — наш менеджер свяжется с вами.
            </p>

            {submitted ? (
              <div style={{ background: "#ECFDF5", border: "1px solid #A7F3D0", borderRadius: 16, padding: "24px 28px", textAlign: "center" }}>
                <div style={{ width: 48, height: 48, borderRadius: "50%", background: "#10B981", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 12px" }}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                <div style={{ font: "700 18px/1.3 Inter Variable, sans-serif", color: "#065F46", marginBottom: 6 }}>Заявка отправлена</div>
                <p style={{ font: "400 14px/1.55 Inter Variable, sans-serif", color: "#047857", margin: 0 }}>
                  Мы получили ваши данные и в ближайшее время свяжемся с вами.
                </p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <Field label="Название компании *" value={form.company_name} onChange={(v) => upd("company_name", v)} required disabled={submitting} />
                <Field label="ФИО контактного лица *" value={form.contact_name} onChange={(v) => upd("contact_name", v)} required disabled={submitting} />
                <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: 14 }}>
                  <Field label="Телефон *" value={form.phone} onChange={(v) => upd("phone", v)} placeholder="+7 700 000 00 00" required disabled={submitting} type="tel" />
                  <Field label="Email *" value={form.email} onChange={(v) => upd("email", v)} placeholder="info@company.kz" required disabled={submitting} type="email" />
                </div>
                <Field label="Города / регионы работы" value={form.cities} onChange={(v) => upd("cities", v)} disabled={submitting} />

                <div>
                  <label style={{ display: "block", font: "600 13px/1 Inter Variable, sans-serif", color: "#111827", marginBottom: 8 }}>
                    Тип интеграции
                  </label>
                  <div style={{ display: "grid", gap: 8 }}>
                    {[
                      { key: "api", label: "Готовы к автоматической интеграции" },
                      { key: "manual", label: "Принимаем заказы вручную через кабинет" },
                      { key: "unsure", label: "Нужна консультация" },
                    ].map((opt) => (
                      <label key={opt.key} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", border: form.integration_type === opt.key ? "1px solid #2563EB" : "1px solid #E5E7EB", borderRadius: 10, background: form.integration_type === opt.key ? "#EFF6FF" : "#FFFFFF", cursor: submitting ? "not-allowed" : "pointer", transition: "all 0.15s" }}>
                        <input
                          type="radio"
                          name="integration_type"
                          value={opt.key}
                          checked={form.integration_type === opt.key}
                          onChange={() => upd("integration_type", opt.key as PartnerIntegrationType)}
                          disabled={submitting}
                          style={{ accentColor: "#2563EB" }}
                        />
                        <span style={{ font: "400 14px/1.4 Inter Variable, sans-serif", color: "#111827" }}>{opt.label}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div>
                  <label style={{ display: "block", font: "600 13px/1 Inter Variable, sans-serif", color: "#111827", marginBottom: 6 }}>
                    Комментарий
                  </label>
                  <textarea
                    value={form.comment}
                    onChange={(e) => upd("comment", e.target.value)}
                    rows={4}
                    maxLength={2000}
                    placeholder="Кратко расскажите о компании"
                    disabled={submitting}
                    style={{ width: "100%", padding: "10px 12px", border: "1px solid #E5E7EB", borderRadius: 10, font: "400 14px/1.5 Inter Variable, sans-serif", color: "#111827", background: "#FFFFFF", outline: "none", resize: "vertical", boxSizing: "border-box" }}
                  />
                </div>

                <label style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "4px 0" }}>
                  <input
                    type="checkbox"
                    checked={form.consent}
                    onChange={(e) => upd("consent", e.target.checked)}
                    disabled={submitting}
                    style={{ marginTop: 3, accentColor: "#2563EB" }}
                  />
                  <span style={{ font: "400 13px/1.5 Inter Variable, sans-serif", color: "#6B7280" }}>
                    Согласен на обработку персональных данных для связи по вопросу партнёрства.
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
                  style={{ marginTop: 4, padding: "12px 24px", background: "#2563EB", color: "#FFFFFF", border: "none", borderRadius: 10, font: "600 15px/1 Inter Variable, sans-serif", cursor: submitting ? "not-allowed" : "pointer", opacity: submitting ? 0.7 : 1, transition: "background 0.15s" }}
                >
                  {submitting ? "Отправляем…" : "Отправить заявку"}
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
      <label style={{ display: "block", font: "600 13px/1 Inter Variable, sans-serif", color: "#111827", marginBottom: 6 }}>
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        style={{ width: "100%", padding: "10px 12px", border: "1px solid #E5E7EB", borderRadius: 10, font: "400 14px/1 Inter Variable, sans-serif", color: "#111827", background: "#FFFFFF", outline: "none", boxSizing: "border-box" }}
      />
    </div>
  );
}
