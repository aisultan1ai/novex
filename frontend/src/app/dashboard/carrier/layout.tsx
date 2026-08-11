"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/providers/auth-provider";

const TABS = [
  { label: "Обзор",      href: "/dashboard/carrier" },
  { label: "Заказы",     href: "/dashboard/carrier/orders" },
  { label: "Финансы",    href: "/dashboard/carrier/commissions" },
  { label: "Тарифы",     href: "/dashboard/carrier/tariffs" },
  { label: "Интеграция", href: "/dashboard/carrier/integration" },
  { label: "API Docs",   href: "/dashboard/carrier/docs" },
];

export default function CarrierLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { currentUser, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && currentUser?.role !== "carrier") {
      router.replace("/dashboard/orders");
    }
  }, [isLoading, currentUser, router]);

  if (isLoading || currentUser?.role !== "carrier") return null;

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: "#4338ca", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="1" y="3" width="15" height="13" rx="1"/><path d="M16 8h4l3 5v3h-7V8z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>
            </svg>
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0E1826" }}>Кабинет перевозчика</h1>
            <p style={{ margin: 0, fontSize: 13, color: "#64748b" }}>Управление интеграцией с Novex</p>
          </div>
        </div>

        <div style={{ display: "flex", gap: 6, background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 12, padding: 4, width: "fit-content" }}>
          {TABS.map(({ label, href }) => {
            const active = href === "/dashboard/carrier"
              ? pathname === "/dashboard/carrier"
              : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                style={{
                  padding: "7px 18px",
                  borderRadius: 8,
                  fontSize: 13,
                  fontWeight: active ? 600 : 500,
                  textDecoration: "none",
                  background: active ? "#4338ca" : "transparent",
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
