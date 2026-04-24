"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";

import { calculateShippingQuote, ApiError } from "@/lib/api/shipping";
import type { ShipmentType, ShippingQuoteRequest } from "@/types/quote";

type FormState = {
  from_city: string;
  to_city: string;
  shipment_type: ShipmentType;
  weight_kg: string;
  quantity: string;
  width_cm: string;
  height_cm: string;
  depth_cm: string;
};

const initial: FormState = {
  from_city: "Алматы",
  to_city: "Астана",
  shipment_type: "parcel",
  weight_kg: "2.5",
  quantity: "1",
  width_cm: "20",
  height_cm: "15",
  depth_cm: "10",
};

export default function ShortQuoteForm() {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(initial);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof FormState>(key: K, val: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: val }));
  }

  function toPayload(): ShippingQuoteRequest {
    return {
      from_country: "KZ",
      from_city: form.from_city.trim(),
      to_country: "KZ",
      to_city: form.to_city.trim(),
      shipment_type: form.shipment_type,
      weight_kg: Number(form.weight_kg),
      quantity: Number(form.quantity),
      width_cm: Number(form.width_cm),
      height_cm: Number(form.height_cm),
      depth_cm: Number(form.depth_cm),
    };
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await calculateShippingQuote(toPayload());
      router.push(`/quote/results?quoteSessionId=${result.quote_session_id}`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : "Не удалось рассчитать тарифы.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  const inp: React.CSSProperties = {
    width: "100%",
    padding: "11px 14px",
    borderRadius: 10,
    border: "1.5px solid #e5e7eb",
    fontSize: 15,
    outline: "none",
    boxSizing: "border-box",
    color: "#111827",
    background: "#fff",
    fontFamily: "inherit",
    transition: "border-color 0.15s",
  };

  const lbl: React.CSSProperties = {
    display: "block",
    fontSize: 12,
    fontWeight: 600,
    color: "#6b7280",
    marginBottom: 6,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Route row */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 36px 1fr",
          gap: 0,
          alignItems: "end",
          marginBottom: 20,
        }}
      >
        <div>
          <label style={lbl}>Откуда</label>
          <input
            style={inp}
            value={form.from_city}
            onChange={(e) => set("from_city", e.target.value)}
            placeholder="Город отправки"
            required
          />
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            paddingBottom: 2,
            color: "#9ca3af",
            fontSize: 20,
          }}
        >
          →
        </div>

        <div>
          <label style={lbl}>Куда</label>
          <input
            style={inp}
            value={form.to_city}
            onChange={(e) => set("to_city", e.target.value)}
            placeholder="Город доставки"
            required
          />
        </div>
      </div>

      {/* Shipment type toggle */}
      <div style={{ marginBottom: 20 }}>
        <label style={lbl}>Что отправляете</label>
        <div style={{ display: "flex", gap: 8 }}>
          {(
            [
              { value: "parcel", label: "Посылка" },
              { value: "document", label: "Документ" },
            ] as { value: ShipmentType; label: string }[]
          ).map(({ value, label }) => {
            const active = form.shipment_type === value;
            return (
              <button
                key={value}
                type="button"
                onClick={() => set("shipment_type", value)}
                style={{
                  padding: "9px 20px",
                  borderRadius: 10,
                  border: active ? "1.5px solid #111827" : "1.5px solid #e5e7eb",
                  background: active ? "#111827" : "#fff",
                  color: active ? "#fff" : "#6b7280",
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: "pointer",
                  fontFamily: "inherit",
                  transition: "all 0.15s",
                }}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Parameters row */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr 1fr 1fr",
          gap: 10,
          marginBottom: 24,
        }}
      >
        <div>
          <label style={lbl}>Вес, кг</label>
          <input
            style={inp}
            value={form.weight_kg}
            onChange={(e) => set("weight_kg", e.target.value)}
            inputMode="decimal"
            placeholder="2.5"
            required
          />
        </div>
        <div>
          <label style={lbl}>Кол-во</label>
          <input
            style={inp}
            value={form.quantity}
            onChange={(e) => set("quantity", e.target.value)}
            inputMode="numeric"
            placeholder="1"
            required
          />
        </div>
        <div>
          <label style={lbl}>Ширина, см</label>
          <input
            style={inp}
            value={form.width_cm}
            onChange={(e) => set("width_cm", e.target.value)}
            inputMode="decimal"
            placeholder="20"
            required
          />
        </div>
        <div>
          <label style={lbl}>Высота, см</label>
          <input
            style={inp}
            value={form.height_cm}
            onChange={(e) => set("height_cm", e.target.value)}
            inputMode="decimal"
            placeholder="15"
            required
          />
        </div>
        <div>
          <label style={lbl}>Глубина, см</label>
          <input
            style={inp}
            value={form.depth_cm}
            onChange={(e) => set("depth_cm", e.target.value)}
            inputMode="decimal"
            placeholder="10"
            required
          />
        </div>
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={isSubmitting}
        style={{
          width: "100%",
          padding: "14px 24px",
          borderRadius: 12,
          border: "none",
          background: isSubmitting ? "#6b7280" : "#111827",
          color: "#fff",
          fontSize: 15,
          fontWeight: 700,
          cursor: isSubmitting ? "not-allowed" : "pointer",
          fontFamily: "inherit",
          letterSpacing: "-0.2px",
          transition: "background 0.15s",
        }}
      >
        {isSubmitting ? "Рассчитываем..." : "Рассчитать тарифы →"}
      </button>

      {error && (
        <div
          style={{
            marginTop: 12,
            padding: "12px 14px",
            borderRadius: 10,
            background: "#fef2f2",
            border: "1px solid #fecaca",
            color: "#b91c1c",
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}
    </form>
  );
}
