import { apiRequest, ApiError } from "./client";
import type {
  LoginRequest,
  ProfileResponse,
  RegisterRequest,
  TokenResponse,
} from "@/types/auth";

export { ApiError };

export async function registerUser(
  payload: RegisterRequest,
): Promise<ProfileResponse> {
  return apiRequest<ProfileResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function loginUser(payload: LoginRequest): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function logoutUser(): Promise<void> {
  await apiRequest("/auth/logout", { method: "POST" });
}

export async function getProfile(): Promise<ProfileResponse> {
  return apiRequest<ProfileResponse>("/auth/profile", { method: "GET" });
}

export async function updateProfile(payload: {
  full_name?: string | null;
  phone?: string | null;
  company_name?: string | null;
  tax_id?: string | null;
}): Promise<ProfileResponse> {
  return apiRequest<ProfileResponse>("/auth/profile", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function forgotPassword(email: string): Promise<void> {
  await apiRequest("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(token: string, new_password: string): Promise<void> {
  await apiRequest("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, new_password }),
  });
}

export async function changePassword(payload: {
  current_password: string;
  new_password: string;
}): Promise<void> {
  await apiRequest("/profile/change-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function verifyEmail(token: string): Promise<void> {
  await apiRequest("/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export async function resendVerificationEmail(): Promise<void> {
  await apiRequest("/auth/resend-verification", { method: "POST" });
}
