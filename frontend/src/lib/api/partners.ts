import { apiRequest } from "./client";

export type PartnerIntegrationType = "api" | "manual" | "unsure";

export interface PartnerApplicationPayload {
  company_name: string;
  contact_name: string;
  phone: string;
  email: string;
  cities?: string | null;
  integration_type: PartnerIntegrationType;
  comment?: string | null;
  consent: boolean;
}

export async function submitPartnerApplication(
  payload: PartnerApplicationPayload,
): Promise<{ ok: boolean; message: string }> {
  return apiRequest<{ ok: boolean; message: string }>("/partners/apply", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
