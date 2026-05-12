import { getAuthHeaders } from "@/lib/auth/session";
import type {
  CarrierWebhookConfig,
  CarrierWebhookCreate,
  CarrierWebhookUpdate,
  DispatchQueueItem,
  TestResult,
} from "@/types/carrier_webhooks";

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

export const getCarrierWebhooks = (): Promise<CarrierWebhookConfig[]> =>
  req("/admin/carrier-webhooks");

export const createCarrierWebhook = (data: CarrierWebhookCreate): Promise<CarrierWebhookConfig> =>
  req("/admin/carrier-webhooks", { method: "POST", body: JSON.stringify(data) });

export const updateCarrierWebhook = (carrier_code: string, data: CarrierWebhookUpdate): Promise<CarrierWebhookConfig> =>
  req(`/admin/carrier-webhooks/${carrier_code}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteCarrierWebhook = (carrier_code: string): Promise<void> =>
  req(`/admin/carrier-webhooks/${carrier_code}`, { method: "DELETE" });

export const testCarrierWebhook = (carrier_code: string): Promise<TestResult> =>
  req(`/admin/carrier-webhooks/${carrier_code}/test`, { method: "POST" });

export const getDispatchQueue = (): Promise<{ items: DispatchQueueItem[]; total: number }> =>
  req("/admin/orders/dispatch-queue");

export const retryDispatch = (draft_id: number): Promise<{ ok: boolean; tracking_number: string | null }> =>
  req(`/admin/orders/${draft_id}/retry-dispatch`, { method: "POST" });

export const markDispatched = (
  draft_id: number,
  tracking_number: string,
): Promise<{ id: number; status: string; carrier_tracking_number: string }> =>
  req(`/admin/orders/${draft_id}/mark-dispatched`, {
    method: "POST",
    body: JSON.stringify({ tracking_number }),
  });
