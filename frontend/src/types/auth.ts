export type RoleCode = "customer" | "admin" | "operator" | "carrier";
export type CustomerType = "individual" | "company";
export type BillingMode = "prepaid" | "postpaid";

export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string | null;
  phone?: string | null;
  customer_type: CustomerType;
  company_name?: string | null;
  billing_mode?: BillingMode | null;
  tax_id: string;
  pd_consent: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface ProfileResponse {
  user_id: number;
  email: string;
  full_name: string | null;
  phone: string | null;
  is_active: boolean;
  email_verified: boolean;
  role: RoleCode;
  customer_type: CustomerType | null;
  company_name: string | null;
  tax_id: string | null;
  billing_mode: BillingMode | null;
  carrier_id: number | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  profile: ProfileResponse;
}