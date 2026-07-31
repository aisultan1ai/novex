import { apiRequest } from "./client";

export type CancellationStatus = "pending" | "approved" | "api_cancelled" | "rejected";

export interface CancellationRequestFull {
  id: number;
  order_draft_id: number;
  requested_by_user_id: number;
  carrier_code: string;
  reason: string;
  status: CancellationStatus;
  api_attempted: boolean;
  api_error: string | null;
  carrier_response: string | null;
  resolved_by_user_id: number | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CancellationListResponse {
  items: CancellationRequestFull[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// ── Admin ─────────────────────────────────────────────────────────────────

export const adminListCancellations = (params: {
  status?: CancellationStatus;
  carrier_code?: string;
  page?: number;
  size?: number;
} = {}): Promise<CancellationListResponse> => {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.carrier_code) qs.set("carrier_code", params.carrier_code);
  qs.set("page", String(params.page ?? 1));
  qs.set("size", String(params.size ?? 20));
  return apiRequest(`/admin/cancellation-requests?${qs.toString()}`);
};

export const adminGetCancellation = (id: number): Promise<CancellationRequestFull> =>
  apiRequest(`/admin/cancellation-requests/${id}`);

export const adminApproveCancellation = (id: number, comment?: string): Promise<CancellationRequestFull> =>
  apiRequest(`/admin/cancellation-requests/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ comment: comment ?? null }),
  });

export const adminRejectCancellation = (id: number, comment: string): Promise<CancellationRequestFull> =>
  apiRequest(`/admin/cancellation-requests/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });

export const adminRetryApiCancellation = (id: number): Promise<CancellationRequestFull> =>
  apiRequest(`/admin/cancellation-requests/${id}/retry-api`, { method: "POST" });

// ── Carrier ───────────────────────────────────────────────────────────────

export const carrierListCancellations = (params: {
  status?: CancellationStatus;
  page?: number;
  size?: number;
} = {}): Promise<CancellationListResponse> => {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  qs.set("page", String(params.page ?? 1));
  qs.set("size", String(params.size ?? 20));
  return apiRequest(`/carrier/cancellation-requests?${qs.toString()}`);
};

export const carrierGetCancellation = (id: number): Promise<CancellationRequestFull> =>
  apiRequest(`/carrier/cancellation-requests/${id}`);

export const carrierApproveCancellation = (id: number, comment?: string): Promise<CancellationRequestFull> =>
  apiRequest(`/carrier/cancellation-requests/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ comment: comment ?? null }),
  });

export const carrierRejectCancellation = (id: number, comment: string): Promise<CancellationRequestFull> =>
  apiRequest(`/carrier/cancellation-requests/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
