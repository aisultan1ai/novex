"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, usePathname } from "next/navigation";
import { getAdminCarrier } from "@/lib/api/admin";
import type { AdminCarrierDetail } from "@/types/admin";
import { useIsAdmin } from "@/hooks/use-is-admin";

export default function CarrierDetailLayout({ children }: { children: ReactNode }) {
  const isAdmin = useIsAdmin();
  const { id } = useParams<{ id: string }>();
  const carrierId = Number(id);
  const pathname = usePathname();
  const [carrier, setCarrier] = useState<AdminCarrierDetail | null>(null);

  useEffect(() => {
    getAdminCarrier(carrierId).then(setCarrier).catch(() => {});
  }, [carrierId]);

  const base = `/dashboard/admin/carriers/${carrierId}`;
  const tabs = [
    { label: "Обзор",      href: base },
    { label: "Тарифы",     href: `${base}/tariffs` },
    // Integration / API tabs show carrier secrets — admin only.
    ...(isAdmin
      ? [
          { label: "Интеграция", href: `${base}/integration` },
          { label: "API",        href: `${base}/api` },
        ]
      : []),
  ];

  return (
    <div>
      <Link
        href="/dashboard/admin/carriers"
        style={{ color: "#64748b", fontSize: 13, textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4, marginBottom: 14 }}
      >
        ← Перевозчики
      </Link>

      {/* Carrier header */}
      <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 14, padding: "16px 22px", display: "flex", alignItems: "center", gap: 14, minHeight: 72, marginBottom: 0 }}>
        {carrier ? (
          <>
            <div style={{ width: 40, height: 40, borderRadius: 10, background: "#0B2545", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, fontWeight: 800, color: "#fff", flexShrink: 0 }}>
              {carrier.name[0]}
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <span style={{ fontSize: 17, fontWeight: 800, color: "#0B2545" }}>{carrier.name}</span>
                <span style={{ fontFamily: "monospace", fontSize: 12, color: "#94a3b8", background: "#f1f5f9", padding: "2px 8px", borderRadius: 6 }}>{carrier.code}</span>
                <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: carrier.is_active ? "#dcfce7" : "#f1f5f9", color: carrier.is_active ? "#166534" : "#94a3b8" }}>
                  {carrier.is_active ? "Активен" : "Неактивен"}
                </span>
              </div>
              {carrier.description && (
                <div style={{ fontSize: 12, color: "#64748b", marginTop: 3 }}>{carrier.description}</div>
              )}
            </div>
          </>
        ) : (
          <div style={{ height: 22, width: 180, background: "#f1f5f9", borderRadius: 6 }} />
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 2, borderBottom: "2px solid #f1f5f9", marginBottom: 24 }}>
        {tabs.map(({ label, href }) => {
          const active = href === base ? pathname === base : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              style={{
                padding: "12px 20px",
                fontSize: 14,
                fontWeight: active ? 700 : 500,
                textDecoration: "none",
                color: active ? "#0B2545" : "#64748b",
                borderBottom: `2px solid ${active ? "#0B2545" : "transparent"}`,
                marginBottom: -2,
                whiteSpace: "nowrap",
                transition: "color 0.15s",
              }}
            >
              {label}
            </Link>
          );
        })}
      </div>

      {children}
    </div>
  );
}
