"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";

const ALL_ADMIN_TABS = [
  { label: "Обзор",           href: "/dashboard/admin",                adminOnly: true  },
  { label: "Заказы",          href: "/dashboard/admin/orders",         adminOnly: false },
  { label: "Пользователи",    href: "/dashboard/admin/users",          adminOnly: false },
  { label: "Перевозчики",     href: "/dashboard/admin/carriers",       adminOnly: false },
  { label: "Отзывы",          href: "/dashboard/admin/reviews",        adminOnly: true  },
  { label: "Комиссии",        href: "/dashboard/admin/commissions",    adminOnly: false },
  { label: "Очередь заказов", href: "/dashboard/admin/dispatch-queue", adminOnly: false },
  { label: "Настройки",       href: "/dashboard/admin/settings",       adminOnly: false },
  { label: "Аудит",           href: "/dashboard/admin/audit-logs",     adminOnly: true  },
];

export default function AdminSubLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { currentUser, isLoading } = useAuth();
  const isMobile = useIsMobile();

  const isAdmin    = currentUser?.role === "admin";
  const isOperator = currentUser?.role === "operator";

  useEffect(() => {
    if (!isLoading && !isAdmin && !isOperator) {
      router.replace("/dashboard/orders");
    }
  }, [isLoading, isAdmin, isOperator, router]);

  if (isLoading || (!isAdmin && !isOperator)) return null;

  const tabs = isAdmin ? ALL_ADMIN_TABS : ALL_ADMIN_TABS.filter((t) => !t.adminOnly);

  if (isMobile) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "60vh", padding: "40px 24px", textAlign: "center" }}>
        <div style={{ width: 56, height: 56, borderRadius: 14, background: "#0f172a", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 20 }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="3" width="20" height="14" rx="2" /><path d="M8 21h8M12 17v4" />
          </svg>
        </div>
        <h2 style={{ margin: "0 0 10px", font: "700 20px/1.3 Inter Variable, sans-serif", color: "#0f172a" }}>
          Только для компьютера
        </h2>
        <p style={{ margin: 0, font: "400 14px/1.6 Inter Variable, sans-serif", color: "#64748b", maxWidth: 280 }}>
          Административная панель доступна только с компьютера или ноутбука.
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Admin header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: "#0f172a", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
            </svg>
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0f172a" }}>
              {isAdmin ? "Администрирование" : "Панель оператора"}
            </h1>
            <p style={{ margin: 0, fontSize: 13, color: "#64748b" }}>
              {isAdmin ? "Управление платформой Novex" : "Управление заказами и диспетчеризацией"}
            </p>
          </div>
        </div>

        {/* Sub-nav pills */}
        <div style={{ display: "flex", gap: 6, background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 12, padding: 4, width: "fit-content", flexWrap: "wrap" }}>
          {tabs.map(({ label, href }) => {
            const active = href === "/dashboard/admin"
              ? pathname === "/dashboard/admin"
              : pathname.startsWith(href);
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
                  background: active ? "#0f172a" : "transparent",
                  color: active ? "#ffffff" : "#64748b",
                  transition: "all 0.15s",
                  whiteSpace: "nowrap",
                }}
              >
                {label}
              </Link>
            );
          })}
        </div>
      </div>

      {children}
    </div>
  );
}
