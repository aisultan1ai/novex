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
