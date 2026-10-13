"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import WorkCounters from "@/components/admin/WorkCounters";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { getAdminStats } from "@/lib/api/admin";
import type { AdminStats } from "@/types/admin";
import { Link } from "@/i18n/navigation";

function StatCard({ label, value, sub, href, color }: { label: string; value: number | string; sub?: string; href?: string; color?: string }) {
  const content = (
    <div
      style={{
        background: "#ffffff",
        border: "1px solid #E2E8EE",
        borderRadius: 16,
        padding: "24px 28px",
        cursor: href ? "pointer" : "default",
        transition: "box-shadow 0.15s",
        height: "100%",
        boxSizing: "border-box",
        minHeight: 110,
      }}
      onMouseEnter={(e) => { if (href) e.currentTarget.style.boxShadow = "0 4px 20px rgba(0,0,0,0.08)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.boxShadow = "none"; }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, color: "#64748b", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.04em" }}>
        {label}
      </div>
      <div style={{ fontSize: 36, fontWeight: 800, color: color ?? "#0B2545", lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 8 }}>{sub}</div>}
    </div>
  );
  if (href) return <Link href={href} style={{ textDecoration: "none" }}>{content}</Link>;
  return content;
}

function QuickLink({ href, title, desc, icon }: { href: string; title: string; desc: string; icon: string }) {
  return (
    <Link href={href} style={{ textDecoration: "none" }}>
      <div
        style={{ background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 14, padding: "20px 24px", display: "flex", gap: 16, alignItems: "flex-start", cursor: "pointer", transition: "box-shadow 0.15s" }}
        onMouseEnter={(e) => { e.currentTarget.style.boxShadow = "0 4px 20px rgba(0,0,0,0.08)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.boxShadow = "none"; }}
      >
        <span style={{ fontSize: 28 }}>{icon}</span>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#0B2545" }}>{title}</div>
          <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>{desc}</div>
        </div>
      </div>
    </Link>
  );
}

export default function AdminOverviewPage() {
  const t = useTranslations("admin.overview");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isMobile = useIsMobile();

  useEffect(() => {
    getAdminStats()
      .then(setStats)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <>
      <WorkCounters />

      {error && (
        <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 14, marginBottom: 24 }}>
          {error}
        </div>
      )}

      <div style={{ fontSize: 13, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 10 }}>{t("stats")}</div>
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(auto-fit, minmax(170px, 1fr))", gap: isMobile ? 10 : 20, marginBottom: 32 }}>
        <StatCard
          label={t("users")}
          value={stats?.total_users ?? "-"}
          sub={stats ? t("activeUsers", { n: stats.active_users }) : undefined}
          href="/dashboard/admin/users"
        />
        <StatCard
          label={t("orders")}
          value={stats?.total_orders ?? "-"}
          href="/dashboard/admin/orders"
        />
        <StatCard
          label={t("paid")}
          value={stats?.paid_orders ?? "-"}
          color="#16a34a"
          sub={t("paidSub")}
        />
        <StatCard
          label={t("conversion")}
          value={stats ? `${Math.round((stats.paid_orders / Math.max(stats.total_orders, 1)) * 100)}%` : "-"}
          sub={t("conversionSub")}
        />
      </div>

      {/* Quick links lead to desktop-only sections — hidden on phones. */}
      {!isMobile && <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <QuickLink href="/dashboard/admin/orders" title={t("quick.orders.title")} desc={t("quick.orders.desc")} icon="📦" />
        <QuickLink href="/dashboard/admin/users" title={t("quick.users.title")} desc={t("quick.users.desc")} icon="👥" />
        <QuickLink href="/dashboard/admin/carriers" title={t("quick.carriers.title")} desc={t("quick.carriers.desc")} icon="🚚" />
        <QuickLink href="/dashboard/admin/commissions" title={t("quick.commissions.title")} desc={t("quick.commissions.desc")} icon="💰" />
      </div>}
    </>
  );
}
