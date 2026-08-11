"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "@/lib/api/notifications";
import type { Notification } from "@/types/notifications";

function formatDateTime(iso: string) {
  // Backend returns naive UTC without 'Z' - append it so browser parses as UTC, not local
  const d = new Date(/[Z+]/.test(iso) ? iso : iso + "Z");
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "только что";
  if (diffMin < 60) return `${diffMin} мин. назад`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH} ч. назад`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 7) return `${diffD} дн. назад`;
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "short" });
}

const TYPE_ICONS: Record<string, string> = {
  order_status: "📦",
  payment:      "💳",
  system:       "🔔",
};

export default function NotificationsPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const isMobile = useIsMobile();

  const [items, setItems] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [markingAll, setMarkingAll] = useState(false);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push("/login");
  }, [isAuthenticated, authLoading, router]);

  useEffect(() => {
    if (!isAuthenticated) return;
    listNotifications()
      .then((res) => { setItems(res.items); setUnread(res.unread_count); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, [isAuthenticated]);

  async function handleMarkRead(id: number) {
    try {
      await markNotificationRead(id);
      setItems((prev) => prev.map((n) => n.id === id ? { ...n, is_read: true } : n));
      setUnread((prev) => Math.max(0, prev - 1));
    } catch {
      // silent
    }
  }

  // Row click: navigate to the linked entity (if any) AND fire the read
  // toggle. We optimistically mark-read first so navigation is not delayed by
  // the PATCH round-trip.
  function handleRowClick(n: Notification) {
    if (!n.is_read) void handleMarkRead(n.id);
    if (n.link_url) router.push(n.link_url);
  }

  async function handleMarkAll() {
    setMarkingAll(true);
    try {
      await markAllNotificationsRead();
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnread(0);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setMarkingAll(false);
    }
  }

  if (authLoading || (!isAuthenticated && !authLoading)) return null;

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: isMobile ? 22 : 28, fontWeight: 800, color: "#0E1826" }}>
            Уведомления
          </h1>
          {unread > 0 && (
            <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>
              {unread} непрочитанных
            </p>
          )}
        </div>
        {unread > 0 && (
          <button
            onClick={() => void handleMarkAll()}
            disabled={markingAll}
            style={{
              padding: isMobile ? "8px 14px" : "9px 18px",
              borderRadius: 10,
              border: "1px solid #E2E8EE",
              background: "#ffffff",
              color: "#475569",
              fontSize: isMobile ? 12 : 13,
              fontWeight: 500,
              cursor: markingAll ? "not-allowed" : "pointer",
              opacity: markingAll ? 0.6 : 1,
              fontFamily: "inherit",
            }}
          >
            {markingAll ? "Обновляем…" : isMobile ? "Прочитать все" : "Отметить все прочитанными"}
          </button>
        )}
      </div>

      {error && (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 10, padding: "12px 16px", color: "#b91c1c", fontSize: 14, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {isLoading ? (
        <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>
          Загружаем уведомления…
        </div>
      ) : items.length === 0 ? (
        <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, padding: "64px 24px", textAlign: "center" }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🔔</div>
          <p style={{ fontSize: 16, fontWeight: 700, margin: "0 0 6px", color: "#0E1826" }}>
            Уведомлений пока нет
          </p>
          <p style={{ margin: 0, fontSize: 14, color: "#64748b" }}>
            Здесь будут появляться обновления по вашим заказам
          </p>
        </div>
      ) : (
        <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, overflow: "hidden" }}>
          {items.map((n, idx) => {
            const isLast = idx === items.length - 1;
            const icon = TYPE_ICONS[n.type] ?? "🔔";
            // Row is clickable when it has a target OR is still unread -
            // either action counts as user intent. Fully read + no link is
            // rendered as static text.
            const clickable = Boolean(n.link_url) || !n.is_read;
            return (
              <div
                key={n.id}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: isMobile ? 12 : 16,
                  padding: isMobile ? "14px 16px" : "18px 24px",
                  borderBottom: isLast ? "none" : "1px solid #f1f5f9",
                  background: n.is_read ? "#ffffff" : "#f8faff",
                  cursor: clickable ? "pointer" : "default",
                  transition: "background 0.1s",
                }}
                onClick={() => { if (clickable) handleRowClick(n); }}
              >
                <div style={{ fontSize: 22, flexShrink: 0, marginTop: 1 }}>{icon}</div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, marginBottom: 4 }}>
                    <div style={{ fontSize: 14, fontWeight: n.is_read ? 500 : 700, color: "#0E1826" }}>
                      {n.title}
                    </div>
                    <div style={{ fontSize: 12, color: "#94a3b8", whiteSpace: "nowrap", flexShrink: 0 }}>
                      {formatDateTime(n.created_at)}
                    </div>
                  </div>
                  {n.body && (
                    <div style={{ fontSize: 13, color: "#475569" }}>{n.body}</div>
                  )}
                </div>

                {!n.is_read && (
                  <div
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: "#3b82f6",
                      flexShrink: 0,
                      marginTop: 6,
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
