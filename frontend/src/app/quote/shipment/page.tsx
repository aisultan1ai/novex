"use client";

import type { FormEvent } from "react";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Check } from "lucide-react";

import Navbar from "@/components/layout/Navbar";
import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { ApiError, createDraftFromQuote, cseRecalcDraft, updateOrderDraftShipment } from "@/lib/api/orders";
import { fetchCsePvzByCity, type CsePvzItem } from "@/lib/api/cse";
import type { ProfileResponse } from "@/types/auth";
import type {
  DeliveryType,
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
  // Filled only when insurance=true. Backend stores it on package[0].declared_value
  // and forwards to Exline as <inshprice> / to CSE as DeclaredValueRate. Sending
  // insurance without a real value gets silently ignored by both carriers.
  declared_value: string;
  // CSE-only: chosen delivery type + PVZ GUIDs for warehouse legs. For other
  // carriers the backend ignores these and defaults to door_to_door.
  delivery_type: DeliveryType;
  sender_pvz_guid: string;
  recipient_pvz_guid: string;
};

const DELIVERY_TYPE_OPTIONS: { value: DeliveryType; label: string; hint: string }[] = [
  { value: "door_to_door",           label: "Курьер до двери",              hint: "Курьер заберёт у отправителя и привезёт получателю" },
  { value: "door_to_warehouse",      label: "Получатель заберёт из ПВЗ",    hint: "Курьер заберёт у отправителя, получатель забирает из ПВЗ CSE" },
  { value: "warehouse_to_door",      label: "Отправитель сдаст в ПВЗ",      hint: "Отправитель сам сдаёт в ПВЗ CSE, курьер привезёт получателю" },
  { value: "warehouse_to_warehouse", label: "ПВЗ → ПВЗ (оба самовывоз)",    hint: "Отправитель сдаёт в ПВЗ CSE, получатель забирает из ПВЗ CSE" },
];

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

// Standard envelope dimensions used when shipment_type is "document" — carriers
// still require positive dimensions on their APIs even for docs.
const DOCUMENT_ENVELOPE_CM = { width: 32, height: 22, depth: 1 };

function mapPackageFormToPayload(
  pkg: PackageFormState,
  declaredValue: number | null,
  isDocument: boolean,
): ShipmentPackageInput {
  const width = isDocument ? DOCUMENT_ENVELOPE_CM.width : Number(pkg.width_cm);
  const height = isDocument ? DOCUMENT_ENVELOPE_CM.height : Number(pkg.height_cm);
  const depth = isDocument ? DOCUMENT_ENVELOPE_CM.depth : Number(pkg.depth_cm);
  return {
    description: pkg.description.trim(), quantity: Number(pkg.quantity),
    weight_kg: Number(pkg.weight_kg),
    width_cm: width, height_cm: height, depth_cm: depth,
    declared_value: declaredValue,
    declared_value_currency: declaredValue !== null ? "KZT" : null,
  };
}

function buildShipmentPayload(form: ShipmentFormState, isDocument: boolean): UpdateShipmentDetailsRequest {
  const parsedDeclared = form.insurance ? Number(form.declared_value) : NaN;
  const declaredValue = Number.isFinite(parsedDeclared) && parsedDeclared > 0
    ? parsedDeclared
    : null;
  const senderWh = form.delivery_type === "warehouse_to_door" || form.delivery_type === "warehouse_to_warehouse";
  const recipientWh = form.delivery_type === "door_to_warehouse" || form.delivery_type === "warehouse_to_warehouse";
  return {
    sender: mapPartyFormToPayload(form.sender),
    recipient: mapPartyFormToPayload(form.recipient),
    packages: [mapPackageFormToPayload(form.packageItem, declaredValue, isDocument)],
    call_before_delivery: form.call_before_delivery,
    insurance: form.insurance,
    fragile: form.fragile,
    delivery_type: form.delivery_type,
    sender_pvz_guid: senderWh ? (form.sender_pvz_guid || null) : null,
    recipient_pvz_guid: recipientWh ? (form.recipient_pvz_guid || null) : null,
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
    declared_value: draft.packages[0]?.declared_value != null ? String(draft.packages[0].declared_value) : "",
    delivery_type: draft.delivery_type ?? "door_to_door",
    sender_pvz_guid: draft.sender_pvz_guid ?? "",
    recipient_pvz_guid: draft.recipient_pvz_guid ?? "",
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
  const isMobile = useIsMobile();
  return (
    <div
      style={{
        background: "#ffffff",
        border: "1px solid #E5E7EB",
        borderRadius: 16,
        padding: isMobile ? "18px" : "24px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
      }}
    >
      <h2 style={{
        font: `600 ${isMobile ? 16 : 18}px/1.2 Inter Variable, sans-serif`,
        color: "#111827",
        margin: `0 0 ${isMobile ? 16 : 20}px`,
      }}>
        {title}
      </h2>
      {children}
    </div>
  );
}

/* ─── CSE PVZ picker ─────────────────────────────────────────────────────── */

function PvzPickerSection({
  title, city, list, loading, value, onChange,
}: {
  title: string;
  city: string;
  list: CsePvzItem[];
  loading: boolean;
  value: string;
  onChange: (guid: string) => void;
}) {
  const selectStyle: React.CSSProperties = {
    width: "100%",
    padding: "12px 14px",
    border: "1px solid #E5E7EB",
    borderRadius: 10,
    background: "#ffffff",
    font: "400 14px/1.2 Inter Variable, sans-serif",
    color: "#111827",
    cursor: "pointer",
  };
  const hint = !city.trim()
    ? "Введите город выше — тогда покажем список ПВЗ."
    : loading
    ? "Загружаем список ПВЗ…"
    : list.length === 0
    ? "Для этого города нет доступных ПВЗ CSE."
    : "";
  return (
    <SectionCard title={title}>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={loading || list.length === 0}
          style={selectStyle}
        >
          <option value="">— Выберите ПВЗ —</option>
          {list.map((p) => (
            <option key={p.guid} value={p.guid}>
              {p.address}{p.schedule ? `  •  ${p.schedule}` : ""}
            </option>
          ))}
        </select>
        {hint && (
          <div style={{ font: "400 12px/1.4 Inter Variable, sans-serif", color: "#6B7280" }}>
            {hint}
          </div>
        )}
      </div>
    </SectionCard>
  );
}

/* ─── Tariff summary card ────────────────────────────────────────────────── */

function TariffSummary({
  draft, onChangeTariff, livePrice, isRecalculating,
}: {
  draft: OrderDraftResponse;
  onChangeTariff: () => void;
  livePrice?: { price: number; currency: string } | null;
  isRecalculating?: boolean;
}) {
  const displayPrice = livePrice?.price ?? draft.price_snapshot;
  const displayCurrency = livePrice?.currency ?? draft.currency_snapshot;
  const basePrice = draft.price_snapshot;
  const deltaPositive = livePrice && livePrice.price > basePrice;
  const deltaNegative = livePrice && livePrice.price < basePrice;
  const delta = livePrice ? Math.abs(livePrice.price - basePrice) : 0;
  return _TariffSummaryImpl({
    draft, onChangeTariff,
    displayPrice, displayCurrency, isRecalculating,
    deltaSign: deltaPositive ? "+" : deltaNegative ? "−" : "",
    delta,
  });
}

function _TariffSummaryImpl({
  draft, onChangeTariff, displayPrice, displayCurrency,
  isRecalculating, deltaSign, delta,
}: {
  draft: OrderDraftResponse;
  onChangeTariff: () => void;
  displayPrice: number;
  displayCurrency: string;
  isRecalculating?: boolean;
  deltaSign: string;
  delta: number;
}) {
  const isMobile = useIsMobile();
  return (
    <div
      style={{
        background: "#EFF6FF",
        border: "1.5px solid #2563EB",
        borderRadius: 16,
        padding: isMobile ? "16px" : "20px 24px",
        display: "flex",
        flexDirection: isMobile ? "column" : "row",
        justifyContent: "space-between",
        alignItems: isMobile ? "stretch" : "center",
        gap: isMobile ? 14 : 16,
        marginBottom: isMobile ? 20 : 28,
        boxShadow: "0 4px 16px rgba(37,99,235,0.10)",
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ font: "500 11px/1 Inter Variable, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: "#2563EB", marginBottom: 6 }}>
          Выбранный тариф
        </div>
        <div style={{
          font: `700 ${isMobile ? 16 : 18}px/1.2 Inter Variable, sans-serif`,
          color: "#111827", marginBottom: 4,
        }}>
          {draft.carrier_name_snapshot} · {draft.tariff_name_snapshot}
        </div>
        <div style={{ font: `400 ${isMobile ? 13 : 14}px/1.3 Inter Variable, sans-serif`, color: "#6B7280" }}>
          {draft.from_city_snapshot} → {draft.to_city_snapshot} · {draft.shipment_type_snapshot}
        </div>
      </div>
      <div style={{
        display: "flex",
        flexDirection: isMobile ? "row" : "column",
        alignItems: isMobile ? "center" : "flex-end",
        justifyContent: isMobile ? "space-between" : "flex-start",
        gap: isMobile ? 12 : 4,
        paddingTop: isMobile ? 12 : 0,
        borderTop: isMobile ? "1px solid rgba(37,99,235,0.2)" : "none",
      }}>
        <div>
          <div style={{
            font: `700 ${isMobile ? 22 : 26}px/1 Inter Variable, sans-serif`,
            color: "#111827", marginBottom: 4,
            whiteSpace: "nowrap",
            opacity: isRecalculating ? 0.5 : 1,
            transition: "opacity 0.2s",
          }}>
            {formatPrice(displayPrice, displayCurrency)}
          </div>
          {delta > 0 && !isRecalculating && (
            <div style={{
              font: `500 ${isMobile ? 11 : 12}px/1 Inter Variable, sans-serif`,
              color: deltaSign === "+" ? "#B45309" : "#059669",
              marginBottom: 4,
            }}>
              {deltaSign}{formatPrice(delta, displayCurrency)} к базовой
            </div>
          )}
          <div style={{
            font: `600 ${isMobile ? 12 : 13}px/1 Inter Variable, sans-serif`,
            color: "#2563EB",
            marginBottom: isMobile ? 0 : 12,
          }}>
            {draft.eta_days_min_snapshot}–{draft.eta_days_max_snapshot} дн.
          </div>
        </div>
        <button
          onClick={onChangeTariff}
          style={{
            border: "1.5px solid #2563EB",
            background: "#ffffff",
            color: "#2563EB",
            borderRadius: 8,
            padding: isMobile ? "8px 14px" : "7px 14px",
            font: "600 13px/1 Inter Variable, sans-serif",
            cursor: "pointer",
            fontFamily: "inherit",
            transition: "all 0.15s",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "#EFF6FF"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "#ffffff"; }}
        >
          Изменить
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

function PackageSection({ values, onChange, isDocument }: {
  values: PackageFormState;
  onChange: (key: keyof PackageFormState, value: string) => void;
  isDocument: boolean;
}) {
  const isMobile = useIsMobile();
  const baseFields: { key: keyof PackageFormState; label: string; mode?: React.HTMLAttributes<HTMLInputElement>["inputMode"] }[] = [
    { key: "description", label: "Описание содержимого" },
    { key: "quantity", label: "Количество мест", mode: "numeric" },
    { key: "weight_kg", label: "Вес, кг", mode: "decimal" },
  ];
  const dimensionFields: { key: keyof PackageFormState; label: string; mode?: React.HTMLAttributes<HTMLInputElement>["inputMode"] }[] = [
    { key: "width_cm", label: "Ширина, см", mode: "decimal" },
    { key: "height_cm", label: "Высота, см", mode: "decimal" },
    { key: "depth_cm", label: "Глубина, см", mode: "decimal" },
  ];
  const fields = isDocument ? baseFields : [...baseFields, ...dimensionFields];

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
      {isDocument && (
        <div style={{
          marginTop: 12,
          padding: "10px 14px",
          background: "#F0F9FF",
          border: "1px solid #BAE6FD",
          borderRadius: 10,
          font: "400 12px/1.4 Inter Variable, sans-serif",
          color: "#0369A1",
        }}>
          Для документов используется стандартный размер конверта (32×22×1 см).
        </div>
      )}
    </SectionCard>
  );
}

/* ─── Page ───────────────────────────────────────────────────────────────── */

function ShipmentPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { currentUser, isAuthenticated, isLoading, logout } = useAuth();
  const isMobile = useIsMobile();

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
    try {
      const raw = sessionStorage.getItem(storageKey);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as Partial<ShipmentFormState>;
      // Backfill fields that may be missing from forms cached before their addition.
      // Without this, sessionStorage from an older build silently strips fields.
      return {
        sender: parsed.sender ?? emptyParty(),
        recipient: parsed.recipient ?? emptyParty(),
        packageItem: parsed.packageItem ?? emptyPackage(),
        call_before_delivery: parsed.call_before_delivery ?? false,
        insurance: parsed.insurance ?? false,
        fragile: parsed.fragile ?? false,
        declared_value: parsed.declared_value ?? "",
        delivery_type: parsed.delivery_type ?? "door_to_door",
        sender_pvz_guid: parsed.sender_pvz_guid ?? "",
        recipient_pvz_guid: parsed.recipient_pvz_guid ?? "",
      };
    } catch { return null; }
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
    () => loadSavedForm() ?? { sender: emptyParty(), recipient: emptyParty(), packageItem: emptyPackage(), call_before_delivery: false, insurance: false, fragile: false, declared_value: "", delivery_type: "door_to_door", sender_pvz_guid: "", recipient_pvz_guid: "" },
  );

  const [draft, setDraft] = useState<OrderDraftResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  // Cached PVZ lists per side; keyed by (side, city) so switching city refreshes.
  const [senderPvzList, setSenderPvzList] = useState<CsePvzItem[]>([]);
  const [recipientPvzList, setRecipientPvzList] = useState<CsePvzItem[]>([]);
  const [pvzLoading, setPvzLoading] = useState<{ sender: boolean; recipient: boolean }>({ sender: false, recipient: false });

  // Live recalc: whenever the customer toggles insurance / delivery_type /
  // declared_value, ask the backend for the fully-loaded final price so the
  // number shown next to "Продолжить к оплате" matches CSE billing.
  const [livePrice, setLivePrice] = useState<{ price: number; currency: string } | null>(null);
  const [isRecalculating, setIsRecalculating] = useState(false);

  const isCse = (draft?.carrier_code_snapshot ?? "").toLowerCase() === "cse";
  const senderLegWh = form.delivery_type === "warehouse_to_door" || form.delivery_type === "warehouse_to_warehouse";
  const recipientLegWh = form.delivery_type === "door_to_warehouse" || form.delivery_type === "warehouse_to_warehouse";

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace(`/login?next=${encodeURIComponent(fullNextUrl)}`);
    }
  }, [fullNextUrl, isAuthenticated, isLoading, router]);

  useEffect(() => {
    if (!currentUser) return;
    setForm((prev) => ({ ...prev, sender: mergeSenderWithCurrentUser(prev.sender, currentUser) }));
  }, [currentUser]);

  // Fetch sender-side PVZ list when it's needed and the city is known.
  useEffect(() => {
    if (!isCse || !senderLegWh) { setSenderPvzList([]); return; }
    const city = form.sender.city.trim();
    if (!city) { setSenderPvzList([]); return; }
    const ac = new AbortController();
    setPvzLoading((p) => ({ ...p, sender: true }));
    fetchCsePvzByCity(city, ac.signal)
      .then((list) => setSenderPvzList(list))
      .catch(() => { /* network error → keep list empty; UI will show hint */ })
      .finally(() => setPvzLoading((p) => ({ ...p, sender: false })));
    return () => ac.abort();
  }, [isCse, senderLegWh, form.sender.city]);

  useEffect(() => {
    if (!isCse || !recipientLegWh) { setRecipientPvzList([]); return; }
    const city = form.recipient.city.trim();
    if (!city) { setRecipientPvzList([]); return; }
    const ac = new AbortController();
    setPvzLoading((p) => ({ ...p, recipient: true }));
    fetchCsePvzByCity(city, ac.signal)
      .then((list) => setRecipientPvzList(list))
      .catch(() => { /* keep empty */ })
      .finally(() => setPvzLoading((p) => ({ ...p, recipient: false })));
    return () => ac.abort();
  }, [isCse, recipientLegWh, form.recipient.city]);

  // Clear stale PVZ selections when the user switches delivery type away from
  // a leg that needed a PVZ. Prevents sending an unrelated GUID to backend.
  useEffect(() => {
    if (!senderLegWh && form.sender_pvz_guid) {
      updateForm((prev) => ({ ...prev, sender_pvz_guid: "" }));
    }
    if (!recipientLegWh && form.recipient_pvz_guid) {
      updateForm((prev) => ({ ...prev, recipient_pvz_guid: "" }));
    }
    // Only reacts to delivery_type change; ignore linter's dependency nag.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.delivery_type]);

  // Debounced recalc — asks CSE for the final price including add-on services.
  // Only fires when the draft is CSE and at least one price-affecting option
  // is set. 500ms debounce so we don't hammer CSE while the user is typing.
  useEffect(() => {
    if (!draft) return;
    if (!isCse) { setLivePrice(null); return; }
    const rawDeclared = form.insurance ? Number(form.declared_value) : NaN;
    const declaredValue = Number.isFinite(rawDeclared) && rawDeclared > 0 ? rawDeclared : null;
    // If nothing that affects price is set, just clear the override.
    const hasExtras = form.delivery_type !== "door_to_door" || form.insurance || (declaredValue !== null);
    if (!hasExtras) { setLivePrice(null); return; }

    const ac = new AbortController();
    const timer = setTimeout(() => {
      setIsRecalculating(true);
      cseRecalcDraft(draft.draft_id, {
        delivery_type: form.delivery_type,
        insurance: form.insurance,
        declared_value: declaredValue,
      }, ac.signal)
        .then((r) => {
          if (r.recalculated) setLivePrice({ price: Number(r.price), currency: r.currency });
        })
        .catch(() => { /* silent — TariffSummary falls back to draft.price_snapshot */ })
        .finally(() => setIsRecalculating(false));
    }, 500);

    return () => { clearTimeout(timer); ac.abort(); };
  }, [draft, isCse, form.delivery_type, form.insurance, form.declared_value]);

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
    updateForm((prev) => {
      const next = { ...prev, [key]: val };
      // Reset declared_value when insurance is turned off so a stale amount
      // does not silently persist in sessionStorage / draft.
      if (key === "insurance" && !val) next.declared_value = "";
      return next;
    });
  }
  function updateDeclaredValue(value: string) {
    // Allow only digits and one decimal separator.
    const cleaned = value.replace(",", ".").replace(/[^\d.]/g, "");
    const parts = cleaned.split(".");
    const normalized = parts.length > 2 ? `${parts[0]}.${parts.slice(1).join("")}` : cleaned;
    updateForm((prev) => ({ ...prev, declared_value: normalized }));
  }
  function updatePackageField(key: keyof PackageFormState, value: string) {
    // Russian keyboards default to "," on the decimal key. Normalize to "."
    // for weight/dimension fields so users can type either separator.
    const numericKeys: readonly (keyof PackageFormState)[] = [
      "weight_kg", "width_cm", "height_cm", "depth_cm",
    ];
    const normalized = numericKeys.includes(key) ? value.replace(",", ".") : value;
    updateForm((prev) => ({ ...prev, packageItem: { ...prev.packageItem, [key]: normalized } }));
  }

  function isValidKzPhone(raw: string): boolean {
    const digits = raw.replace(/[\s\-()]/g, "");
    return /^(\+?7|8)[0-9]{10}$/.test(digits);
  }

  function validateStep(step: number): string | null {
    if (step === 0) {
      const p = form.packageItem;
      if (!p.description.trim()) return "Введите описание содержимого.";
      const qty = Number(p.quantity);
      if (!p.quantity || isNaN(qty) || qty <= 0 || !Number.isInteger(qty)) return "Укажите корректное количество мест.";
      const w = Number(p.weight_kg);
      if (!p.weight_kg || isNaN(w) || w <= 0) return "Укажите корректный вес.";
      const isDocument = (draft?.shipment_type_snapshot ?? "").toLowerCase() === "document";
      if (!isDocument) {
        const wd = Number(p.width_cm), h = Number(p.height_cm), d = Number(p.depth_cm);
        if (!p.width_cm || isNaN(wd) || wd <= 0) return "Укажите ширину.";
        if (!p.height_cm || isNaN(h) || h <= 0) return "Укажите высоту.";
        if (!p.depth_cm || isNaN(d) || d <= 0) return "Укажите глубину.";
      }
      if (form.insurance) {
        const dv = Number(form.declared_value);
        if (!form.declared_value || isNaN(dv) || dv <= 0) {
          return "Укажите объявленную ценность для страхования.";
        }
      }
    }
    if (step === 1) {
      const s = form.sender;
      if (!s.full_name.trim()) return "Укажите ФИО отправителя.";
      if (!s.phone.trim()) return "Укажите телефон отправителя.";
      if (!isValidKzPhone(s.phone)) return "Телефон отправителя: формат +7XXXXXXXXXX или 8XXXXXXXXXX.";
      if (!s.country.trim() || s.country.trim().length !== 2) return "Код страны - 2 буквы (например KZ).";
      if (!s.city.trim()) return "Укажите город отправителя.";
      if (!s.address_line1.trim()) return "Укажите адрес отправителя.";
      if (isCse && senderLegWh && !form.sender_pvz_guid) {
        return "Выберите ПВЗ отправителя (для выбранного типа доставки).";
      }
    }
    if (step === 2) {
      const r = form.recipient;
      if (!r.full_name.trim()) return "Укажите ФИО получателя.";
      if (!r.phone.trim()) return "Укажите телефон получателя.";
      if (!isValidKzPhone(r.phone)) return "Телефон получателя: формат +7XXXXXXXXXX или 8XXXXXXXXXX.";
      if (!r.country.trim() || r.country.trim().length !== 2) return "Код страны - 2 буквы (например KZ).";
      if (!r.city.trim()) return "Укажите город получателя.";
      if (!r.address_line1.trim()) return "Укажите адрес получателя.";
      if (isCse && recipientLegWh && !form.recipient_pvz_guid) {
        return "Выберите ПВЗ получателя (для выбранного типа доставки).";
      }
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
      const isDocument = (draft.shipment_type_snapshot ?? "").toLowerCase() === "document";
      await updateOrderDraftShipment(draft.draft_id, buildShipmentPayload(form, isDocument));
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

      <main style={{
        maxWidth: 860, margin: "0 auto",
        padding: isMobile ? "20px 16px 40px" : "40px 20px 80px",
      }}>
        {/* Page title */}
        <div style={{ marginBottom: isMobile ? 20 : 32 }}>
          <div style={{
            display: "flex", justifyContent: "space-between",
            alignItems: "center", flexWrap: "wrap",
            gap: isMobile ? 10 : 12,
            marginBottom: isMobile ? 20 : 32,
          }}>
            <h1 style={{
              font: `700 ${isMobile ? 20 : 28}px/1.2 Inter Variable, sans-serif`,
              letterSpacing: "-0.02em", color: "#111827", margin: 0,
              flex: 1, minWidth: 0,
            }}>
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
                padding: isMobile ? "8px 14px" : "10px 18px",
                font: `600 ${isMobile ? 13 : 14}px/1 Inter Variable, sans-serif`,
                cursor: "pointer",
                fontFamily: "inherit",
                transition: "background 0.15s",
                whiteSpace: "nowrap",
                flexShrink: 0,
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#F9FAFB")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "#ffffff")}
            >
              ← Назад
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
              livePrice={livePrice}
              isRecalculating={isRecalculating}
            />

            {/* Shipment form */}
            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 20 }}>

              {/* ── Step 0: Данные отправления ── */}
              {currentStep === 0 && (
                <>
                  <PackageSection
                    values={form.packageItem}
                    onChange={updatePackageField}
                    isDocument={(draft?.shipment_type_snapshot ?? "").toLowerCase() === "document"}
                  />
                  {isCse && (
                    <SectionCard title="Тип доставки">
                      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                        {DELIVERY_TYPE_OPTIONS.map((opt) => (
                          <label key={opt.value} style={{ display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer" }}>
                            <input
                              type="radio"
                              name="delivery_type"
                              value={opt.value}
                              checked={form.delivery_type === opt.value}
                              onChange={() => updateForm((prev) => ({ ...prev, delivery_type: opt.value }))}
                              style={{ marginTop: 3, width: 16, height: 16, cursor: "pointer", accentColor: "#2563EB" }}
                            />
                            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                              <span style={{ font: "500 14px/1.3 Inter Variable, sans-serif", color: "#111827" }}>{opt.label}</span>
                              <span style={{ font: "400 12px/1.4 Inter Variable, sans-serif", color: "#6B7280" }}>{opt.hint}</span>
                            </div>
                          </label>
                        ))}
                        {(senderLegWh || recipientLegWh) && (
                          <div style={{ marginTop: 4, padding: 10, background: "#F3F4F6", borderRadius: 8, font: "400 12px/1.4 Inter Variable, sans-serif", color: "#6B7280" }}>
                            ПВЗ выбирается на следующих шагах, после заполнения города{senderLegWh && recipientLegWh ? " отправителя и получателя" : senderLegWh ? " отправителя" : " получателя"}.
                          </div>
                        )}
                      </div>
                    </SectionCard>
                  )}
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
                      {form.insurance && (
                        <div style={{ marginTop: 4, paddingTop: 12, borderTop: "1px dashed #E5E7EB" }}>
                          <FormField
                            label="Объявленная ценность, ₸"
                            value={form.declared_value}
                            onChange={updateDeclaredValue}
                            required
                            inputMode="decimal"
                          />
                          <div style={{ marginTop: 6, font: "400 12px/1.4 Inter Variable, sans-serif", color: "#6B7280" }}>
                            Сумма, на которую будет застрахован груз. Передаётся перевозчику при отправке.
                          </div>
                        </div>
                      )}
                    </div>
                  </SectionCard>
                </>
              )}

              {/* ── Step 1: Отправитель ── */}
              {currentStep === 1 && (
                <>
                  <PartySection
                    title="Отправитель"
                    values={form.sender}
                    onChange={(key, val) => updatePartyField("sender", key, val)}
                    onToggleSave={(val) => toggleSaveAddress("sender", val)}
                  />
                  {isCse && senderLegWh && (
                    <PvzPickerSection
                      title="ПВЗ отправителя (CSE)"
                      city={form.sender.city}
                      list={senderPvzList}
                      loading={pvzLoading.sender}
                      value={form.sender_pvz_guid}
                      onChange={(guid) => updateForm((prev) => ({ ...prev, sender_pvz_guid: guid }))}
                    />
                  )}
                </>
              )}

              {/* ── Step 2: Получатель ── */}
              {currentStep === 2 && (
                <>
                  <PartySection
                    title="Получатель"
                    values={form.recipient}
                    onChange={(key, val) => updatePartyField("recipient", key, val)}
                    onToggleSave={(val) => toggleSaveAddress("recipient", val)}
                  />
                  {isCse && recipientLegWh && (
                    <PvzPickerSection
                      title="ПВЗ получателя (CSE)"
                      city={form.recipient.city}
                      list={recipientPvzList}
                      loading={pvzLoading.recipient}
                      value={form.recipient_pvz_guid}
                      onChange={(guid) => updateForm((prev) => ({ ...prev, recipient_pvz_guid: guid }))}
                    />
                  )}
                </>
              )}

              {/* Navigation */}
              <div style={{
                display: "flex",
                flexDirection: isMobile ? "column-reverse" : "row",
                justifyContent: "space-between",
                alignItems: isMobile ? "stretch" : "center",
                gap: isMobile ? 10 : 12,
                marginTop: 8,
              }}>
                <button
                  type="button"
                  onClick={currentStep === 0 ? () => router.push("/") : handlePrevStep}
                  style={{
                    background: isMobile ? "#ffffff" : "none",
                    border: isMobile ? "1px solid #E5E7EB" : "none",
                    borderRadius: isMobile ? 10 : 0,
                    color: "#6B7280",
                    font: "500 14px/1 Inter Variable, sans-serif",
                    cursor: "pointer",
                    fontFamily: "inherit",
                    padding: isMobile ? "12px 20px" : 0,
                    width: isMobile ? "100%" : "auto",
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
                      padding: isMobile ? "14px 24px" : "14px 32px",
                      font: "600 15px/1 Inter Variable, sans-serif",
                      cursor: "pointer",
                      fontFamily: "inherit",
                      transition: "background 0.15s",
                      width: isMobile ? "100%" : "auto",
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
                      padding: isMobile ? "14px 24px" : "14px 32px",
                      font: "600 15px/1 Inter Variable, sans-serif",
                      cursor: isSubmitting ? "not-allowed" : "pointer",
                      fontFamily: "inherit",
                      transition: "background 0.15s",
                      width: isMobile ? "100%" : "auto",
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
