"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { getWorkCounters, type WorkCounters } from "@/lib/api/admin";

type BadgeKey = keyof Pick<WorkCounters, "payment_review" | "cancellation_pending">;

const ALL_ADMIN_TABS: { label: string; href: string; adminOnly: boolean; badge?: BadgeKey }[] = [
  { label: "Обзор",           href: "/dashboard/admin",                adminOnly: false },
  { label: "Заказы",          href: "/dashboard/admin/orders",         adminOnly: false, badge: "payment_review" },
  { label: "Заявки на отмену", href: "/dashboard/admin/cancellations", adminOnly: false, badge: "cancellation_pending" },
  { label: "Пользователи",    href: "/dashboard/admin/users",          adminOnly: false },
  { label: "Перевозчики",     href: "/dashboard/admin/carriers",       adminOnly: false },
  { label: "Отзывы",          href: "/dashboard/admin/reviews",        adminOnly: true  },
  { label: "Комиссии",        href: "/dashboard/admin/commissions",    adminOnly: false },
  { label: "Очередь заказов", href: "/dashboard/admin/dispatch-queue", adminOnly: false },
  { label: "Настройки",       href: "/dashboard/admin/settings",       adminOnly: false },
  { label: "Аудит",           href: "/dashboard/admin/audit-logs",     adminOnly: true  },
];

// Sections usable from a phone: the desk, orders (check a payment proof,
// confirm / reject) and cancellation requests. Everything else stays
// desktop-only — wide tables and tariff editors don't fit a phone.
const MOBILE_PATHS = ["/dashboard/admin", "/dashboard/admin/orders", "/dashboard/admin/cancellations"];

function isTabActive(href: string, pathname: string): boolean {
  return href === "/dashboard/admin" ? pathname === "/dashboard/admin" : pathname.startsWith(href);
}

export default function AdminSubLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { currentUser, isLoading } = useAuth();
  const isMobile = useIsMobile();

  const isAdmin    = currentUser?.role === "admin";
  const isOperator = currentUser?.role === "operator";

  // Badges on tabs; refreshed on navigation so a just-resolved item disappears.
  const [counters, setCounters] = useState<WorkCounters | null>(null);
  useEffect(() => {
    if (!isAdmin && !isOperator) return;
    getWorkCounters().then(setCounters).catch(() => setCounters(null));
  }, [pathname, isAdmin, isOperator]);

  useEffect(() => {
    if (!isLoading && !isAdmin && !isOperator) {
      router.replace("/dashboard/orders");
    }
  }, [isLoading, isAdmin, isOperator, router]);

  if (isLoading || (!isAdmin && !isOperator)) return null;

  const roleTabs = isAdmin ? ALL_ADMIN_TABS : ALL_ADMIN_TABS.filter((t) => !t.adminOnly);
  const tabs = isMobile ? roleTabs.filter((t) => MOBILE_PATHS.includes(t.href)) : roleTabs;
  const mobileAllowed = MOBILE_PATHS.some((p) => isTabActive(p, pathname));

  if (isMobile && !mobileAllowed) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "60vh", padding: "40px 24px", textAlign: "center" }}>
        <div style={{ width: 56, height: 56, borderRadius: 14, background: "#0B2545", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 20 }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="3" width="20" height="14" rx="2" /><path d="M8 21h8M12 17v4" />
          </svg>
        </div>
        <h2 style={{ margin: "0 0 10px", font: "700 20px/1.3 Inter Variable, sans-serif", color: "#0B2545" }}>
          Только для компьютера
        </h2>
        <p style={{ margin: "0 0 20px", font: "400 14px/1.6 Inter Variable, sans-serif", color: "#64748b", maxWidth: 280 }}>
          Этот раздел доступен только с компьютера. С телефона можно работать с заказами и заявками на отмену.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%", maxWidth: 280 }}>
          {tabs.map(({ label, href }) => (
            <Link key={href} href={href} style={{ padding: "11px 16px", borderRadius: 10, background: "#0B2545", color: "#fff", fontSize: 14, fontWeight: 600, textDecoration: "none" }}>
              {label}
            </Link>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Admin header */}
      <div style={{ marginBottom: isMobile ? 16 : 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: isMobile ? 12 : 16 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: "#0B2545", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
            </svg>
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0B2545" }}>
              {isAdmin ? "Администрирование" : "Панель оператора"}
            </h1>
            <p style={{ margin: 0, fontSize: 13, color: "#64748b" }}>
              {isAdmin ? "Управление платформой Novex" : "Управление заказами и диспетчеризацией"}
            </p>
          </div>
        </div>

        {/* Sub-nav pills */}
        <div style={{
          display: "flex", gap: 6, background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 12, padding: 4,
          width: isMobile ? "auto" : "fit-content",
          flexWrap: isMobile ? "nowrap" : "wrap",
          overflowX: isMobile ? "auto" : undefined,
          scrollbarWidth: isMobile ? "none" : undefined,
        }}>
          {tabs.map(({ label, href, badge }) => {
            const active = isTabActive(href, pathname);
            const count = badge && counters ? counters[badge] : 0;
            return (
              <Link
                key={href}
                href={href}
                style={{
                  padding: "7px 16px",
                  borderRadius: 8,
                  fontSize: 13,
                  fontWeight: active ? 600 : 500,
                  textDecoration: "none",
                  background: active ? "#0B2545" : "transparent",
                  color: active ? "#ffffff" : "#64748b",
                  transition: "all 0.15s",
                  whiteSpace: "nowrap",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                {label}
                {count > 0 && (
                  <span style={{ minWidth: 18, height: 18, padding: "0 5px", borderRadius: 999, background: active ? "rgba(255,255,255,0.2)" : "#E2E8EE", color: active ? "#ffffff" : "#0B2545", fontSize: 11, fontWeight: 700, display: "inline-flex", alignItems: "center", justifyContent: "center", boxSizing: "border-box" }}>
                    {count}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      </div>

      {children}
    </div>
  );
}
