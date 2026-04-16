import type { ProfileResponse } from "@/types/auth";

export const ACCESS_TOKEN_STORAGE_KEY = "novex_access_token";
export const AUTH_PROFILE_STORAGE_KEY = "novex_auth_profile";

export interface StoredAuthSession {
  accessToken: string | null;
  profile: ProfileResponse | null;
}

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

export function saveAuthSession(
  accessToken: string,
  profile: ProfileResponse,
): void {
  if (!isBrowser()) return;

  window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, accessToken);
  window.localStorage.setItem(
    AUTH_PROFILE_STORAGE_KEY,
    JSON.stringify(profile),
  );
}

export function getAccessToken(): string | null {
  if (!isBrowser()) return null;
  return window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
}

export function getStoredCurrentUser(): ProfileResponse | null {
  if (!isBrowser()) return null;

  const raw = window.localStorage.getItem(AUTH_PROFILE_STORAGE_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as ProfileResponse;
  } catch {
    return null;
  }
}

export function getAuthSession(): StoredAuthSession {
  return {
    accessToken: getAccessToken(),
    profile: getStoredCurrentUser(),
  };
}

export function clearAuthSession(): void {
  if (!isBrowser()) return;

  window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
  window.localStorage.removeItem(AUTH_PROFILE_STORAGE_KEY);
}

export function isAuthenticated(): boolean {
  return Boolean(getAccessToken());
}

export function getAuthHeaders(): HeadersInit {
  const token = getAccessToken();

  if (!token) {
    return {};
  }

  return {
    Authorization: `Bearer ${token}`,
  };
}