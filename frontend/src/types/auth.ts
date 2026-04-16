export type RoleCode = "customer" | "admin" | "operator";
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
  role: RoleCode;
  customer_type: CustomerType;
  company_name: string | null;
  billing_mode: BillingMode;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  profile: ProfileResponse;
}