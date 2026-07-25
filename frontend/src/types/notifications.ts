export interface Notification {
  id: number;
  user_id: number;
  type: string;
  title: string;
  body: string | null;
  // Relative path the client should navigate to (e.g. /dashboard/orders/1042).
  // Null for legacy rows or system messages with no canonical target.
  link_url: string | null;
  is_read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  items: Notification[];
  unread_count: number;
}
