import type { ProfileResponse } from "@/types/auth";

const AUTH_PROFILE_STORAGE_KEY = "novex_auth_profile";

// Only non-sensitive fields (id, email, role) - phone, billing, company stay server-side
interface StoredData {
  user_id: number;
  email: string;
  full_name: string | null;
  role: string;
  carrier_id: number | null;
  expires_at: number | null;
}

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

export function saveAuthSession(profile: ProfileResponse, expiresIn?: number): void {
  if (!isBrowser()) return;
  const stored: StoredData = {
    user_id: profile.user_id,
    email: profile.email,
    full_name: profile.full_name,
    role: profile.role,
    carrier_id: profile.carrier_id,
    expires_at: expiresIn ? Date.now() + expiresIn * 1000 : null,
  };
  window.localStorage.setItem(AUTH_PROFILE_STORAGE_KEY, JSON.stringify(stored));
}

export function getStoredCurrentUser(): ProfileResponse | null {
  if (!isBrowser()) return null;

  const raw = window.localStorage.getItem(AUTH_PROFILE_STORAGE_KEY);
  if (!raw) return null;

  try {
    const stored = JSON.parse(raw) as StoredData;
    if (!stored.user_id || !stored.email || !stored.role) return null;
    // Reconstruct ProfileResponse - sensitive fields (phone, company, billing) are
    // not stored locally and must be fetched from the API when needed
    return {
      user_id: stored.user_id,
      email: stored.email,
      full_name: stored.full_name ?? null,
      phone: null,
      is_active: true,
      role: stored.role as ProfileResponse["role"],
      customer_type: null,
      company_name: null,
      tax_id: null,
      billing_mode: null,
      carrier_id: stored.carrier_id ?? null,
    };
  } catch {
    return null;
  }
}

export function getSessionExpiresAt(): number | null {
  if (!isBrowser()) return null;
  const raw = window.localStorage.getItem(AUTH_PROFILE_STORAGE_KEY);
  if (!raw) return null;
  try {
    const stored = JSON.parse(raw) as StoredData;
    return stored.expires_at ?? null;
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
