import { apiRequest, ApiError, safeFetch } from "./client";
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

const PROFILE_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ?? "/api/v1";

/**
 * Background profile sync used by AuthProvider. Unlike getProfile() it never
 * throws and never triggers the global "session expired" redirect — a stale
 * browser session on a public page must not bounce the visitor to /login.
 */
export async function fetchProfileQuietly(): Promise<ProfileResponse | null> {
  try {
    const res = await safeFetch(`${PROFILE_BASE_URL}/auth/profile`, {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as ProfileResponse;
  } catch {
    return null;
  }
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
