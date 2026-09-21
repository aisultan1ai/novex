import { apiRequest } from "./client";

export interface CsePvzItem {
  guid: string;
  address: string;
  city: string;
  lat: string;
  lon: string;
  schedule: string;
  phone: string;
  type: string;
}

// Fetches CSE PVZ list filtered by city name. Backend resolves the CSE
// geography GUID and caches it, so subsequent calls for the same city are
// cheap. Returns [] when the city can't be resolved (e.g. non-KZ city).
export async function fetchCsePvzByCity(city: string, signal?: AbortSignal): Promise<CsePvzItem[]> {
  const params = new URLSearchParams({ city });
  return apiRequest<CsePvzItem[]>(`/carriers/cse/pvz?${params.toString()}`, {
    method: "GET",
    signal,
  });
}

// ── Delivery info / available dates ─────────────────────────────────────

export interface CseAvailableSlot {
  from: string; // "HH:MM"
  to: string;
}
export interface CseAvailableDate {
  date: string; // ISO date "YYYY-MM-DD" or datetime
  slots: CseAvailableSlot[];
}

export interface CseDeliveryInfo {
  min_days: number | null;
  max_days: number | null;
  cod_available: boolean;
  card_available: boolean;
  services: Array<{ guid: string; name: string }>;
}

// Server accepts either a raw CSE geography GUID or a `postcode-KZ-XXXXXX`
// value. Consumer typically passes the postcode form from
// cityToPostcode() in the shipment form — same identifier the backend
// uses for the Calc call.
export async function fetchCseDeliveryInfo(
  fromGeo: string,
  toGeo: string,
  signal?: AbortSignal,
): Promise<CseDeliveryInfo> {
  const params = new URLSearchParams({ from_geo: fromGeo, to_geo: toGeo });
  return apiRequest<CseDeliveryInfo>(`/carriers/cse/delivery-info?${params.toString()}`, {
    method: "GET",
    signal,
  });
}

export async function fetchCseTakeDates(
  fromGeo: string,
  signal?: AbortSignal,
): Promise<CseAvailableDate[]> {
  const params = new URLSearchParams({ from_geo: fromGeo });
  return apiRequest<CseAvailableDate[]>(`/carriers/cse/take-dates?${params.toString()}`, {
    method: "GET",
    signal,
  });
}

export async function fetchCseDeliveryDates(
  fromGeo: string,
  toGeo: string,
  signal?: AbortSignal,
): Promise<CseAvailableDate[]> {
  const params = new URLSearchParams({ from_geo: fromGeo, to_geo: toGeo });
  return apiRequest<CseAvailableDate[]>(`/carriers/cse/delivery-dates?${params.toString()}`, {
    method: "GET",
    signal,
  });
}
