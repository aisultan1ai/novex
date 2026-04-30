import { getAuthHeaders } from "@/lib/auth/session";
import type {
  AdminCarrier, AdminCarrierDetail, AdminCarrierService,
  AdminOrderDetail, AdminOrderRow, AdminStats,
  AdminTariffRate, AdminUser, AdminUserDetail,
  PaginatedResponse,
} from "@/types/admin";

const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") || "/api/v1");

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...getAuthHeaders(), ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error((data as { detail?: string })?.detail ?? `HTTP ${res.status}`);
  return data as T;
}

async function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: form,
    cache: "no-store",
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error((data as { detail?: string })?.detail ?? `HTTP ${res.status}`);
  return data as T;
}

// ── Stats ─────────────────────────────────────────────────────────────────────
export const getAdminStats = (): Promise<AdminStats> =>
  req("/admin/users/stats");

// ── Users ─────────────────────────────────────────────────────────────────────
export const listAdminUsers = (params: { page?: number; size?: number; search?: string } = {}): Promise<PaginatedResponse<AdminUser>> => {
  const q = new URLSearchParams();
  if (params.page) q.set("page", String(params.page));
  if (params.size) q.set("size", String(params.size));
  if (params.search) q.set("search", params.search);
  return req(`/admin/users?${q}`);
};

export const getAdminUser = (id: number): Promise<AdminUserDetail> =>
  req(`/admin/users/${id}`);

export const updateAdminUser = (id: number, body: { is_active: boolean }): Promise<{ id: number; is_active: boolean }> =>
  req(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(body) });

// ── Orders ────────────────────────────────────────────────────────────────────
export const listAdminOrders = (params: { page?: number; size?: number; status?: string; user_id?: number } = {}): Promise<PaginatedResponse<AdminOrderRow>> => {
  const q = new URLSearchParams();
  if (params.page) q.set("page", String(params.page));
  if (params.size) q.set("size", String(params.size));
  if (params.status) q.set("status", params.status);
  if (params.user_id) q.set("user_id", String(params.user_id));
  return req(`/admin/orders?${q}`);
};

export const getAdminOrder = (id: number): Promise<AdminOrderDetail> =>
  req(`/admin/orders/${id}`);

export const updateOrderStatus = (id: number, status: string): Promise<{ id: number; status: string }> =>
  req(`/admin/orders/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) });

// ── Carriers ──────────────────────────────────────────────────────────────────
export const listAdminCarriers = (): Promise<AdminCarrier[]> =>
  req("/admin/carriers");

export const createAdminCarrier = (body: { code: string; name: string; description?: string; is_active?: boolean }): Promise<AdminCarrier> =>
  req("/admin/carriers", { method: "POST", body: JSON.stringify(body) });

export const getAdminCarrier = (id: number): Promise<AdminCarrierDetail> =>
  req(`/admin/carriers/${id}`);

export const updateAdminCarrier = (id: number, body: { name?: string; description?: string; is_active?: boolean }): Promise<AdminCarrier> =>
  req(`/admin/carriers/${id}`, { method: "PATCH", body: JSON.stringify(body) });

// Services
export const createAdminService = (carrierId: number, body: { code: string; name: string; shipment_type?: string }): Promise<AdminCarrierService> =>
  req(`/admin/carriers/${carrierId}/services`, { method: "POST", body: JSON.stringify(body) });

// Rates
export const listAdminRates = (carrierId: number, serviceId: number): Promise<AdminTariffRate[]> =>
  req(`/admin/carriers/${carrierId}/services/${serviceId}/rates`);

export const deleteAdminRate = (carrierId: number, serviceId: number, rateId: number): Promise<void> =>
  req(`/admin/carriers/${carrierId}/services/${serviceId}/rates/${rateId}`, { method: "DELETE" });

export const uploadTariffGrid = (carrierId: number, serviceId: number, file: File): Promise<{ inserted: number }> =>
  upload(`/admin/carriers/${carrierId}/services/${serviceId}/rates/upload`, file);
