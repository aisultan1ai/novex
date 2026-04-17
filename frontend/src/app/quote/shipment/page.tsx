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
  declared_value: string;
  declared_value_currency: string;
};

type ShipmentFormState = {
  sender: PartyFormState;
  recipient: PartyFormState;
  packageItem: PackageFormState;
};

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  background: "linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%)",
  padding: "32px 20px 64px",
  color: "#0f172a",
  fontFamily:
    "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
};

const containerStyle: CSSProperties = {
  maxWidth: 1100,
  margin: "0 auto",
};

const cardStyle: CSSProperties = {
  border: "1px solid #e5e7eb",
  borderRadius: 16,
  padding: 20,
  background: "#ffffff",
  boxShadow: "0 8px 24px rgba(15, 23, 42, 0.06)",
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
  padding: "12px 16px",
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
};

const successStyle: CSSProperties = {
  ...cardStyle,
  border: "1px solid #bbf7d0",
  background: "#f0fdf4",
  color: "#166534",
};

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
  declared_value: "",
  declared_value_currency: "KZT",
});

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

function mapPackageFormToPayload(
  packageItem: PackageFormState,
): ShipmentPackageInput {
  return {
    description: packageItem.description.trim(),
    quantity: Number(packageItem.quantity),
    weight_kg: Number(packageItem.weight_kg),
    width_cm: Number(packageItem.width_cm),
    height_cm: Number(packageItem.height_cm),
    depth_cm: Number(packageItem.depth_cm),
    declared_value: packageItem.declared_value.trim()
      ? Number(packageItem.declared_value)
      : null,
    declared_value_currency: packageItem.declared_value_currency.trim() || null,
  };
}

function buildShipmentPayload(
  form: ShipmentFormState,
): UpdateShipmentDetailsRequest {
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
  createdDraft: OrderDraftResponse,
  currentUser: ProfileResponse | null,
): ShipmentFormState {
  const baseSender = createdDraft.sender
    ? {
        full_name: createdDraft.sender.full_name,
        phone: createdDraft.sender.phone,
        email: createdDraft.sender.email || "",
        company_name: createdDraft.sender.company_name || "",
        country: createdDraft.sender.country,
        city: createdDraft.sender.city,
        address_line1: createdDraft.sender.address_line1,
        address_line2: createdDraft.sender.address_line2 || "",
        postal_code: createdDraft.sender.postal_code || "",
        comment: createdDraft.sender.comment || "",
      }
    : {
        ...emptyParty(),
        country: createdDraft.from_country_snapshot || "KZ",
        city: createdDraft.from_city_snapshot || "",
      };

  return {
    sender: mergeSenderWithCurrentUser(baseSender, currentUser),
    recipient: createdDraft.recipient
      ? {
          full_name: createdDraft.recipient.full_name,
          phone: createdDraft.recipient.phone,
          email: createdDraft.recipient.email || "",
          company_name: createdDraft.recipient.company_name || "",
          country: createdDraft.recipient.country,
          city: createdDraft.recipient.city,
          address_line1: createdDraft.recipient.address_line1,
          address_line2: createdDraft.recipient.address_line2 || "",
          postal_code: createdDraft.recipient.postal_code || "",
          comment: createdDraft.recipient.comment || "",
        }
      : {
          ...emptyParty(),
          country: createdDraft.to_country_snapshot || "KZ",
          city: createdDraft.to_city_snapshot || "",
        },
    packageItem: createdDraft.packages[0]
      ? {
          description: createdDraft.packages[0].description,
          quantity: String(createdDraft.packages[0].quantity),
          weight_kg: String(createdDraft.packages[0].weight_kg),
          width_cm: String(createdDraft.packages[0].width_cm),
          height_cm: String(createdDraft.packages[0].height_cm),
          depth_cm: String(createdDraft.packages[0].depth_cm),
          declared_value:
            createdDraft.packages[0].declared_value != null
              ? String(createdDraft.packages[0].declared_value)
              : "",
          declared_value_currency:
            createdDraft.packages[0].declared_value_currency || "KZT",
        }
      : emptyPackage(),
  };
}

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

  const fullNextUrl = useMemo(() => {
    if (!quoteSessionId) {
      return "/quote/shipment";
    }
    return `/quote/shipment?quoteSessionId=${quoteSessionId}`;
  }, [quoteSessionId]);

  const createDraftRequestedRef = useRef(false);

  const [form, setForm] = useState<ShipmentFormState>({
    sender: emptyParty(),
    recipient: emptyParty(),
    packageItem: emptyPackage(),
  });

  const [draft, setDraft] = useState<OrderDraftResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isLoading) {
      return;
    }

    if (!isAuthenticated) {
      router.replace(`/login?next=${encodeURIComponent(fullNextUrl)}`);
    }
  }, [fullNextUrl, isAuthenticated, isLoading, router]);

  useEffect(() => {
    if (!currentUser) {
      return;
    }

    setForm((prev) => ({
      ...prev,
      sender: mergeSenderWithCurrentUser(prev.sender, currentUser),
    }));
  }, [currentUser]);

  useEffect(() => {
    if (isLoading || !isAuthenticated) {
      return;
    }

    if (!quoteSessionId) {
      setError("Не найден quoteSessionId. Вернитесь к выбору тарифа.");
      setIsBootstrapping(false);
      return;
    }

    if (createDraftRequestedRef.current) {
      return;
    }

    createDraftRequestedRef.current = true;

    async function bootstrapDraft() {
      setError(null);
      setSuccessMessage(null);
      setIsBootstrapping(true);

      try {
        const createdDraft = await createDraftFromQuote({
          quote_session_id: quoteSessionId,
        });

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

  function updatePartyField(
    role: "sender" | "recipient",
    key: keyof PartyFormState,
    value: string,
  ) {
    setForm((prev) => ({
      ...prev,
      [role]: {
        ...prev[role],
        [key]: value,
      },
    }));
  }

  function updatePackageField(key: keyof PackageFormState, value: string) {
    setForm((prev) => ({
      ...prev,
      packageItem: {
        ...prev.packageItem,
        [key]: value,
      },
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!draft) {
      setError("Draft order ещё не создан.");
      return;
    }

    setError(null);
    setSuccessMessage(null);
    setIsSubmitting(true);

    try {
      const payload = buildShipmentPayload(form);
      const updatedDraft = await updateOrderDraftShipment(draft.draft_id, payload);
      setDraft(updatedDraft);
      setForm(mapDraftToForm(updatedDraft, currentUser));
      setSuccessMessage("Данные отправления успешно сохранены в draft order.");
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
            <div style={badgeStyle}>Shipment details</div>
            <h1 style={{ margin: "14px 0 8px", fontSize: 34, lineHeight: 1.1 }}>
              Оформление отправления
            </h1>
            <p style={{ margin: 0, color: "#475569", lineHeight: 1.7 }}>
              На этом шаге мы создаём draft order и сохраняем sender,
              recipient и package details.
            </p>
          </div>

          <div style={{ display: "flex", gap: 12 }}>
            <button
              style={buttonSecondary}
              onClick={() =>
                router.push(
                  quoteSessionId
                    ? `/quote/results?quoteSessionId=${quoteSessionId}`
                    : "/",
                )
              }
            >
              Назад к тарифам
            </button>
          </div>
        </header>

        {error ? <div style={errorStyle}>{error}</div> : null}
        {successMessage ? <div style={successStyle}>{successMessage}</div> : null}

        {isBootstrapping ? (
          <div style={{ ...cardStyle, marginTop: 20 }}>
            Подготавливаем draft order...
          </div>
        ) : draft ? (
          <>
            <div
              style={{
                ...cardStyle,
                marginTop: 20,
                marginBottom: 20,
                display: "grid",
                gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                gap: 16,
              }}
            >
              <div>
                <div style={{ color: "#64748b", marginBottom: 6 }}>Draft ID</div>
                <strong>{draft.draft_id}</strong>
              </div>
              <div>
                <div style={{ color: "#64748b", marginBottom: 6 }}>Статус</div>
                <strong>{draft.status}</strong>
              </div>
              <div>
                <div style={{ color: "#64748b", marginBottom: 6 }}>Тариф</div>
                <strong>
                  {draft.carrier_name_snapshot} — {draft.tariff_name_snapshot}
                </strong>
              </div>
              <div>
                <div style={{ color: "#64748b", marginBottom: 6 }}>Стоимость</div>
                <strong>
                  {draft.price_snapshot} {draft.currency_snapshot}
                </strong>
              </div>
              <div>
                <div style={{ color: "#64748b", marginBottom: 6 }}>Срок</div>
                <strong>
                  {draft.eta_days_min_snapshot}-{draft.eta_days_max_snapshot} дн.
                </strong>
              </div>
              <div>
                <div style={{ color: "#64748b", marginBottom: 6 }}>
                  Quote session
                </div>
                <strong>{draft.quote_session_id}</strong>
              </div>
            </div>

            <form onSubmit={handleSubmit} style={{ display: "grid", gap: 20 }}>
              <div style={cardStyle}>
                <h2 style={{ marginTop: 0, marginBottom: 16, fontSize: 22 }}>
                  Отправитель
                </h2>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                    gap: 16,
                  }}
                >
                  <div>
                    <label style={labelStyle}>ФИО</label>
                    <input
                      style={inputStyle}
                      value={form.sender.full_name}
                      onChange={(e) =>
                        updatePartyField("sender", "full_name", e.target.value)
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Телефон</label>
                    <input
                      style={inputStyle}
                      value={form.sender.phone}
                      onChange={(e) =>
                        updatePartyField("sender", "phone", e.target.value)
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Email</label>
                    <input
                      style={inputStyle}
                      value={form.sender.email}
                      onChange={(e) =>
                        updatePartyField("sender", "email", e.target.value)
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Компания</label>
                    <input
                      style={inputStyle}
                      value={form.sender.company_name}
                      onChange={(e) =>
                        updatePartyField("sender", "company_name", e.target.value)
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Код страны</label>
                    <input
                      style={inputStyle}
                      value={form.sender.country}
                      onChange={(e) =>
                        updatePartyField("sender", "country", e.target.value)
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Город</label>
                    <input
                      style={inputStyle}
                      value={form.sender.city}
                      onChange={(e) =>
                        updatePartyField("sender", "city", e.target.value)
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Адрес</label>
                    <input
                      style={inputStyle}
                      value={form.sender.address_line1}
                      onChange={(e) =>
                        updatePartyField("sender", "address_line1", e.target.value)
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Доп. адрес</label>
                    <input
                      style={inputStyle}
                      value={form.sender.address_line2}
                      onChange={(e) =>
                        updatePartyField("sender", "address_line2", e.target.value)
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Почтовый индекс</label>
                    <input
                      style={inputStyle}
                      value={form.sender.postal_code}
                      onChange={(e) =>
                        updatePartyField("sender", "postal_code", e.target.value)
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Комментарий</label>
                    <input
                      style={inputStyle}
                      value={form.sender.comment}
                      onChange={(e) =>
                        updatePartyField("sender", "comment", e.target.value)
                      }
                    />
                  </div>
                </div>
              </div>

              <div style={cardStyle}>
                <h2 style={{ marginTop: 0, marginBottom: 16, fontSize: 22 }}>
                  Получатель
                </h2>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                    gap: 16,
                  }}
                >
                  <div>
                    <label style={labelStyle}>ФИО</label>
                    <input
                      style={inputStyle}
                      value={form.recipient.full_name}
                      onChange={(e) =>
                        updatePartyField("recipient", "full_name", e.target.value)
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Телефон</label>
                    <input
                      style={inputStyle}
                      value={form.recipient.phone}
                      onChange={(e) =>
                        updatePartyField("recipient", "phone", e.target.value)
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Email</label>
                    <input
                      style={inputStyle}
                      value={form.recipient.email}
                      onChange={(e) =>
                        updatePartyField("recipient", "email", e.target.value)
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Компания</label>
                    <input
                      style={inputStyle}
                      value={form.recipient.company_name}
                      onChange={(e) =>
                        updatePartyField(
                          "recipient",
                          "company_name",
                          e.target.value,
                        )
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Код страны</label>
                    <input
                      style={inputStyle}
                      value={form.recipient.country}
                      onChange={(e) =>
                        updatePartyField("recipient", "country", e.target.value)
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Город</label>
                    <input
                      style={inputStyle}
                      value={form.recipient.city}
                      onChange={(e) =>
                        updatePartyField("recipient", "city", e.target.value)
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Адрес</label>
                    <input
                      style={inputStyle}
                      value={form.recipient.address_line1}
                      onChange={(e) =>
                        updatePartyField(
                          "recipient",
                          "address_line1",
                          e.target.value,
                        )
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Доп. адрес</label>
                    <input
                      style={inputStyle}
                      value={form.recipient.address_line2}
                      onChange={(e) =>
                        updatePartyField(
                          "recipient",
                          "address_line2",
                          e.target.value,
                        )
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Почтовый индекс</label>
                    <input
                      style={inputStyle}
                      value={form.recipient.postal_code}
                      onChange={(e) =>
                        updatePartyField(
                          "recipient",
                          "postal_code",
                          e.target.value,
                        )
                      }
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Комментарий</label>
                    <input
                      style={inputStyle}
                      value={form.recipient.comment}
                      onChange={(e) =>
                        updatePartyField("recipient", "comment", e.target.value)
                      }
                    />
                  </div>
                </div>
              </div>

              <div style={cardStyle}>
                <h2 style={{ marginTop: 0, marginBottom: 16, fontSize: 22 }}>
                  Параметры отправления
                </h2>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                    gap: 16,
                  }}
                >
                  <div>
                    <label style={labelStyle}>Описание</label>
                    <input
                      style={inputStyle}
                      value={form.packageItem.description}
                      onChange={(e) =>
                        updatePackageField("description", e.target.value)
                      }
                      placeholder="Documents / Parcel / Samples"
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Количество</label>
                    <input
                      style={inputStyle}
                      value={form.packageItem.quantity}
                      onChange={(e) =>
                        updatePackageField("quantity", e.target.value)
                      }
                      inputMode="numeric"
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Вес, кг</label>
                    <input
                      style={inputStyle}
                      value={form.packageItem.weight_kg}
                      onChange={(e) =>
                        updatePackageField("weight_kg", e.target.value)
                      }
                      inputMode="decimal"
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Ширина, см</label>
                    <input
                      style={inputStyle}
                      value={form.packageItem.width_cm}
                      onChange={(e) =>
                        updatePackageField("width_cm", e.target.value)
                      }
                      inputMode="decimal"
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Высота, см</label>
                    <input
                      style={inputStyle}
                      value={form.packageItem.height_cm}
                      onChange={(e) =>
                        updatePackageField("height_cm", e.target.value)
                      }
                      inputMode="decimal"
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Глубина, см</label>
                    <input
                      style={inputStyle}
                      value={form.packageItem.depth_cm}
                      onChange={(e) =>
                        updatePackageField("depth_cm", e.target.value)
                      }
                      inputMode="decimal"
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Объявленная стоимость</label>
                    <input
                      style={inputStyle}
                      value={form.packageItem.declared_value}
                      onChange={(e) =>
                        updatePackageField("declared_value", e.target.value)
                      }
                      inputMode="decimal"
                    />
                  </div>

                  <div>
                    <label style={labelStyle}>Валюта стоимости</label>
                    <input
                      style={inputStyle}
                      value={form.packageItem.declared_value_currency}
                      onChange={(e) =>
                        updatePackageField(
                          "declared_value_currency",
                          e.target.value,
                        )
                      }
                    />
                  </div>
                </div>
              </div>

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
                  {isSubmitting
                    ? "Сохраняем..."
                    : "Сохранить данные отправления"}
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