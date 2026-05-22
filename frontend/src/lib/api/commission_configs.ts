import { apiRequest, ApiError } from "./client";

export { ApiError };

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

export async function listCommissionConfigs(): Promise<CommissionConfigResponse[]> {
  return apiRequest<CommissionConfigResponse[]>("/admin/commission-configs");
}

export async function upsertCommissionConfig(
  carrierCode: string,
  payload: CommissionConfigUpsert,
): Promise<CommissionConfigResponse> {
  return apiRequest<CommissionConfigResponse>(`/admin/commission-configs/${carrierCode}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteCommissionConfig(carrierCode: string): Promise<void> {
  await apiRequest(`/admin/commission-configs/${carrierCode}`, { method: "DELETE" });
}
