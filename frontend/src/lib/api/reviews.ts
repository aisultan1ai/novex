const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") || "/api/v1";

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

class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    credentials: "include",
    cache: "no-store",
  });
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const detail =
      typeof data === "object" && data !== null && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : `Request failed with status ${response.status}`;
    throw new ApiError(response.status, detail);
  }
  return data as T;
}

export async function getOrderReview(
  orderDraftId: number,
): Promise<ReviewResponse | null> {
  const data = await request<ReviewResponse | null>(`/orders/${orderDraftId}/review`);
  return data ?? null;
}

export async function createReview(
  orderDraftId: number,
  payload: ReviewCreate,
): Promise<ReviewResponse> {
  return request<ReviewResponse>(`/orders/${orderDraftId}/review`, {
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
  return request<ReviewListResponse>(`/admin/reviews?${qs.toString()}`);
}

export async function getAdminRatingsSummary(): Promise<CarrierRatingSummary[]> {
  return request<CarrierRatingSummary[]>("/admin/reviews/ratings");
}

export { ApiError };
