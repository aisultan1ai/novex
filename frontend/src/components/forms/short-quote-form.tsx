"use client";

import type { CSSProperties, FormEvent } from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";

import { calculateShippingQuote, ApiError } from "@/lib/api/shipping";
import type { ShipmentType, ShippingQuoteRequest } from "@/types/quote";

type FormState = {
  from_country: string;
  from_city: string;
  to_country: string;
  to_city: string;
  shipment_type: ShipmentType;
  weight_kg: string;
  quantity: string;
  width_cm: string;
  height_cm: string;
  depth_cm: string;
};

const cardSectionTitleStyle: CSSProperties = {
  margin: "0 0 8px",
  fontSize: 24,
};

const cardSectionTextStyle: CSSProperties = {
  margin: 0,
  color: "#64748b",
  fontSize: 14,
  lineHeight: 1.6,
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

const formStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  gap: 16,
};

const labelStyle: CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 600,
  marginBottom: 8,
  color: "#334155",
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

const buttonPrimary: CSSProperties = {
  background: "#0f172a",
  color: "#ffffff",
  border: "none",
  borderRadius: 12,
  padding: "12px 18px",
  fontSize: 14,
  fontWeight: 600,
  cursor: "pointer",
};

const errorStyle: CSSProperties = {
  marginTop: 8,
  padding: "10px 12px",
  borderRadius: 12,
  background: "#fef2f2",
  color: "#b91c1c",
  fontSize: 13,
  lineHeight: 1.5,
};

const helperStyle: CSSProperties = {
  marginTop: 8,
  color: "#64748b",
  fontSize: 12,
  lineHeight: 1.5,
};

const initialState: FormState = {
  from_country: "KZ",
  from_city: "Almaty",
  to_country: "KZ",
  to_city: "Astana",
  shipment_type: "parcel",
  weight_kg: "2.5",
  quantity: "1",
  width_cm: "20",
  height_cm: "15",
  depth_cm: "10",
};

export default function ShortQuoteForm() {
  const router = useRouter();

  const [form, setForm] = useState<FormState>(initialState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function toPayload(): ShippingQuoteRequest {
    return {
      from_country: form.from_country.trim().toUpperCase(),
      from_city: form.from_city.trim(),
      to_country: form.to_country.trim().toUpperCase(),
      to_city: form.to_city.trim(),
      shipment_type: form.shipment_type,
      weight_kg: Number(form.weight_kg),
      quantity: Number(form.quantity),
      width_cm: Number(form.width_cm),
      height_cm: Number(form.height_cm),
      depth_cm: Number(form.depth_cm),
    };
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const payload = toPayload();
      const result = await calculateShippingQuote(payload);
      router.push(`/quote/results?quoteSessionId=${result.quote_session_id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Не удалось рассчитать тарифы.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 16,
          flexWrap: "wrap",
          alignItems: "center",
          marginBottom: 24,
        }}
      >
        <div>
          <h2 style={cardSectionTitleStyle}>Короткая форма отправления</h2>
          <p style={cardSectionTextStyle}>
            Форма рассчитывает тарифы через backend API и перенаправляет на
            страницу результатов по `quoteSessionId`.
          </p>
        </div>
        <span style={badgeStyle}>Quote flow</span>
      </div>

      <form onSubmit={handleSubmit} style={formStyle}>
        <div>
          <label style={labelStyle}>Откуда: код страны</label>
          <input
            style={inputStyle}
            value={form.from_country}
            onChange={(e) => updateField("from_country", e.target.value)}
            placeholder="KZ"
            maxLength={2}
          />
          <div style={helperStyle}>Используй 2-буквенный код, например KZ.</div>
        </div>

        <div>
          <label style={labelStyle}>Откуда: город</label>
          <input
            style={inputStyle}
            value={form.from_city}
            onChange={(e) => updateField("from_city", e.target.value)}
            placeholder="Almaty"
          />
        </div>

        <div>
          <label style={labelStyle}>Куда: код страны</label>
          <input
            style={inputStyle}
            value={form.to_country}
            onChange={(e) => updateField("to_country", e.target.value)}
            placeholder="KZ"
            maxLength={2}
          />
          <div style={helperStyle}>Используй 2-буквенный код, например KZ.</div>
        </div>

        <div>
          <label style={labelStyle}>Куда: город</label>
          <input
            style={inputStyle}
            value={form.to_city}
            onChange={(e) => updateField("to_city", e.target.value)}
            placeholder="Astana"
          />
        </div>

        <div>
          <label style={labelStyle}>Тип отправления</label>
          <select
            style={inputStyle}
            value={form.shipment_type}
            onChange={(e) =>
              updateField("shipment_type", e.target.value as ShipmentType)
            }
          >
            <option value="parcel">Посылка</option>
            <option value="document">Документ</option>
          </select>
        </div>

        <div>
          <label style={labelStyle}>Вес, кг</label>
          <input
            style={inputStyle}
            value={form.weight_kg}
            onChange={(e) => updateField("weight_kg", e.target.value)}
            inputMode="decimal"
            placeholder="2.5"
          />
        </div>

        <div>
          <label style={labelStyle}>Количество</label>
          <input
            style={inputStyle}
            value={form.quantity}
            onChange={(e) => updateField("quantity", e.target.value)}
            inputMode="numeric"
            placeholder="1"
          />
        </div>

        <div>
          <label style={labelStyle}>Ширина, см</label>
          <input
            style={inputStyle}
            value={form.width_cm}
            onChange={(e) => updateField("width_cm", e.target.value)}
            inputMode="decimal"
            placeholder="20"
          />
        </div>

        <div>
          <label style={labelStyle}>Высота, см</label>
          <input
            style={inputStyle}
            value={form.height_cm}
            onChange={(e) => updateField("height_cm", e.target.value)}
            inputMode="decimal"
            placeholder="15"
          />
        </div>

        <div>
          <label style={labelStyle}>Глубина, см</label>
          <input
            style={inputStyle}
            value={form.depth_cm}
            onChange={(e) => updateField("depth_cm", e.target.value)}
            inputMode="decimal"
            placeholder="10"
          />
        </div>

        <div style={{ gridColumn: "1 / -1", marginTop: 8 }}>
          <button
            style={{
              ...buttonPrimary,
              opacity: isSubmitting ? 0.7 : 1,
              cursor: isSubmitting ? "not-allowed" : "pointer",
            }}
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Рассчитываем..." : "Рассчитать тарифы"}
          </button>
        </div>
      </form>

      {error ? <div style={errorStyle}>{error}</div> : null}
    </>
  );
}