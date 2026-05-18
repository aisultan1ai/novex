import type { ProfileResponse } from "@/types/auth";

const AUTH_PROFILE_STORAGE_KEY = "novex_auth_profile";

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

export function saveAuthSession(profile: ProfileResponse): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(AUTH_PROFILE_STORAGE_KEY, JSON.stringify(profile));
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

export function clearAuthSession(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(AUTH_PROFILE_STORAGE_KEY);
}

export function isAuthenticated(): boolean {
  return Boolean(getStoredCurrentUser());
}
