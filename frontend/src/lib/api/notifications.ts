import { getAuthHeaders } from "@/lib/auth/session";
import type { NotificationListResponse } from "@/types/notifications";

const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") || "/api/v1");

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...getAuthHeaders(), ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error((data as { detail?: string })?.detail ?? `HTTP ${res.status}`);
  return data as T;
}

export const listNotifications = (): Promise<NotificationListResponse> =>
  req("/notifications");

export const markNotificationRead = (id: number): Promise<void> =>
  req(`/notifications/${id}/read`, { method: "PATCH" });

export const markAllNotificationsRead = (): Promise<{ marked_read: number }> =>
  req("/notifications/read-all", { method: "POST" });
