import { apiRequest, ApiError } from "./client";

export { ApiError };

export interface ReviewCreate {
  rating: number;
  comment?: string | null;
}

export interface ReviewResponse {
  id: number;
  order_draft_id: number;
  user_id: number;
  carrier_code: string;
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface ReviewListResponse {
  items: ReviewResponse[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface CarrierRatingSummary {
  carrier_code: string;
  avg_rating: number;
  count: number;
}

export async function getOrderReview(
  orderDraftId: number,
): Promise<ReviewResponse | null> {
  return apiRequest<ReviewResponse | null>(`/orders/${orderDraftId}/review`);
}

export async function createReview(
  orderDraftId: number,
  payload: ReviewCreate,
): Promise<ReviewResponse> {
  return apiRequest<ReviewResponse>(`/orders/${orderDraftId}/review`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listAdminReviews(params?: {
  carrier_code?: string;
  page?: number;
  size?: number;
}): Promise<ReviewListResponse> {
  const qs = new URLSearchParams();
  if (params?.carrier_code) qs.set("carrier_code", params.carrier_code);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.size) qs.set("size", String(params.size));
  return apiRequest<ReviewListResponse>(`/admin/reviews?${qs.toString()}`);
}

export async function getAdminRatingsSummary(): Promise<CarrierRatingSummary[]> {
  return apiRequest<CarrierRatingSummary[]>("/admin/reviews/ratings");
}
