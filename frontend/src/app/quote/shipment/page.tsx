"use client";

import type { FormEvent } from "react";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Check } from "lucide-react";

import Navbar from "@/components/layout/Navbar";
import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { ApiError, createDraftFromQuote, updateOrderDraftShipment } from "@/lib/api/orders";
import type { ProfileResponse } from "@/types/auth";
import type {
  OrderDraftResponse,
  ShipmentPackageInput,
  ShipmentPartyInput,
  UpdateShipmentDetailsRequest,
} from "@/types/order";

/* ─── Types ──────────────────────────────────────────────────────────────── */

type PartyFormState = {
  full_name: string; phone: string; email: string; company_name: string;
  country: string; city: string; address_line1: string; address_line2: string;
  postal_code: string; comment: string; save_to_address_book: boolean;
};

type PackageFormState = {
  description: string; quantity: string; weight_kg: string;
  width_cm: string; height_cm: string; depth_cm: string;
};

type ShipmentFormState = {
  sender: PartyFormState; recipient: PartyFormState;
  packageItem: PackageFormState;
  call_before_delivery: boolean; insurance: boolean; fragile: boolean;
};

/* ─── Helpers ────────────────────────────────────────────────────────────── */

const emptyParty = (): PartyFormState => ({
  full_name: "", phone: "", email: "", company_name: "", country: "KZ",
  city: "", address_line1: "", address_line2: "", postal_code: "",
  comment: "", save_to_address_book: false,
});

const emptyPackage = (): PackageFormState => ({
  description: "", quantity: "1", weight_kg: "", width_cm: "", height_cm: "", depth_cm: "",
});

function formatPrice(price: number, currency: string): string {
  return `${new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(price)} ${currency}`;
}

function mapPartyFormToPayload(party: PartyFormState): ShipmentPartyInput {
  return {
    full_name: party.full_name.trim(), phone: party.phone.trim(),
    email: party.email.trim() || null, company_name: party.company_name.trim() || null,
    country: party.country.trim().toUpperCase(), city: party.city.trim(),
    address_line1: party.address_line1.trim(), address_line2: party.address_line2.trim() || null,
    postal_code: party.postal_code.trim() || null, comment: party.comment.trim() || null,
    save_to_address_book: party.save_to_address_book,
  };
}

function mapPackageFormToPayload(pkg: PackageFormState): ShipmentPackageInput {
  return {
    description: pkg.description.trim(), quantity: Number(pkg.quantity),
    weight_kg: Number(pkg.weight_kg), width_cm: Number(pkg.width_cm),
    height_cm: Number(pkg.height_cm), depth_cm: Number(pkg.depth_cm),
    declared_value: null, declared_value_currency: null,
  };
}

function buildShipmentPayload(form: ShipmentFormState): UpdateShipmentDetailsRequest {
  return {
    sender: mapPartyFormToPayload(form.sender),
    recipient: mapPartyFormToPayload(form.recipient),
    packages: [mapPackageFormToPayload(form.packageItem)],
    call_before_delivery: form.call_before_delivery,
    insurance: form.insurance,
    fragile: form.fragile,
  };
}

function mergeSenderWithCurrentUser(sender: PartyFormState, user: ProfileResponse | null): PartyFormState {
  return {
    ...sender,
    full_name: sender.full_name || user?.full_name || "",
    phone: sender.phone || user?.phone || "",
    email: sender.email || user?.email || "",
    company_name: sender.company_name || user?.company_name || "",
  };
}

function mapDraftToForm(draft: OrderDraftResponse, user: ProfileResponse | null): ShipmentFormState {
  const baseSender = draft.sender
    ? { full_name: draft.sender.full_name, phone: draft.sender.phone, email: draft.sender.email || "", company_name: draft.sender.company_name || "", country: draft.sender.country, city: draft.sender.city, address_line1: draft.sender.address_line1, address_line2: draft.sender.address_line2 || "", postal_code: draft.sender.postal_code || "", comment: draft.sender.comment || "", save_to_address_book: false }
    : { ...emptyParty(), country: draft.from_country_snapshot || "KZ", city: draft.from_city_snapshot || "" };

  return {
    sender: mergeSenderWithCurrentUser(baseSender, user),
    recipient: draft.recipient
      ? { full_name: draft.recipient.full_name, phone: draft.recipient.phone, email: draft.recipient.email || "", company_name: draft.recipient.company_name || "", country: draft.recipient.country, city: draft.recipient.city, address_line1: draft.recipient.address_line1, address_line2: draft.recipient.address_line2 || "", postal_code: draft.recipient.postal_code || "", comment: draft.recipient.comment || "", save_to_address_book: false }
      : { ...emptyParty(), country: draft.to_country_snapshot || "KZ", city: draft.to_city_snapshot || "" },
    packageItem: draft.packages[0]
      ? { description: draft.packages[0].description, quantity: String(draft.packages[0].quantity), weight_kg: String(draft.packages[0].weight_kg), width_cm: String(draft.packages[0].width_cm), height_cm: String(draft.packages[0].height_cm), depth_cm: String(draft.packages[0].depth_cm) }
      : emptyPackage(),
    call_before_delivery: draft.call_before_delivery ?? false,
    insurance: draft.insurance ?? false,
    fragile: draft.fragile ?? false,
  };
}

/* ─── Stepper ────────────────────────────────────────────────────────────── */

const STEPS = ["Данные отправления", "Отправитель", "Получатель", "Оплата"];

function Stepper({ current }: { current: number }) {
  const isMobile = useIsMobile();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: 40 }}>
      {STEPS.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", flex: i < STEPS.length - 1 ? 1 : "none" }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
              <div
                style={{
                  width: isMobile ? 32 : 40,
                  height: isMobile ? 32 : 40,
                  borderRadius: "50%",
                  border: done ? "none" : active ? "none" : "2px solid #E5E7EB",
                  background: done ? "#10B981" : active ? "#2563EB" : "#ffffff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  font: `700 ${isMobile ? "13px" : "15px"}/1 Inter Variable, sans-serif`,
                  color: done || active ? "#ffffff" : "#9CA3AF",
                  boxShadow: active ? "0 0 0 4px rgba(37,99,235,0.15)" : "none",
                  flexShrink: 0,
                  transition: "all 0.2s",
                }}
              >
                {done ? <Check size={isMobile ? 13 : 16} strokeWidth={3} /> : i + 1}
              </div>
              {!isMobile && (
                <span
                  style={{
                    font: "500 12px/1 Inter Variable, sans-serif",
                    color: active ? "#111827" : done ? "#10B981" : "#9CA3AF",
                    whiteSpace: "nowrap",
                  }}
                >
                  {label}
                </span>
              )}
            </div>
            {i < STEPS.length - 1 && (
              <div
                style={{
                  flex: 1,
                  height: 2,
                  background: done ? "#10B981" : active ? "#2563EB" : "#E5E7EB",
                  margin: "0 6px",
                  marginBottom: isMobile ? 0 : 18,
                  transition: "background 0.2s",
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ─── Input field ────────────────────────────────────────────────────────── */

function FormField({
  label,
  value,
  onChange,
  required,
  inputMode,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
  placeholder?: string;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <div>
      <label style={{ display: "block", font: "600 13px/1 Inter Variable, sans-serif", color: "#374151", marginBottom: 6 }}>
        {label}
        {required && <span style={{ color: "#EF4444", marginLeft: 2 }}>*</span>}
      </label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        inputMode={inputMode}
        placeholder={placeholder}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          width: "100%",
          padding: "11px 14px",
          borderRadius: 10,
          border: focused ? "1.5px solid #2563EB" : "1.5px solid #E5E7EB",
          boxShadow: focused ? "0 0 0 3px rgba(37,99,235,0.15)" : "none",
          font: "400 14px/1 Inter Variable, sans-serif",
          color: "#111827",
          background: "#fff",
          outline: "none",
          boxSizing: "border-box",
          fontFamily: "inherit",
          transition: "border-color 0.15s, box-shadow 0.15s",
        }}
      />
    </div>
  );
}

/* ─── Section card ───────────────────────────────────────────────────────── */

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: "#ffffff",
        border: "1px solid #E5E7EB",
        borderRadius: 16,
        padding: "24px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
      }}
    >
      <h2 style={{ font: "600 18px/1.2 Inter Variable, sans-serif", color: "#111827", margin: "0 0 20px" }}>
        {title}
      </h2>
      {children}
    </div>
  );
}

/* ─── Tariff summary card ────────────────────────────────────────────────── */

function TariffSummary({ draft, onChangeTariff }: { draft: OrderDraftResponse; onChangeTariff: () => void }) {
  return (
    <div
      style={{
        background: "#EFF6FF",
        border: "1.5px solid #2563EB",
        borderRadius: 16,
        padding: "20px 24px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 16,
        marginBottom: 28,
        boxShadow: "0 4px 16px rgba(37,99,235,0.10)",
      }}
    >
      <div>
        <div style={{ font: "500 11px/1 Inter Variable, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: "#2563EB", marginBottom: 8 }}>
          Выбранный тариф
        </div>
        <div style={{ font: "700 18px/1.2 Inter Variable, sans-serif", color: "#111827", marginBottom: 4 }}>
          {draft.carrier_name_snapshot} - {draft.tariff_name_snapshot}
        </div>
        <div style={{ font: "400 14px/1 Inter Variable, sans-serif", color: "#6B7280" }}>
          {draft.from_city_snapshot} → {draft.to_city_snapshot} · {draft.shipment_type_snapshot}
        </div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ font: "700 26px/1 Inter Variable, sans-serif", color: "#111827", marginBottom: 4 }}>
          {formatPrice(draft.price_snapshot, draft.currency_snapshot)}
        </div>
        <div style={{ font: "600 13px/1 Inter Variable, sans-serif", color: "#2563EB", marginBottom: 12 }}>
          {draft.eta_days_min_snapshot}–{draft.eta_days_max_snapshot} дн.
        </div>
        <button
          onClick={onChangeTariff}
          style={{
            border: "1.5px solid #2563EB",
            background: "#ffffff",
            color: "#2563EB",
            borderRadius: 8,
            padding: "7px 14px",
            font: "600 13px/1 Inter Variable, sans-serif",
            cursor: "pointer",
            fontFamily: "inherit",
            transition: "all 0.15s",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "#EFF6FF"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "#ffffff"; }}
        >
          Изменить тариф
        </button>
      </div>
    </div>
  );
}

/* ─── Party section ──────────────────────────────────────────────────────── */

function PartySection({ title, values, onChange, onToggleSave }: {
  title: string;
  values: PartyFormState;
  onChange: (key: keyof PartyFormState, value: string) => void;
  onToggleSave: (val: boolean) => void;
}) {
  const isMobile = useIsMobile();
  const fields: { key: keyof PartyFormState; label: string; required?: boolean }[] = [
    { key: "full_name", label: "ФИО", required: true },
    { key: "phone", label: "Телефон", required: true },
    { key: "email", label: "Email" },
    { key: "company_name", label: "Компания" },
    { key: "country", label: "Код страны (2 буквы)", required: true },
    { key: "city", label: "Город", required: true },
    { key: "address_line1", label: "Адрес", required: true },
    { key: "address_line2", label: "Доп. адрес" },
    { key: "postal_code", label: "Почтовый индекс" },
    { key: "comment", label: "Комментарий" },
  ];

  return (
    <SectionCard title={title}>
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(2, minmax(0, 1fr))", gap: 14 }}>
        {fields.map(({ key, label, required }) => (
          <FormField
            key={key as string}
            label={label}
            value={values[key] as string}
            onChange={(v) => onChange(key, v)}
            required={required}
          />
        ))}
      </div>
      <label
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginTop: 16,
          cursor: "pointer",
          font: "500 14px/1 Inter Variable, sans-serif",
          color: "#374151",
        }}
      >
        <input
          type="checkbox"
          checked={values.save_to_address_book}
          onChange={(e) => onToggleSave(e.target.checked)}
          style={{ width: 16, height: 16, cursor: "pointer", accentColor: "#2563EB" }}
        />
        Сохранить в адресную книгу
      </label>
    </SectionCard>
  );
}

/* ─── Package section ────────────────────────────────────────────────────── */

function PackageSection({ values, onChange }: {
  values: PackageFormState;
  onChange: (key: keyof PackageFormState, value: string) => void;
}) {
  const isMobile = useIsMobile();
  const fields: { key: keyof PackageFormState; label: string; mode?: React.HTMLAttributes<HTMLInputElement>["inputMode"] }[] = [
    { key: "description", label: "Описание содержимого" },
    { key: "quantity", label: "Количество мест", mode: "numeric" },
    { key: "weight_kg", label: "Вес, кг", mode: "decimal" },
    { key: "width_cm", label: "Ширина, см", mode: "decimal" },
    { key: "height_cm", label: "Высота, см", mode: "decimal" },
    { key: "depth_cm", label: "Глубина, см", mode: "decimal" },
  ];

  return (
    <SectionCard title="Параметры отправления">
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(2, minmax(0, 1fr))", gap: 14 }}>
        {fields.map(({ key, label, mode }) => (
          <FormField
            key={key}
            label={label}
            value={values[key]}
            onChange={(v) => onChange(key, v)}
            required
            inputMode={mode}
          />
        ))}
      </div>
    </SectionCard>
  );
}

/* ─── Page ───────────────────────────────────────────────────────────────── */

function ShipmentPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { currentUser, isAuthenticated, isLoading, logout } = useAuth();

  const quoteSessionId = useMemo(() => {
    const raw = searchParams.get("quoteSessionId");
    if (!raw) return null;
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);

  const quoteToken = searchParams.get("token");

  const fullNextUrl = useMemo(
    () => (quoteSessionId
      ? `/quote/shipment?quoteSessionId=${quoteSessionId}${quoteToken ? `&token=${quoteToken}` : ""}`
      : "/quote/shipment"),
    [quoteSessionId, quoteToken],
  );

  const createDraftRequestedRef = useRef(false);
  const storageKey = quoteSessionId ? `novex_shipment_form_${quoteSessionId}` : null;

  function loadSavedForm(): ShipmentFormState | null {
    if (!storageKey) return null;
    try { const raw = sessionStorage.getItem(storageKey); return raw ? JSON.parse(raw) : null; } catch { return null; }
  }
  function saveForm(f: ShipmentFormState) {
    if (!storageKey) return;
    try { sessionStorage.setItem(storageKey, JSON.stringify(f)); } catch { /* ignore */ }
  }
  function clearSavedForm() {
    if (!storageKey) return;
    try { sessionStorage.removeItem(storageKey); } catch { /* ignore */ }
  }

  const [form, setForm] = useState<ShipmentFormState>(
    () => loadSavedForm() ?? { sender: emptyParty(), recipient: emptyParty(), packageItem: emptyPackage(), call_before_delivery: false, insurance: false, fragile: false },
  );

  const [draft, setDraft] = useState<OrderDraftResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace(`/login?next=${encodeURIComponent(fullNextUrl)}`);
    }
  }, [fullNextUrl, isAuthenticated, isLoading, router]);

  useEffect(() => {
    if (!currentUser) return;
    setForm((prev) => ({ ...prev, sender: mergeSenderWithCurrentUser(prev.sender, currentUser) }));
  }, [currentUser]);

  useEffect(() => {
    if (isLoading || !isAuthenticated) return;
    if (!quoteSessionId) { setError("Не найден quoteSessionId. Вернитесь к выбору тарифа."); setIsBootstrapping(false); return; }
    if (createDraftRequestedRef.current) return;
    createDraftRequestedRef.current = true;

    let cancelled = false;
    async function bootstrap() {
      setError(null);
      setIsBootstrapping(true);
      try {
        const created = await createDraftFromQuote({ quote_session_id: quoteSessionId!, public_token: quoteToken });
        if (cancelled) return;
        setDraft(created);
        setForm(mapDraftToForm(created, currentUser));
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError) {
          if (err.status === 401) { logout(`/login?next=${encodeURIComponent(fullNextUrl)}`); return; }
          setError(err.detail);
        } else if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Не удалось подготовить черновик заказа.");
        }
      } finally {
        if (!cancelled) setIsBootstrapping(false);
      }
    }
    void bootstrap();
    return () => { cancelled = true; createDraftRequestedRef.current = false; };
  }, [currentUser, fullNextUrl, isAuthenticated, isLoading, logout, quoteSessionId, quoteToken]);

  function updateForm(updater: (prev: ShipmentFormState) => ShipmentFormState) {
    setForm((prev) => { const next = updater(prev); saveForm(next); return next; });
  }

  function updatePartyField(role: "sender" | "recipient", key: keyof PartyFormState, value: string) {
    updateForm((prev) => ({ ...prev, [role]: { ...prev[role], [key]: value } }));
  }
  function toggleSaveAddress(role: "sender" | "recipient", val: boolean) {
    updateForm((prev) => ({ ...prev, [role]: { ...prev[role], save_to_address_book: val } }));
  }
  function toggleService(key: "call_before_delivery" | "insurance" | "fragile", val: boolean) {
    updateForm((prev) => ({ ...prev, [key]: val }));
  }
  function updatePackageField(key: keyof PackageFormState, value: string) {
    updateForm((prev) => ({ ...prev, packageItem: { ...prev.packageItem, [key]: value } }));
  }

  function validateStep(step: number): string | null {
    if (step === 0) {
      const p = form.packageItem;
      if (!p.description.trim()) return "Введите описание содержимого.";
      const qty = Number(p.quantity);
      if (!p.quantity || isNaN(qty) || qty <= 0 || !Number.isInteger(qty)) return "Укажите корректное количество мест.";
      const w = Number(p.weight_kg);
      if (!p.weight_kg || isNaN(w) || w <= 0) return "Укажите корректный вес.";
      const wd = Number(p.width_cm), h = Number(p.height_cm), d = Number(p.depth_cm);
      if (!p.width_cm || isNaN(wd) || wd <= 0) return "Укажите ширину.";
      if (!p.height_cm || isNaN(h) || h <= 0) return "Укажите высоту.";
      if (!p.depth_cm || isNaN(d) || d <= 0) return "Укажите глубину.";
    }
    if (step === 1) {
      const s = form.sender;
      if (!s.full_name.trim()) return "Укажите ФИО отправителя.";
      if (!s.phone.trim()) return "Укажите телефон отправителя.";
      if (!s.country.trim() || s.country.trim().length !== 2) return "Код страны - 2 буквы (например KZ).";
      if (!s.city.trim()) return "Укажите город отправителя.";
      if (!s.address_line1.trim()) return "Укажите адрес отправителя.";
    }
    if (step === 2) {
      const r = form.recipient;
      if (!r.full_name.trim()) return "Укажите ФИО получателя.";
      if (!r.phone.trim()) return "Укажите телефон получателя.";
      if (!r.country.trim() || r.country.trim().length !== 2) return "Код страны - 2 буквы (например KZ).";
      if (!r.city.trim()) return "Укажите город получателя.";
      if (!r.address_line1.trim()) return "Укажите адрес получателя.";
    }
    return null;
  }

  function handleNextStep() {
    const err = validateStep(currentStep);
    if (err) { setError(err); return; }
    setError(null);
    setCurrentStep((s) => s + 1);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function handlePrevStep() {
    setError(null);
    setCurrentStep((s) => s - 1);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft) { setError("Черновик заказа ещё не создан."); return; }
    setError(null);
    setIsSubmitting(true);
    try {
      await updateOrderDraftShipment(draft.draft_id, buildShipmentPayload(form));
      clearSavedForm();
      router.push(`/checkout?draftId=${draft.draft_id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) { logout(`/login?next=${encodeURIComponent(fullNextUrl)}`); return; }
        setError(err.detail);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Не удалось сохранить данные отправления.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  const cardBase = {
    background: "#ffffff",
    border: "1px solid #E5E7EB",
    borderRadius: 16,
    padding: "20px 24px",
    boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
  };

  if (isLoading || (!isAuthenticated && !error)) {
    return (
      <div style={{ minHeight: "100vh", background: "#FAFAFA" }}>
        <Navbar />
        <main style={{ maxWidth: 860, margin: "0 auto", padding: "60px 20px" }}>
          <div style={cardBase}>
            <span style={{ font: "400 15px/1 Inter Variable, sans-serif", color: "#6B7280" }}>
              Проверяем доступ к оформлению...
            </span>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#FAFAFA" }}>
      <Navbar />

      <main style={{ maxWidth: 860, margin: "0 auto", padding: "40px 20px 80px" }}>
        {/* Page title */}
        <div style={{ marginBottom: 32 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: 32 }}>
            <h1 style={{ font: "700 28px/1.2 Inter Variable, sans-serif", letterSpacing: "-0.02em", color: "#111827", margin: 0 }}>
              Оформление отправления
            </h1>
            <button
              onClick={() => {
                if (!quoteSessionId) { router.push("/"); return; }
                router.push(`/quote/results?quoteSessionId=${quoteSessionId}${quoteToken ? `&token=${quoteToken}` : ""}`);
              }}
              style={{
                border: "1.5px solid #E5E7EB",
                background: "#ffffff",
                color: "#111827",
                borderRadius: 10,
                padding: "10px 18px",
                font: "600 14px/1 Inter Variable, sans-serif",
                cursor: "pointer",
                fontFamily: "inherit",
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#F9FAFB")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "#ffffff")}
            >
              ← Назад к тарифам
            </button>
          </div>

          <Stepper current={currentStep} />
        </div>

        {/* Error */}
        {error && (
          <div
            style={{
              padding: "12px 16px",
              borderRadius: 10,
              background: "#FEF2F2",
              border: "1px solid #FECACA",
              color: "#B91C1C",
              font: "400 14px/1.4 Inter Variable, sans-serif",
              marginBottom: 20,
            }}
          >
            {error}
          </div>
        )}

        {/* Bootstrapping */}
        {isBootstrapping ? (
          <div style={cardBase}>
            <span style={{ font: "400 15px/1 Inter Variable, sans-serif", color: "#6B7280" }}>
              Подготавливаем черновик заказа...
            </span>
          </div>
        ) : draft ? (
          <>
            {/* Tariff summary */}
            <TariffSummary
              draft={draft}
              onChangeTariff={() =>
                router.push(quoteSessionId ? `/quote/results?quoteSessionId=${quoteSessionId}` : "/")
              }
            />

            {/* Shipment form */}
            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 20 }}>

              {/* ── Step 0: Данные отправления ── */}
              {currentStep === 0 && (
                <>
                  <PackageSection values={form.packageItem} onChange={updatePackageField} />
                  <SectionCard title="Дополнительные услуги">
                    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                      {(
                        [
                          { key: "call_before_delivery", label: "Звонок перед доставкой" },
                          { key: "insurance", label: "Страхование груза" },
                          { key: "fragile", label: "Хрупкий груз" },
                        ] as { key: "call_before_delivery" | "insurance" | "fragile"; label: string }[]
                      ).map(({ key, label }) => (
                        <label key={key} style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer", font: "500 14px/1 Inter Variable, sans-serif", color: "#374151" }}>
                          <input type="checkbox" checked={form[key]} onChange={(e) => toggleService(key, e.target.checked)} style={{ width: 16, height: 16, cursor: "pointer", accentColor: "#2563EB" }} />
                          {label}
                        </label>
                      ))}
                    </div>
                  </SectionCard>
                </>
              )}

              {/* ── Step 1: Отправитель ── */}
              {currentStep === 1 && (
                <PartySection
                  title="Отправитель"
                  values={form.sender}
                  onChange={(key, val) => updatePartyField("sender", key, val)}
                  onToggleSave={(val) => toggleSaveAddress("sender", val)}
                />
              )}

              {/* ── Step 2: Получатель ── */}
              {currentStep === 2 && (
                <PartySection
                  title="Получатель"
                  values={form.recipient}
                  onChange={(key, val) => updatePartyField("recipient", key, val)}
                  onToggleSave={(val) => toggleSaveAddress("recipient", val)}
                />
              )}

              {/* Navigation */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginTop: 8 }}>
                <button
                  type="button"
                  onClick={currentStep === 0 ? () => router.push("/") : handlePrevStep}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#6B7280",
                    font: "500 14px/1 Inter Variable, sans-serif",
                    cursor: "pointer",
                    fontFamily: "inherit",
                    padding: 0,
                  }}
                >
                  {currentStep === 0 ? "На главную" : "← Назад"}
                </button>

                {currentStep < 2 ? (
                  <button
                    type="button"
                    onClick={handleNextStep}
                    style={{
                      background: "#2563EB",
                      color: "#ffffff",
                      border: "none",
                      borderRadius: 10,
                      padding: "14px 32px",
                      font: "600 15px/1 Inter Variable, sans-serif",
                      cursor: "pointer",
                      fontFamily: "inherit",
                      transition: "background 0.15s",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "#1D4ED8"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "#2563EB"; }}
                  >
                    Далее →
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    style={{
                      background: isSubmitting ? "#93C5FD" : "#2563EB",
                      color: "#ffffff",
                      border: "none",
                      borderRadius: 10,
                      padding: "14px 32px",
                      font: "600 15px/1 Inter Variable, sans-serif",
                      cursor: isSubmitting ? "not-allowed" : "pointer",
                      fontFamily: "inherit",
                      transition: "background 0.15s",
                    }}
                    onMouseEnter={(e) => { if (!isSubmitting) e.currentTarget.style.background = "#1D4ED8"; }}
                    onMouseLeave={(e) => { if (!isSubmitting) e.currentTarget.style.background = "#2563EB"; }}
                  >
                    {isSubmitting ? "Сохраняем..." : "Далее → Оплата"}
                  </button>
                )}
              </div>
            </form>
          </>
        ) : null}
      </main>
    </div>
  );
}

export default function ShipmentPage() {
  return (
    <Suspense>
      <ShipmentPageInner />
    </Suspense>
  );
}
