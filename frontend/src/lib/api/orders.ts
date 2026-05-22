import { apiRequest, ApiError } from "./client";
import type {
  CreateDraftFromQuoteRequest,
  OrderDraftResponse,
  UpdateShipmentDetailsRequest,
  OrderDraftListResponse,
} from "@/types/order";

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

export async function listOrders(
  page = 1,
  size = 20,
): Promise<OrderDraftListResponse> {
  return apiRequest<OrderDraftListResponse>(
    `/orders?page=${page}&size=${size}`,
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
    throw new ApiError(response.status, `Не удалось скачать накладную (${response.status})`);
  }
  return response.blob();
}
