import { apiRequest } from "./client";
import type { CarrierMeResponse, IntegrationConfig } from "@/types/carrier";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ?? "/api/v1";

export const getCarrierMe = (): Promise<CarrierMeResponse> =>
  apiRequest("/carrier/me");

export const getIntegrationConfig = (): Promise<IntegrationConfig> =>
  apiRequest("/carrier/integration-config");

export interface CarrierOrderParty {
  role: string;
  full_name: string;
  phone: string;
  city: string;
  address_line1: string;
  address_line2: string | null;
  postal_code: string | null;
  comment: string | null;
}

export interface CarrierOrderPackage {
  description: string;
  quantity: number;
  weight_kg: number;
  width_cm: number;
  height_cm: number;
  depth_cm: number;
  declared_value: number | null;
  declared_value_currency: string | null;
}

export interface CarrierOrderPod {
  id: number;
  file_url: string;
  file_name: string;
  mime_type: string;
  created_at: string;
}

export interface CarrierOrderItem {
  id: number;
  status: string;
  carrier_code: string;
  tariff_name: string;
  price: number;
  currency: string;
  from_city: string;
  to_city: string;
  eta_days_min: number;
  eta_days_max: number;
  created_at: string;
  parties: CarrierOrderParty[];
  packages: CarrierOrderPackage[];
  proof_of_delivery?: CarrierOrderPod[];
  tracking_events?: { status: string; description: string | null; location: string | null; occurred_at: string }[];
}

export interface CarrierOrdersResponse {
  items: CarrierOrderItem[];
  total: number;
  page: number;
  size: number;
}

export const listCarrierOrders = (params: { status?: string; page?: number; size?: number } = {}): Promise<CarrierOrdersResponse> => {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.page) q.set("page", String(params.page));
  if (params.size) q.set("size", String(params.size));
  return apiRequest(`/carrier/orders?${q}`);
};

export const getCarrierOrder = (orderId: number): Promise<CarrierOrderItem> =>
  apiRequest(`/carrier/orders/${orderId}`);

export const acceptCarrierOrder = async (orderId: number): Promise<{ order_id: number; status: string; message: string }> => {
  const res = await fetch(`${BASE}/carrier/orders/${orderId}/accept`, {
    method: "POST",
    credentials: "include",
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
  return data;
};

export const rejectCarrierOrder = async (orderId: number, reason: string): Promise<{ order_id: number; status: string; message: string }> => {
  const form = new FormData();
  form.append("reason", reason);
  const res = await fetch(`${BASE}/carrier/orders/${orderId}/reject`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
  return data;
};

export const uploadCarrierPod = async (orderId: number, file: File): Promise<{ document_id: number; file_url: string; file_name: string; order_status: string; message: string }> => {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/carrier/orders/${orderId}/pod`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
  return data;
};
