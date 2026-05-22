import { apiRequest } from "./client";
import type {
  CarrierWebhookConfig,
  CarrierWebhookCreate,
  CarrierWebhookUpdate,
  DispatchQueueItem,
  TestResult,
} from "@/types/carrier_webhooks";

export const getCarrierWebhooks = (): Promise<CarrierWebhookConfig[]> =>
  apiRequest("/admin/carrier-webhooks");

export const createCarrierWebhook = (data: CarrierWebhookCreate): Promise<CarrierWebhookConfig> =>
  apiRequest("/admin/carrier-webhooks", { method: "POST", body: JSON.stringify(data) });

export const updateCarrierWebhook = (carrier_code: string, data: CarrierWebhookUpdate): Promise<CarrierWebhookConfig> =>
  apiRequest(`/admin/carrier-webhooks/${carrier_code}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteCarrierWebhook = (carrier_code: string): Promise<void> =>
  apiRequest(`/admin/carrier-webhooks/${carrier_code}`, { method: "DELETE" });

export const testCarrierWebhook = (carrier_code: string): Promise<TestResult> =>
  apiRequest(`/admin/carrier-webhooks/${carrier_code}/test`, { method: "POST" });

export const getDispatchQueue = (): Promise<{ items: DispatchQueueItem[]; total: number }> =>
  apiRequest("/admin/orders/dispatch-queue");

export const retryDispatch = (draft_id: number): Promise<{ ok: boolean; tracking_number: string | null }> =>
  apiRequest(`/admin/orders/${draft_id}/retry-dispatch`, { method: "POST" });

export const markDispatched = (
  draft_id: number,
  tracking_number: string,
): Promise<{ id: number; status: string; carrier_tracking_number: string }> =>
  apiRequest(`/admin/orders/${draft_id}/mark-dispatched`, {
    method: "POST",
    body: JSON.stringify({ tracking_number }),
  });
