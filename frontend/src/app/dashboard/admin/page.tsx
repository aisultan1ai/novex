"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { getAdminStats } from "@/lib/api/admin";
import type { AdminStats } from "@/types/admin";

function StatCard({ label, value, sub, href, color }: { label: string; value: number | string; sub?: string; href?: string; color?: string }) {
  const content = (
    <div
      style={{
        background: "#ffffff",
        border: "1px solid #e5e7eb",
        borderRadius: 16,
        padding: "24px 28px",
        cursor: href ? "pointer" : "default",
        transition: "box-shadow 0.15s",
      }}
      onMouseEnter={(e) => { if (href) e.currentTarget.style.boxShadow = "0 4px 20px rgba(0,0,0,0.08)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.boxShadow = "none"; }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, color: "#64748b", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.04em" }}>
        {label}
      </div>
      <div style={{ fontSize: 36, fontWeight: 800, color: color ?? "#0f172a", lineHeight: 1 }}>{value}</div>
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
        style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 14, padding: "20px 24px", display: "flex", gap: 16, alignItems: "flex-start", cursor: "pointer", transition: "box-shadow 0.15s" }}
        onMouseEnter={(e) => { e.currentTarget.style.boxShadow = "0 4px 20px rgba(0,0,0,0.08)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.boxShadow = "none"; }}
      >
        <span style={{ fontSize: 28 }}>{icon}</span>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#0f172a" }}>{title}</div>
          <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>{desc}</div>
        </div>
      </div>
    </Link>
  );
}

export default function AdminOverviewPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminStats()
      .then(setStats)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <>
      {error && (
        <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 14, marginBottom: 24 }}>
          {error}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 20, marginBottom: 32 }}>
        <StatCard
          label="Пользователи"
          value={stats?.total_users ?? "—"}
          sub={stats ? `${stats.active_users} активных` : undefined}
          href="/dashboard/admin/users"
        />
        <StatCard
          label="Заказы"
          value={stats?.total_orders ?? "—"}
          href="/dashboard/admin/orders"
        />
        <StatCard
          label="Оплачено"
          value={stats?.paid_orders ?? "—"}
          color="#16a34a"
          sub="заказов"
        />
        <StatCard
          label="Конверсия"
          value={stats ? `${Math.round((stats.paid_orders / Math.max(stats.total_orders, 1)) * 100)}%` : "—"}
          sub="заказов оплачено"
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <QuickLink href="/dashboard/admin/orders" title="Управление заказами" desc="Просмотр всех заказов, смена статуса" icon="📦" />
        <QuickLink href="/dashboard/admin/users" title="Пользователи" desc="Список клиентов, детали аккаунтов" icon="👥" />
        <QuickLink href="/dashboard/admin/carriers" title="Перевозчики" desc="Добавить перевозчика, загрузить тарифы" icon="🚚" />
        <QuickLink href="/dashboard/admin/carriers" title="Тарифные сетки" desc="Загрузка тарифов через JSON-файл" icon="📋" />
      </div>
    </>
  );
}
