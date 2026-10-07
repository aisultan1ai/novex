import { apiRequest, ApiError, responseToApiError, safeFetch } from "./client";
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

// Not paid yet: the customer cancels instantly (no request, nothing to refund).
// `payment_under_review` is deliberately absent — a proof is uploaded, so it is
// an operator decision.
export const UNPAID_CANCELLABLE_STATUSES: readonly string[] = [
  "shipment_details_completed",
  "ready_for_checkout",
  "awaiting_payment",
  "payment_rejected",
];

export const CANCELLABLE_STATUSES: readonly string[] = [
  "paid",
  "dispatch_queued",
  "dispatch_failed",
  "pending_manual",
  "pending_manual_dispatch",
  "sent_to_carrier",
];

// Statuses at which the customer can still change the courier pickup
// date/time. Beyond `picked_up` the parcel is with the courier already.
export const RESCHEDULE_PICKUP_STATUSES: readonly string[] = [
  "dispatch_queued",
  "sent_to_carrier",
  "dispatch_failed",
];

export interface ReschedulePickupRequest {
  pickup_date: string;      // YYYY-MM-DD
  pickup_time_slot: string; // free-form label, e.g. "10:00-14:00"
}

export interface ReschedulePickupResponse {
  outcome: "rescheduled" | "already_scheduled_new";
  order: OrderDraftResponse;
}

export async function reschedulePickup(
  orderId: number,
  payload: ReschedulePickupRequest,
): Promise<ReschedulePickupResponse> {
  return apiRequest<ReschedulePickupResponse>(
    `/orders/${orderId}/reschedule-pickup`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

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
  const response = await safeFetch(`${API_BASE_URL}/orders/${draftId}/label`, {
    method: "GET",
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) {
    // e.g. 409/404 «Накладная ещё формируется у перевозчика.»
    throw await responseToApiError(response);
  }
  return response.blob();
}
