"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { getAdminUser, updateAdminUser } from "@/lib/api/admin";
import type { AdminUserDetail } from "@/types/admin";

const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик", shipment_details_completed: "Детали", ready_for_checkout: "К оплате",
  awaiting_payment: "Ожидает оплаты", paid: "Оплачен", sent_to_carrier: "Передан",
  picked_up: "Забран", in_transit: "В пути", arrived: "Прибыл",
  delivered: "Доставлен", cancelled: "Отменён", return: "Возврат",
};
const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  paid: { bg: "#dcfce7", color: "#166534" }, delivered: { bg: "#dcfce7", color: "#166534" },
  cancelled: { bg: "#fee2e2", color: "#991b1b" }, return: { bg: "#fee2e2", color: "#991b1b" },
  in_transit: { bg: "#ede9fe", color: "#5b21b6" },
};

function formatPrice(price: number, currency: string) {
  return `${new Intl.NumberFormat("ru-RU").format(price)} ${currency}`;
}

function getInitials(name: string | null, email: string) {
  if (name) return name.trim().slice(0, 2).toUpperCase();
  return email.slice(0, 2).toUpperCase();
}

export default function AdminUserDetailPage() {
  const params = useParams();
  const userId = Number(params.id);

  const [user, setUser] = useState<AdminUserDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState(false);

  function load() {
    setIsLoading(true);
    getAdminUser(userId)
      .then(setUser)
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => { load(); }, [userId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleToggle() {
    if (!user) return;
    setToggling(true);
    try {
      await updateAdminUser(user.id, { is_active: !user.is_active });
      load();
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setToggling(false);
    }
  }

  if (isLoading) return <div style={{ padding: 48, textAlign: "center", color: "#64748b" }}>Загружаем…</div>;
  if (error) return <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c" }}>{error}</div>;
  if (!user) return null;

  return (
    <>
      <div style={{ marginBottom: 20 }}>
        <Link href="/dashboard/admin/users" style={{ color: "#64748b", fontSize: 14, textDecoration: "none" }}>← Пользователи</Link>
      </div>

      <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, padding: "28px 32px", marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 24 }}>
          <div style={{ width: 64, height: 64, borderRadius: "50%", background: "#0f172a", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24, fontWeight: 800, color: "#ffffff", flexShrink: 0 }}>
            {getInitials(user.full_name, user.email)}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: "#0f172a" }}>{user.full_name || user.email}</div>
            {user.full_name && <div style={{ fontSize: 14, color: "#64748b" }}>{user.email}</div>}
            <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
              <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: "#ede9fe", color: "#5b21b6" }}>{user.role}</span>
              <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: user.is_active ? "#dcfce7" : "#fee2e2", color: user.is_active ? "#166534" : "#991b1b" }}>{user.is_active ? "Активен" : "Заблокирован"}</span>
              {user.customer_type && <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: "#dbeafe", color: "#1e40af" }}>{user.customer_type === "company" ? "Компания" : "Физ. лицо"}</span>}
            </div>
          </div>
          <button
            onClick={() => void handleToggle()}
            disabled={toggling}
            style={{ padding: "10px 20px", borderRadius: 10, border: `1px solid ${user.is_active ? "#fecaca" : "#bbf7d0"}`, background: user.is_active ? "#fef2f2" : "#f0fdf4", color: user.is_active ? "#b91c1c" : "#166534", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", opacity: toggling ? 0.7 : 1 }}
          >
            {user.is_active ? "Заблокировать" : "Разблокировать"}
          </button>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
          {[
            ["ID", `#${user.id}`],
            ["Телефон", user.phone || "—"],
            ["Компания", user.company_name || "—"],
            ["Тип оплаты", user.billing_mode || "—"],
            ["Заказов", user.orders.length],
            ["Зарегистрирован", new Date(user.created_at).toLocaleDateString("ru-RU")],
          ].map(([label, value]) => (
            <div key={String(label)}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>{label}</div>
              <div style={{ fontSize: 15, fontWeight: 600, color: "#0f172a" }}>{value}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
        <div style={{ padding: "16px 24px", borderBottom: "1px solid #e5e7eb" }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#0f172a" }}>Заказы ({user.orders.length})</h2>
        </div>

        {user.orders.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "#94a3b8", fontSize: 14 }}>Заказов нет</div>
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "80px 1fr 160px 120px 120px", gap: 12, padding: "10px 24px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              <span>№</span><span>Маршрут</span><span>Перевозчик</span><span>Сумма</span><span>Статус</span>
            </div>
            {user.orders.map((order, idx) => {
              const sc = STATUS_COLORS[order.status] ?? { bg: "#f1f5f9", color: "#475569" };
              return (
                <div key={order.id} style={{ display: "grid", gridTemplateColumns: "80px 1fr 160px 120px 120px", gap: 12, padding: "14px 24px", borderBottom: idx < user.orders.length - 1 ? "1px solid #f1f5f9" : "none", alignItems: "center" }}>
                  <span style={{ fontFamily: "monospace", fontSize: 13, color: "#94a3b8", fontWeight: 600 }}>#{order.id}</span>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#0f172a" }}>{order.from_city} → {order.to_city}</div>
                    <div style={{ fontSize: 12, color: "#94a3b8" }}>{new Date(order.created_at).toLocaleDateString("ru-RU")}</div>
                  </div>
                  <div style={{ fontSize: 13, color: "#475569" }}>{order.carrier_name}</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>{formatPrice(order.price, order.currency)}</div>
                  <span style={{ display: "inline-block", padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: sc.bg, color: sc.color }}>
                    {STATUS_LABELS[order.status] ?? order.status}
                  </span>
                </div>
              );
            })}
          </>
        )}
      </div>
    </>
  );
}
