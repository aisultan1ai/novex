"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";

function IconBell() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function IconLogout() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

const BASE_TABS = [
  { label: "Мои заказы",      href: "/dashboard/orders",       admin: false },
  { label: "Адресная книга",  href: "/dashboard/address-book", admin: false },
  { label: "Профиль",         href: "/dashboard/profile",      admin: false },
  { label: "Отчёты",          href: "/dashboard/reports",      admin: false },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { logout, currentUser } = useAuth();

  const navTabs = [
    ...BASE_TABS,
    ...(currentUser?.role === "admin"
      ? [{ label: "Администрирование", href: "/dashboard/admin", admin: true }]
      : []),
  ];

  function handleLogout() {
    logout();
    router.push("/");
  }

  const displayName = currentUser?.full_name || currentUser?.email || "Пользователь";

  return (
    <div style={{ minHeight: "100vh", background: "#f1f5f9" }}>

      {/* HEADER */}
      <header
        style={{
          height: 60,
          background: "#ffffff",
          borderBottom: "1px solid #e5e7eb",
          padding: "0 40px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          position: "sticky",
          top: 0,
          zIndex: 50,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" style={{ fontSize: 20, fontWeight: 800, color: "#0f172a", textDecoration: "none" }}>
            Novex
          </Link>
          <span style={{ color: "#e5e7eb", fontSize: 18 }}>|</span>
          <span style={{ fontSize: 14, color: "#64748b", fontWeight: 500 }}>
            {displayName}
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            style={{
              width: 36,
              height: 36,
              borderRadius: "50%",
              border: "1px solid #e5e7eb",
              background: "#ffffff",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#64748b",
            }}
          >
            <IconBell />
          </button>
          <button
            onClick={handleLogout}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "8px 14px",
              borderRadius: 10,
              border: "1px solid #e5e7eb",
              background: "#ffffff",
              color: "#64748b",
              fontSize: 13,
              fontWeight: 500,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            <IconLogout />
            Выйти
          </button>
        </div>
      </header>

      {/* NAV TABS */}
      <nav
        style={{
          background: "#ffffff",
          borderBottom: "1px solid #e5e7eb",
          padding: "0 40px",
          display: "flex",
          gap: 0,
        }}
      >
        {navTabs.map(({ label, href, admin }) => {
          const active = pathname.startsWith(href);
          const activeColor = admin ? "#d97706" : "#0f172a";
          const activeBorder = admin ? "#d97706" : "#0f172a";
          const idleColor = admin ? "#b45309" : "#64748b";
          return (
            <Link
              key={href}
              href={href}
              style={{
                padding: "14px 20px",
                fontSize: 14,
                fontWeight: active ? 600 : 500,
                textDecoration: "none",
                color: active ? activeColor : idleColor,
                borderBottom: active ? `2px solid ${activeBorder}` : "2px solid transparent",
                marginBottom: -1,
                transition: "color 0.15s",
                whiteSpace: "nowrap",
              }}
              onMouseEnter={(e) => {
                if (!active) (e.currentTarget as HTMLAnchorElement).style.color = activeColor;
              }}
              onMouseLeave={(e) => {
                if (!active) (e.currentTarget as HTMLAnchorElement).style.color = idleColor;
              }}
            >
              {label}
            </Link>
          );
        })}
      </nav>

      {/* CONTENT */}
      <div
        style={{
          padding: "32px 40px",
          background: "#f1f5f9",
          minHeight: "calc(100vh - 120px)",
          fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif",
        }}
      >
        {children}
      </div>
    </div>
  );
}
