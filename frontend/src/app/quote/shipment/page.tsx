"use client";

import type { CSSProperties, FormEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import {
  ApiError,
  createDraftFromQuote,
  updateOrderDraftShipment,
} from "@/lib/api/orders";
import type { ProfileResponse } from "@/types/auth";
import type {
  OrderDraftResponse,
  ShipmentPackageInput,
  ShipmentPartyInput,
  UpdateShipmentDetailsRequest,
} from "@/types/order";

// ─── Types ────────────────────────────────────────────────────────────────────

type PartyFormState = {
  full_name: string;
  phone: string;
  email: string;
  company_name: string;
  country: string;
  city: string;
  address_line1: string;
  address_line2: string;
  postal_code: string;
  comment: string;
};

type PackageFormState = {
  description: string;
  quantity: string;
  weight_kg: string;
  width_cm: string;
  height_cm: string;
  depth_cm: string;
};

type ShipmentFormState = {
  sender: PartyFormState;
  recipient: PartyFormState;
  packageItem: PackageFormState;
};

// ─── Styles ───────────────────────────────────────────────────────────────────

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  background: "linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%)",
  padding: "32px 20px 64px",
  color: "#0f172a",
  fontFamily:
    "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
};

const containerStyle: CSSProperties = { maxWidth: 1100, margin: "0 auto" };

const cardStyle: CSSProperties = {
  border: "1px solid #e5e7eb",
  borderRadius: 16,
  padding: 20,
  background: "#ffffff",
  boxShadow: "0 8px 24px rgba(15, 23, 42, 0.06)",
};

const tariffCardStyle: CSSProperties = {
  ...cardStyle,
  border: "1.5px solid #6366f1",
  background: "linear-gradient(135deg, #f5f3ff 0%, #eff6ff 100%)",
  marginBottom: 24,
};

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "12px 14px",
  borderRadius: 12,
  border: "1px solid #cbd5e1",
  fontSize: 14,
  outline: "none",
  boxSizing: "border-box",
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
  padding: "12px 24px",
  fontSize: 14,
  fontWeight: 600,
  cursor: "pointer",
};

const buttonSecondary: CSSProperties = {
  background: "#ffffff",
  color: "#0f172a",
  border: "1px solid #cbd5e1",
  borderRadius: 12,
  padding: "12px 16px",
  fontSize: 14,
  fontWeight: 600,
  cursor: "pointer",
};

const badgeStyle: CSSProperties = {
  display: "inline-block",
  padding: "6px 10px",
  borderRadius: 999,
  background: "#eff6ff",
  color: "#1d4ed8",
  fontSize: 12,
  fontWeight: 700,
};

const errorStyle: CSSProperties = {
  ...cardStyle,
  border: "1px solid #fecaca",
  background: "#fef2f2",
  color: "#b91c1c",
  marginBottom: 20,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

const emptyParty = (): PartyFormState => ({
  full_name: "",
  phone: "",
  email: "",
  company_name: "",
  country: "KZ",
  city: "",
  address_line1: "",
  address_line2: "",
  postal_code: "",
  comment: "",
});

const emptyPackage = (): PackageFormState => ({
  description: "",
  quantity: "1",
  weight_kg: "",
  width_cm: "",
  height_cm: "",
  depth_cm: "",
});

function formatPrice(price: number, currency: string): string {
  return `${new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(price)} ${currency}`;
}

function mapPartyFormToPayload(party: PartyFormState): ShipmentPartyInput {
  return {
    full_name: party.full_name.trim(),
    phone: party.phone.trim(),
    email: party.email.trim() || null,
    company_name: party.company_name.trim() || null,
    country: party.country.trim().toUpperCase(),
    city: party.city.trim(),
    address_line1: party.address_line1.trim(),
    address_line2: party.address_line2.trim() || null,
    postal_code: party.postal_code.trim() || null,
    comment: party.comment.trim() || null,
  };
}

function mapPackageFormToPayload(pkg: PackageFormState): ShipmentPackageInput {
  return {
    description: pkg.description.trim(),
    quantity: Number(pkg.quantity),
    weight_kg: Number(pkg.weight_kg),
    width_cm: Number(pkg.width_cm),
    height_cm: Number(pkg.height_cm),
    depth_cm: Number(pkg.depth_cm),
    declared_value: null,
    declared_value_currency: null,
  };
}

function buildShipmentPayload(form: ShipmentFormState): UpdateShipmentDetailsRequest {
  return {
    sender: mapPartyFormToPayload(form.sender),
    recipient: mapPartyFormToPayload(form.recipient),
    packages: [mapPackageFormToPayload(form.packageItem)],
  };
}

function mergeSenderWithCurrentUser(
  sender: PartyFormState,
  currentUser: ProfileResponse | null,
): PartyFormState {
  return {
    ...sender,
    full_name: sender.full_name || currentUser?.full_name || "",
    phone: sender.phone || currentUser?.phone || "",
    email: sender.email || currentUser?.email || "",
    company_name: sender.company_name || currentUser?.company_name || "",
  };
}

function mapDraftToForm(
  draft: OrderDraftResponse,
  currentUser: ProfileResponse | null,
): ShipmentFormState {
  const baseSender = draft.sender
    ? {
        full_name: draft.sender.full_name,
        phone: draft.sender.phone,
        email: draft.sender.email || "",
        company_name: draft.sender.company_name || "",
        country: draft.sender.country,
        city: draft.sender.city,
        address_line1: draft.sender.address_line1,
        address_line2: draft.sender.address_line2 || "",
        postal_code: draft.sender.postal_code || "",
        comment: draft.sender.comment || "",
      }
    : { ...emptyParty(), country: draft.from_country_snapshot || "KZ", city: draft.from_city_snapshot || "" };

  return {
    sender: mergeSenderWithCurrentUser(baseSender, currentUser),
    recipient: draft.recipient
      ? {
          full_name: draft.recipient.full_name,
          phone: draft.recipient.phone,
          email: draft.recipient.email || "",
          company_name: draft.recipient.company_name || "",
          country: draft.recipient.country,
          city: draft.recipient.city,
          address_line1: draft.recipient.address_line1,
          address_line2: draft.recipient.address_line2 || "",
          postal_code: draft.recipient.postal_code || "",
          comment: draft.recipient.comment || "",
        }
      : { ...emptyParty(), country: draft.to_country_snapshot || "KZ", city: draft.to_city_snapshot || "" },
    packageItem: draft.packages[0]
      ? {
          description: draft.packages[0].description,
          quantity: String(draft.packages[0].quantity),
          weight_kg: String(draft.packages[0].weight_kg),
          width_cm: String(draft.packages[0].width_cm),
          height_cm: String(draft.packages[0].height_cm),
          depth_cm: String(draft.packages[0].depth_cm),
        }
      : emptyPackage(),
  };
}

// ─── Tariff summary card ──────────────────────────────────────────────────────

function TariffCard({
  draft,
  onChangeTariff,
}: {
  draft: OrderDraftResponse;
  onChangeTariff: () => void;
}) {
  return (
    <div style={tariffCardStyle}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: 16,
        }}
      >
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#6366f1", textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>
            Выбранный тариф
          </div>
          <div style={{ fontSize: 20, fontWeight: 800, color: "#0f172a", marginBottom: 4 }}>
            {draft.carrier_name_snapshot} — {draft.tariff_name_snapshot}
          </div>
          <div style={{ fontSize: 14, color: "#475569" }}>
            {draft.from_city_snapshot} → {draft.to_city_snapshot}
            {" · "}
            {draft.shipment_type_snapshot}
          </div>
        </div>

        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 28, fontWeight: 800, color: "#0f172a" }}>
            {formatPrice(draft.price_snapshot, draft.currency_snapshot)}
          </div>
          <div style={{ fontSize: 13, color: "#6366f1", fontWeight: 600, marginBottom: 12 }}>
            {draft.eta_days_min_snapshot}–{draft.eta_days_max_snapshot} дн.
          </div>
          <button style={{ ...buttonSecondary, fontSize: 13, padding: "8px 14px" }} onClick={onChangeTariff}>
            Изменить тариф
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Party form section ───────────────────────────────────────────────────────

function PartySection({
  title,
  values,
  onChange,
}: {
  title: string;
  values: PartyFormState;
  onChange: (key: keyof PartyFormState, value: string) => void;
}) {
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
    <div style={cardStyle}>
      <h2 style={{ marginTop: 0, marginBottom: 20, fontSize: 20, fontWeight: 700 }}>{title}</h2>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: 16,
        }}
      >
        {fields.map(({ key, label, required }) => (
          <div key={key}>
            <label style={labelStyle}>
              {label}
              {required && <span style={{ color: "#ef4444", marginLeft: 2 }}>*</span>}
            </label>
            <input
              style={inputStyle}
              value={values[key]}
              onChange={(e) => onChange(key, e.target.value)}
              required={required}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Package form section ─────────────────────────────────────────────────────

function PackageSection({
  values,
  onChange,
}: {
  values: PackageFormState;
  onChange: (key: keyof PackageFormState, value: string) => void;
}) {
  const fields: { key: keyof PackageFormState; label: string; mode?: string }[] = [
    { key: "description", label: "Описание содержимого" },
    { key: "quantity", label: "Количество мест", mode: "numeric" },
    { key: "weight_kg", label: "Вес, кг", mode: "decimal" },
    { key: "width_cm", label: "Ширина, см", mode: "decimal" },
    { key: "height_cm", label: "Высота, см", mode: "decimal" },
    { key: "depth_cm", label: "Глубина, см", mode: "decimal" },
  ];

  return (
    <div style={cardStyle}>
      <h2 style={{ marginTop: 0, marginBottom: 20, fontSize: 20, fontWeight: 700 }}>
        Параметры отправления
      </h2>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: 16,
        }}
      >
        {fields.map(({ key, label, mode }) => (
          <div key={key}>
            <label style={labelStyle}>
              {label}
              <span style={{ color: "#ef4444", marginLeft: 2 }}>*</span>
            </label>
            <input
              style={inputStyle}
              value={values[key]}
              onChange={(e) => onChange(key, e.target.value)}
              inputMode={mode as React.HTMLAttributes<HTMLInputElement>["inputMode"]}
              required
            />
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ShipmentPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { currentUser, isAuthenticated, isLoading, logout } = useAuth();

  const quoteSessionId = useMemo(() => {
    const raw = searchParams.get("quoteSessionId");
    if (!raw) return null;
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);

  const fullNextUrl = useMemo(
    () => (quoteSessionId ? `/quote/shipment?quoteSessionId=${quoteSessionId}` : "/quote/shipment"),
    [quoteSessionId],
  );

  const createDraftRequestedRef = useRef(false);

  const [form, setForm] = useState<ShipmentFormState>({
    sender: emptyParty(),
    recipient: emptyParty(),
    packageItem: emptyPackage(),
  });

  const [draft, setDraft] = useState<OrderDraftResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Redirect if not authenticated
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace(`/login?next=${encodeURIComponent(fullNextUrl)}`);
    }
  }, [fullNextUrl, isAuthenticated, isLoading, router]);

  // Pre-fill sender from current user profile
  useEffect(() => {
    if (!currentUser) return;
    setForm((prev) => ({
      ...prev,
      sender: mergeSenderWithCurrentUser(prev.sender, currentUser),
    }));
  }, [currentUser]);

  // Bootstrap draft
  useEffect(() => {
    if (isLoading || !isAuthenticated) return;

    if (!quoteSessionId) {
      setError("Не найден quoteSessionId. Вернитесь к выбору тарифа.");
      setIsBootstrapping(false);
      return;
    }

    if (createDraftRequestedRef.current) return;
    createDraftRequestedRef.current = true;

    async function bootstrapDraft() {
      setError(null);
      setIsBootstrapping(true);

      try {
        const createdDraft = await createDraftFromQuote({ quote_session_id: quoteSessionId! });
        setDraft(createdDraft);
        setForm(mapDraftToForm(createdDraft, currentUser));
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 401) {
            logout(`/login?next=${encodeURIComponent(fullNextUrl)}`);
            return;
          }
          setError(err.detail);
        } else if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Не удалось подготовить черновик заказа.");
        }
      } finally {
        setIsBootstrapping(false);
      }
    }

    void bootstrapDraft();
  }, [currentUser, fullNextUrl, isAuthenticated, isLoading, logout, quoteSessionId]);

  function updatePartyField(role: "sender" | "recipient", key: keyof PartyFormState, value: string) {
    setForm((prev) => ({ ...prev, [role]: { ...prev[role], [key]: value } }));
  }

  function updatePackageField(key: keyof PackageFormState, value: string) {
    setForm((prev) => ({ ...prev, packageItem: { ...prev.packageItem, [key]: value } }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!draft) {
      setError("Черновик заказа ещё не создан.");
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      const payload = buildShipmentPayload(form);
      await updateOrderDraftShipment(draft.draft_id, payload);
      // Navigate to orders list after successful save
      router.push("/dashboard/orders");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          logout(`/login?next=${encodeURIComponent(fullNextUrl)}`);
          return;
        }
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

  if (isLoading || (!isAuthenticated && !error)) {
    return (
      <main style={pageStyle}>
        <div style={containerStyle}>
          <div style={cardStyle}>Проверяем доступ к оформлению...</div>
        </div>
      </main>
    );
  }

  return (
    <main style={pageStyle}>
      <div style={containerStyle}>
        {/* Header */}
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: 16,
            alignItems: "center",
            marginBottom: 28,
            flexWrap: "wrap",
          }}
        >
          <div>
            <div style={badgeStyle}>Оформление отправления</div>
            <h1 style={{ margin: "14px 0 8px", fontSize: 34, lineHeight: 1.1 }}>
              Данные отправления
            </h1>
            <p style={{ margin: 0, color: "#475569", lineHeight: 1.7 }}>
              Заполните данные отправителя, получателя и параметры посылки.
            </p>
          </div>

          <button
            style={buttonSecondary}
            onClick={() =>
              router.push(
                quoteSessionId ? `/quote/results?quoteSessionId=${quoteSessionId}` : "/",
              )
            }
          >
            Назад к тарифам
          </button>
        </header>

        {error && <div style={errorStyle}>{error}</div>}

        {isBootstrapping ? (
          <div style={{ ...cardStyle }}>Подготавливаем черновик заказа...</div>
        ) : draft ? (
          <>
            {/* Selected tariff card */}
            <TariffCard
              draft={draft}
              onChangeTariff={() =>
                router.push(
                  quoteSessionId ? `/quote/results?quoteSessionId=${quoteSessionId}` : "/",
                )
              }
            />

            {/* Shipment form */}
            <form onSubmit={handleSubmit} style={{ display: "grid", gap: 20 }}>
              <PartySection
                title="Отправитель"
                values={form.sender}
                onChange={(key, val) => updatePartyField("sender", key, val)}
              />

              <PartySection
                title="Получатель"
                values={form.recipient}
                onChange={(key, val) => updatePartyField("recipient", key, val)}
              />

              <PackageSection
                values={form.packageItem}
                onChange={updatePackageField}
              />

              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <button
                  type="submit"
                  style={{
                    ...buttonPrimary,
                    opacity: isSubmitting ? 0.7 : 1,
                    cursor: isSubmitting ? "not-allowed" : "pointer",
                  }}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Сохраняем..." : "Сохранить и продолжить →"}
                </button>

                <button
                  type="button"
                  style={buttonSecondary}
                  onClick={() => router.push("/")}
                >
                  На главную
                </button>
              </div>
            </form>
          </>
        ) : null}
      </div>
    </main>
  );
}
