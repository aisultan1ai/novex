import type { AddressEntry, AddressEntryCreate } from "@/types/address_book";

const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") || "/api/v1");

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    credentials: "include",
    cache: "no-store",
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error((data as { detail?: string })?.detail ?? `HTTP ${res.status}`);
  return data as T;
}

export const listAddresses = (): Promise<AddressEntry[]> =>
  req("/profile/addresses");

export const createAddress = (body: AddressEntryCreate): Promise<AddressEntry> =>
  req("/profile/addresses", { method: "POST", body: JSON.stringify(body) });

export const deleteAddress = (id: number): Promise<void> =>
  req(`/profile/addresses/${id}`, { method: "DELETE" });
