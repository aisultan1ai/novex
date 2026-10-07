import type { ShippingQuoteResponse } from "@/types/quote";

/**
 * The home page calculator state (cities, weight, dimensions + the tariff list)
 * is kept in sessionStorage so «Назад» from the order form — the browser button,
 * «На главную» or «Изменить тариф» — returns to the same calculation instead of
 * an empty form. Cleared once the shipment details are saved (the calculation
 * has then become an order).
 */
const KEY = "novex_home_quote";
const MAX_AGE_MS = 3 * 60 * 60 * 1000; // quote sessions are short-lived anyway

export interface HomeQuoteForm {
  fromCity: string;
  toCity: string;
  shipmentType: "parcel" | "document";
  weightKg: string;
  quantity: string;
  widthCm: string;
  heightCm: string;
  depthCm: string;
}

export interface HomeQuoteSnapshot {
  savedAt: number;
  form: HomeQuoteForm;
  results: ShippingQuoteResponse | null;
}

export function saveHomeQuote(form: HomeQuoteForm, results: ShippingQuoteResponse | null): void {
  try {
    const snapshot: HomeQuoteSnapshot = { savedAt: Date.now(), form, results };
    sessionStorage.setItem(KEY, JSON.stringify(snapshot));
  } catch {
    /* private mode / quota — restoring is a convenience, never required */
  }
}

export function loadHomeQuote(): HomeQuoteSnapshot | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const snapshot = JSON.parse(raw) as HomeQuoteSnapshot;
    if (!snapshot?.form || typeof snapshot.savedAt !== "number") return null;
    if (Date.now() - snapshot.savedAt > MAX_AGE_MS) {
      sessionStorage.removeItem(KEY);
      return null;
    }
    return snapshot;
  } catch {
    return null;
  }
}

export function clearHomeQuote(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
