
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") || "/api/v1";

export type CommissionType = "percentage" | "fixed" | "combined";

export interface CommissionConfigResponse {
  id: number;
  carrier_code: string;
  commission_type: CommissionType;
  commission_rate: string | null;
  fixed_amount: string | null;
  currency: string;
}

export interface CommissionConfigUpsert {
  commission_type: CommissionType;
  commission_rate?: number | null;
  fixed_amount?: number | null;
  currency: string;
}

class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
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

export async function listCommissionConfigs(): Promise<CommissionConfigResponse[]> {
  return request<CommissionConfigResponse[]>("/admin/commission-configs");
}

export async function upsertCommissionConfig(
  carrierCode: string,
  payload: CommissionConfigUpsert,
): Promise<CommissionConfigResponse> {
  return request<CommissionConfigResponse>(`/admin/commission-configs/${carrierCode}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteCommissionConfig(carrierCode: string): Promise<void> {
  await fetch(`${API_BASE_URL}/admin/commission-configs/${carrierCode}`, {
    method: "DELETE",
    credentials: "include",
    cache: "no-store",
  });
}

export { ApiError };
