import { getAuthHeaders } from "@/lib/auth/session";
import type {
  CreateDraftFromQuoteRequest,
  OrderDraftResponse,
  UpdateShipmentDetailsRequest, OrderDraftListResponse,
} from "@/types/order";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") || "/api/v1";

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function parseJsonSafely(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return null;
  }

  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  const data = await parseJsonSafely(response);

  if (!response.ok) {
    const detail =
      typeof data === "object" &&
      data !== null &&
      "detail" in data &&
      typeof (data as { detail?: unknown }).detail === "string"
        ? (data as { detail: string }).detail
        : `Request failed with status ${response.status}`;

    throw new ApiError(response.status, detail);
  }

  return data as T;
}

export async function createDraftFromQuote(
  payload: CreateDraftFromQuoteRequest,
): Promise<OrderDraftResponse> {
  return request<OrderDraftResponse>("/orders/drafts/from-quote", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getOrderDraft(
  draftId: number,
): Promise<OrderDraftResponse> {
  return request<OrderDraftResponse>(`/orders/drafts/${draftId}`, {
    method: "GET",
  });
}

export async function updateOrderDraftShipment(
  draftId: number,
  payload: UpdateShipmentDetailsRequest,
): Promise<OrderDraftResponse> {
  return request<OrderDraftResponse>(`/orders/drafts/${draftId}/shipment`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function listOrders(): Promise<OrderDraftListResponse> {
  const token = getToken();
  const res = await fetch(`${API_BASE}/orders`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail ?? "Не удалось получить список заказов.");
  }

  return res.json() as Promise<OrderDraftListResponse>;
}

export { ApiError };