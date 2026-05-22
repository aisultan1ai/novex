import { apiRequest } from "./client";
import type { AddressEntry, AddressEntryCreate } from "@/types/address_book";

export const listAddresses = (): Promise<AddressEntry[]> =>
  apiRequest("/profile/addresses");

export const createAddress = (body: AddressEntryCreate): Promise<AddressEntry> =>
  apiRequest("/profile/addresses", { method: "POST", body: JSON.stringify(body) });

export const deleteAddress = (id: number): Promise<void> =>
  apiRequest(`/profile/addresses/${id}`, { method: "DELETE" });
