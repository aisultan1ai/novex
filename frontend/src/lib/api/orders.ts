import { apiRequest, ApiError } from "./client";
import type {
  CancelOrderResponse,
  CreateDraftFromQuoteRequest,
  DeliveryType,
  OrderDraftResponse,
  UpdateShipmentDetailsRequest,
  OrderDraftListResponse,
} from "@/types/order";

export interface CseRecalcRequest {
  delivery_type: DeliveryType;
  insurance: boolean;
  declared_value?: number | null;
  weight_kg?: number | null;
  width_cm?: number | null;
  height_cm?: number | null;
  depth_cm?: number | null;
  quantity?: number | null;
}

export interface CseRecalcResponse {
  price: number;          // customer-facing (with markup)
  carrier_price: number;
  currency: string;
  recalculated: boolean;  // false for non-CSE drafts
}

export async function cseRecalcDraft(
  draftId: number,
  payload: CseRecalcRequest,
  signal?: AbortSignal,
): Promise<CseRecalcResponse> {
  return apiRequest<CseRecalcResponse>(`/orders/drafts/${draftId}/cse-recalc`, {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ?? "/api/v1";

export { ApiError };

export async function createDraftFromQuote(
  payload: CreateDraftFromQuoteRequest,
): Promise<OrderDraftResponse> {
  return apiRequest<OrderDraftResponse>("/orders/drafts/from-quote", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getOrderDraft(
  draftId: number,
): Promise<OrderDraftResponse> {
  return apiRequest<OrderDraftResponse>(`/orders/drafts/${draftId}`, {
    method: "GET",
  });
}

export async function updateOrderDraftShipment(
  draftId: number,
  payload: UpdateShipmentDetailsRequest,
): Promise<OrderDraftResponse> {
  return apiRequest<OrderDraftResponse>(`/orders/drafts/${draftId}/shipment`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function proceedToCheckout(
  draftId: number,
): Promise<OrderDraftResponse> {
  return apiRequest<OrderDraftResponse>(`/orders/drafts/${draftId}/checkout`, {
    method: "POST",
  });
}

export async function mockPayOrderDraft(
  draftId: number,
): Promise<OrderDraftResponse> {
  return apiRequest<OrderDraftResponse>(`/orders/drafts/${draftId}/pay/mock`, {
    method: "POST",
  });
}

export async function deleteOrderDraft(draftId: number): Promise<void> {
  await apiRequest<null>(`/orders/drafts/${draftId}`, { method: "DELETE" });
}

export async function cancelOrder(
  orderId: number,
  reason: string,
): Promise<CancelOrderResponse> {
  return apiRequest<CancelOrderResponse>(`/orders/${orderId}/cancel`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export const CANCELLABLE_STATUSES: readonly string[] = [
  "paid",
  "dispatch_queued",
  "dispatch_failed",
  "pending_manual",
  "pending_manual_dispatch",
  "sent_to_carrier",
];

export async function listOrders(
  page = 1,
  size = 20,
  statuses?: readonly string[],
): Promise<OrderDraftListResponse> {
  const qs = new URLSearchParams();
  qs.set("page", String(page));
  qs.set("size", String(size));
  if (statuses && statuses.length > 0) {
    qs.set("statuses", statuses.join(","));
  }
  return apiRequest<OrderDraftListResponse>(
    `/orders?${qs.toString()}`,
    { method: "GET" },
  );
}

export async function downloadOrderLabel(draftId: number): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/orders/${draftId}/label`, {
    method: "GET",
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) {
    // Try to extract backend's detail message (e.g. "Накладная ещё формируется у перевозчика.").
    let detail = `Не удалось скачать накладную (${response.status})`;
    try {
      const ct = response.headers.get("content-type") ?? "";
      if (ct.includes("application/json")) {
        const body = await response.json();
        if (typeof body?.detail === "string") detail = body.detail;
      }
    } catch {
      // fall back to default
    }
    throw new ApiError(response.status, detail);
  }
  return response.blob();
}
