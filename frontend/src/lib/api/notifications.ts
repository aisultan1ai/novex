import { apiRequest } from "./client";
import type { NotificationListResponse } from "@/types/notifications";

export const listNotifications = (): Promise<NotificationListResponse> =>
  apiRequest("/notifications");

export const markNotificationRead = (id: number): Promise<void> =>
  apiRequest(`/notifications/${id}/read`, { method: "PATCH" });

export const markAllNotificationsRead = (): Promise<{ marked_read: number }> =>
  apiRequest("/notifications/read-all", { method: "POST" });
