"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/providers/auth-provider";

const ADMIN_TABS = [
  { label: "Обзор",         href: "/dashboard/admin" },
  { label: "Заказы",        href: "/dashboard/admin/orders" },
  { label: "Пользователи",  href: "/dashboard/admin/users" },
  { label: "Перевозчики",   href: "/dashboard/admin/carriers" },
];

export default function AdminSubLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { currentUser, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && currentUser?.role !== "admin") {
      router.replace("/dashboard/orders");
    }
  }, [isLoading, currentUser, router]);

  if (isLoading || currentUser?.role !== "admin") return null;

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
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0f172a" }}>Администрирование</h1>
            <p style={{ margin: 0, fontSize: 13, color: "#64748b" }}>Управление платформой Novex</p>
          </div>
        </div>

        {/* Sub-nav pills */}
        <div style={{ display: "flex", gap: 6, background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 12, padding: 4, width: "fit-content" }}>
          {ADMIN_TABS.map(({ label, href }) => {
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
